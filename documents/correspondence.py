from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile

from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone

from .models import CorrespondenceRecord, CorrespondenceSequence


OUTGOING_TEMPLATE_PATH = Path(__file__).resolve().parent / "document_templates" / "outgoing_letter_template.docx"
MEMO_TEMPLATE_PATH = Path(__file__).resolve().parent / "document_templates" / "service_memo_template.docx"
NUMBER_MARKER = "<w:t>№</w:t>".encode("utf-8")
SUBJECT_PREFIX_MARKER = '<w:t xml:space="preserve">О </w:t>'.encode("utf-8")
SUBJECT_ELLIPSIS_MARKER = '<w:t xml:space="preserve"> …</w:t>'.encode("utf-8")
ADDRESSEE_MARKER = '<w:t>Наименование компании ХХ «ХХХ»</w:t>'.encode("utf-8")
SALUTATION_MARKER = '<w:t>ХХХХХ Х</w:t>'.encode("utf-8")
MEMO_DATE_MARKER = "<w:t>от</w:t>".encode("utf-8")
MEMO_SUBJECT_MARKER = "<w:t>О…</w:t>".encode("utf-8")
MEMO_ADDRESSEE_MARKER = "<w:t>ФИО</w:t>".encode("utf-8")
MEMO_SALUTATION_MARKER = '<w:t xml:space="preserve"> ….</w:t>'.encode("utf-8")
MEMO_TRAILING_SPACE_MARKER = '<w:t xml:space="preserve"> </w:t>'.encode("utf-8")
OUTGOING_START_NUMBER = 657


def _insert_text_in_adjacent_cell(
    document_xml,
    marker,
    value,
    marker_missing_message,
    adjacent_cell_missing_message,
    font_size=24,
):
    marker_position = document_xml.find(marker)
    if marker_position == -1:
        raise ValueError(marker_missing_message)

    marker_cell_end = document_xml.find(b"</w:tc>", marker_position)
    number_cell_start = document_xml.find(b"<w:tc", marker_cell_end)
    number_cell_end = document_xml.find(b"</w:tc>", number_cell_start)
    paragraph_end = document_xml.find(b"</w:p>", number_cell_start, number_cell_end)
    if min(marker_cell_end, number_cell_start, number_cell_end, paragraph_end) == -1:
        raise ValueError(adjacent_cell_missing_message)

    number_run = (
        '<w:r><w:rPr><w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" '
        f'w:cs="Times New Roman"/><w:sz w:val="{font_size}"/><w:szCs w:val="{font_size}"/></w:rPr>'
        f"<w:t>{escape(str(value).strip())}</w:t></w:r>"
    ).encode("utf-8")
    return document_xml[:paragraph_end] + number_run + document_xml[paragraph_end:]


def _insert_number_in_adjacent_cell(document_xml, registration_number, font_size=24):
    return _insert_text_in_adjacent_cell(
        document_xml,
        NUMBER_MARKER,
        registration_number,
        "В шаблоне не найдена ячейка с символом «№».",
        "В шаблоне не найдена соседняя ячейка для номера.",
        font_size,
    )


def _replace_subject_marker(document_xml, subject):
    if not subject:
        return document_xml
    prefix_position = document_xml.find(SUBJECT_PREFIX_MARKER)
    ellipsis_position = document_xml.find(SUBJECT_ELLIPSIS_MARKER, prefix_position)
    if prefix_position == -1 or ellipsis_position == -1:
        raise ValueError("В шаблоне письма не найдена строка «О …» для наименования.")
    subject_text = subject.strip()
    if subject_text.lower().startswith("о "):
        subject_text = subject_text[2:].lstrip()
    replacement = f'<w:t xml:space="preserve">О {escape(subject_text)}</w:t>'.encode("utf-8")
    document_xml = document_xml.replace(SUBJECT_PREFIX_MARKER, replacement, 1)
    return document_xml.replace(SUBJECT_ELLIPSIS_MARKER, b"<w:t></w:t>", 1)


def _replace_text_marker(document_xml, marker, value, missing_marker_message):
    if not value:
        return document_xml
    if marker not in document_xml:
        raise ValueError(missing_marker_message)
    replacement = f"<w:t>{escape(value.strip())}</w:t>".encode("utf-8")
    return document_xml.replace(marker, replacement, 1)


def _replace_memo_subject_marker(document_xml, subject):
    if not subject:
        return document_xml
    if MEMO_SUBJECT_MARKER not in document_xml:
        raise ValueError("В шаблоне служебной записки не найдена строка «О…» для наименования.")
    subject_text = subject.strip()
    if not subject_text.lower().startswith(("о ", "об ")):
        subject_text = f"О {subject_text}"
    replacement = f"<w:t>{escape(subject_text)}</w:t>".encode("utf-8")
    return document_xml.replace(MEMO_SUBJECT_MARKER, replacement, 1)


def _replace_memo_salutation(document_xml, addressee_person):
    if not addressee_person:
        return document_xml
    marker_position = document_xml.find(MEMO_SALUTATION_MARKER)
    if marker_position == -1:
        raise ValueError("В шаблоне служебной записки не найдено обращение «Уважаемый».")
    replacement = (
        f'<w:t xml:space="preserve"> {escape(addressee_person.strip())}</w:t>'
    ).encode("utf-8")
    document_xml = document_xml.replace(MEMO_SALUTATION_MARKER, replacement, 1)
    trailing_position = document_xml.find(MEMO_TRAILING_SPACE_MARKER, marker_position + len(replacement))
    if trailing_position != -1 and trailing_position - marker_position < 1000:
        document_xml = (
            document_xml[:trailing_position]
            + b"<w:t></w:t>"
            + document_xml[trailing_position + len(MEMO_TRAILING_SPACE_MARKER):]
        )
    return document_xml


@transaction.atomic
def reserve_correspondence_number(user, kind):
    try:
        sequence = CorrespondenceSequence.objects.select_for_update().get(kind=kind)
    except CorrespondenceSequence.DoesNotExist:
        start_number = OUTGOING_START_NUMBER if kind == CorrespondenceRecord.OUTGOING else 1
        CorrespondenceSequence.objects.create(kind=kind, next_number=start_number)
        sequence = CorrespondenceSequence.objects.select_for_update().get(kind=kind)

    existing = (
        CorrespondenceRecord.objects.filter(
            kind=kind,
            status=CorrespondenceRecord.RESERVED,
            created_by=user,
        )
        .order_by("reserved_at", "id")
        .first()
    )
    if existing:
        return existing

    reserved_number = sequence.next_number
    while CorrespondenceRecord.objects.filter(kind=kind, sequence_number=reserved_number).exists():
        reserved_number += 1
    sequence.next_number = reserved_number + 1
    sequence.save(update_fields=["next_number", "updated_at"])

    return CorrespondenceRecord.objects.create(
        kind=kind,
        sequence_number=reserved_number,
        executor=user,
        created_by=user,
    )


def build_outgoing_letter_template(registration_number, subject="", addressee="", addressee_person=""):
    if not OUTGOING_TEMPLATE_PATH.exists():
        raise FileNotFoundError("Шаблон исходящего письма не найден на сервере.")

    output = BytesIO()
    marker_replaced = False

    with ZipFile(OUTGOING_TEMPLATE_PATH, "r") as source, ZipFile(output, "w", ZIP_DEFLATED) as target:
        for item in source.infolist():
            payload = source.read(item.filename)
            if item.filename == "word/document.xml" and NUMBER_MARKER in payload:
                payload = _insert_number_in_adjacent_cell(payload, registration_number)
                payload = _replace_subject_marker(payload, subject)
                payload = _replace_text_marker(
                    payload,
                    ADDRESSEE_MARKER,
                    addressee,
                    "В шаблоне письма не найдено поле для адресата.",
                )
                payload = _replace_text_marker(
                    payload,
                    SALUTATION_MARKER,
                    addressee_person,
                    "В шаблоне письма не найдено обращение «Уважаемый».",
                )
                marker_replaced = True
            target.writestr(item, payload)

    if not marker_replaced:
        raise ValueError("В шаблоне письма не найдено поле «№» для подстановки номера.")
    return output.getvalue()


def attach_generated_outgoing_template(record):
    if record.kind != CorrespondenceRecord.OUTGOING or not record.department_id:
        raise ValueError("Для формирования бланка выберите подразделение.")

    registration_number = record.build_registration_number()
    file_name = f"Исходящее письмо {registration_number}.docx"
    payload = build_outgoing_letter_template(
        registration_number,
        record.subject,
        record.addressee,
        record.addressee_person,
    )

    if record.draft_file:
        record.draft_file.delete(save=False)
    record.registration_number = registration_number
    record.draft_original_name = file_name
    record.template_generated_at = timezone.now()
    record.draft_file.save(file_name, ContentFile(payload), save=False)
    record.save(
        update_fields=[
            "department",
            "subject",
            "addressee",
            "addressee_person",
            "registration_number",
            "draft_file",
            "draft_original_name",
            "template_generated_at",
            "updated_at",
        ]
    )
    return payload, file_name


def build_service_memo_template(registration_number, registration_date, subject="", addressee_person=""):
    if not MEMO_TEMPLATE_PATH.exists():
        raise FileNotFoundError("Шаблон служебной записки не найден на сервере.")

    output = BytesIO()
    marker_replaced = False
    formatted_date = registration_date.strftime("%d.%m.%Y")

    with ZipFile(MEMO_TEMPLATE_PATH, "r") as source, ZipFile(output, "w", ZIP_DEFLATED) as target:
        for item in source.infolist():
            payload = source.read(item.filename)
            if item.filename == "word/document.xml" and NUMBER_MARKER in payload:
                payload = _insert_number_in_adjacent_cell(payload, registration_number, font_size=28)
                payload = _insert_text_in_adjacent_cell(
                    payload,
                    MEMO_DATE_MARKER,
                    formatted_date,
                    "В шаблоне служебной записки не найдено поле «от» для даты.",
                    "В шаблоне служебной записки не найдена соседняя ячейка для даты.",
                    font_size=28,
                )
                payload = _replace_memo_subject_marker(payload, subject)
                payload = _replace_text_marker(
                    payload,
                    MEMO_ADDRESSEE_MARKER,
                    addressee_person,
                    "В шаблоне служебной записки не найдено поле «ФИО».",
                )
                payload = _replace_memo_salutation(payload, addressee_person)
                marker_replaced = True
            target.writestr(item, payload)

    if not marker_replaced:
        raise ValueError("В шаблоне служебной записки не найдено поле «№» для подстановки номера.")
    return output.getvalue()


def attach_generated_memo_template(record):
    if record.kind != CorrespondenceRecord.MEMO or not record.department_id:
        raise ValueError("Для формирования бланка выберите подразделение.")

    registration_number = record.build_registration_number()
    file_name = f"Служебная записка {registration_number}.docx"
    payload = build_service_memo_template(
        registration_number,
        record.registration_date,
        record.subject,
        record.addressee_person,
    )

    if record.draft_file:
        record.draft_file.delete(save=False)
    record.registration_number = registration_number
    record.draft_original_name = file_name
    record.template_generated_at = timezone.now()
    record.draft_file.save(file_name, ContentFile(payload), save=False)
    record.save(
        update_fields=[
            "department",
            "registration_date",
            "subject",
            "addressee_person",
            "registration_number",
            "draft_file",
            "draft_original_name",
            "template_generated_at",
            "updated_at",
        ]
    )
    return payload, file_name
