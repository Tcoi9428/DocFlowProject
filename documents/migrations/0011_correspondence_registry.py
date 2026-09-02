import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models

import documents.models


def seed_correspondence_settings(apps, schema_editor):
    Department = apps.get_model("documents", "CorrespondenceDepartment")
    Sequence = apps.get_model("documents", "CorrespondenceSequence")

    for code, name in [
        ("01", "Общий отдел"),
        ("02", "Инжиниринг"),
        ("03", "Сервис"),
    ]:
        Department.objects.get_or_create(code=code, defaults={"name": name})

    for kind in ["outgoing", "incoming", "memo"]:
        start_number = 657 if kind == "outgoing" else 1
        Sequence.objects.get_or_create(kind=kind, defaults={"next_number": start_number})


class Migration(migrations.Migration):

    dependencies = [
        ("documents", "0010_approvaltask_document_version_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="CorrespondenceDepartment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Создано")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Изменено")),
                ("name", models.CharField(max_length=150, unique=True, verbose_name="Наименование")),
                ("code", models.CharField(max_length=2, unique=True, verbose_name="Код в регистрационном номере")),
                ("is_active", models.BooleanField(default=True, verbose_name="Активно")),
            ],
            options={
                "verbose_name": "Подразделение корреспонденции",
                "verbose_name_plural": "Подразделения корреспонденции",
                "ordering": ["code"],
            },
        ),
        migrations.CreateModel(
            name="CorrespondenceSequence",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Создано")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Изменено")),
                (
                    "kind",
                    models.CharField(
                        choices=[
                            ("outgoing", "Исходящая корреспонденция"),
                            ("incoming", "Входящая корреспонденция"),
                            ("memo", "Служебные записки"),
                        ],
                        max_length=20,
                        unique=True,
                        verbose_name="Вид корреспонденции",
                    ),
                ),
                (
                    "next_number",
                    models.PositiveIntegerField(
                        default=1,
                        help_text="Укажите номер, который система выдаст при следующем резервировании.",
                        verbose_name="Следующий порядковый номер",
                    ),
                ),
            ],
            options={
                "verbose_name": "Счетчик корреспонденции",
                "verbose_name_plural": "Счетчики корреспонденции",
                "ordering": ["kind"],
            },
        ),
        migrations.CreateModel(
            name="CorrespondenceRecord",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Создано")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Изменено")),
                (
                    "kind",
                    models.CharField(
                        choices=[
                            ("outgoing", "Исходящая корреспонденция"),
                            ("incoming", "Входящая корреспонденция"),
                            ("memo", "Служебные записки"),
                        ],
                        max_length=20,
                        verbose_name="Вид корреспонденции",
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("reserved", "Номер зарезервирован"),
                            ("registered", "Зарегистрировано"),
                            ("canceled", "Отменено"),
                        ],
                        default="reserved",
                        max_length=20,
                        verbose_name="Статус",
                    ),
                ),
                ("sequence_number", models.PositiveIntegerField(verbose_name="Порядковый номер")),
                ("registration_number", models.CharField(blank=True, db_index=True, max_length=40, verbose_name="Регистрационный номер")),
                ("addressee", models.CharField(blank=True, max_length=250, verbose_name="Адресат")),
                ("addressee_person", models.CharField(blank=True, max_length=250, verbose_name="Кому")),
                ("subject", models.CharField(blank=True, max_length=300, verbose_name="Наименование")),
                ("registration_date", models.DateField(default=django.utils.timezone.localdate, verbose_name="Дата")),
                ("reserved_at", models.DateTimeField(default=django.utils.timezone.now, verbose_name="Номер зарезервирован")),
                ("registered_at", models.DateTimeField(blank=True, null=True, verbose_name="Зарегистрировано")),
                ("template_generated_at", models.DateTimeField(blank=True, null=True, verbose_name="Бланк сформирован")),
                ("draft_file", models.FileField(blank=True, upload_to=documents.models.correspondence_upload_path, verbose_name="Черновик")),
                ("draft_original_name", models.CharField(blank=True, max_length=255, verbose_name="Имя файла черновика")),
                ("signed_file", models.FileField(blank=True, upload_to=documents.models.correspondence_upload_path, verbose_name="Подписанный документ")),
                ("signed_original_name", models.CharField(blank=True, max_length=255, verbose_name="Имя подписанного файла")),
                (
                    "created_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="registered_correspondence",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Кто зарегистрировал",
                    ),
                ),
                (
                    "department",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="correspondence_records",
                        to="documents.correspondencedepartment",
                        verbose_name="Подразделение",
                    ),
                ),
                (
                    "executor",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="executed_correspondence",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Исполнитель",
                    ),
                ),
                (
                    "reply_to",
                    models.ForeignKey(
                        blank=True,
                        limit_choices_to={"kind": "incoming", "status": "registered"},
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="outgoing_replies",
                        to="documents.correspondencerecord",
                        verbose_name="Ответ на входящее письмо",
                    ),
                ),
            ],
            options={
                "verbose_name": "Запись корреспонденции",
                "verbose_name_plural": "Реестр корреспонденции",
                "ordering": ["-registration_date", "-sequence_number"],
            },
        ),
        migrations.AddConstraint(
            model_name="correspondencerecord",
            constraint=models.UniqueConstraint(
                fields=("kind", "sequence_number"),
                name="unique_correspondence_kind_sequence",
            ),
        ),
        migrations.RunPython(seed_correspondence_settings, migrations.RunPython.noop),
    ]
