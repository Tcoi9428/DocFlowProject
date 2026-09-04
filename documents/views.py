import hashlib
import json
from io import BytesIO

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.models import User
from django.http import FileResponse, Http404, JsonResponse
from django.db.models import Count, Q
from django.forms import HiddenInput
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date

from .forms import (
    ApprovalActionForm,
    AttachmentForm,
    CommentForm,
    DelegateForm,
    DocumentForm,
    DocumentSearchForm,
    IncomingCorrespondenceFileForm,
    IncomingCorrespondenceForm,
    MemoCorrespondenceForm,
    OutgoingCorrespondenceForm,
    PasswordResetConfirmForm,
    PasswordResetRequestForm,
    ParallelRevisionCorrectionForm,
    RevisionCorrectionForm,
    ReturnForRevisionForm,
    SignedCorrespondenceFileForm,
)
from .models import (
    ApprovalRoute,
    ApprovalTask,
    Attachment,
    AuditLog,
    CustomFieldDefinition,
    CorrespondenceDepartment,
    CorrespondenceRecord,
    Document,
    DocumentApprover,
    DocumentComment,
    DocumentType,
    Notification,
    PasswordResetRequest,
    RevisionRequest,
)
from .correspondence import (
    attach_generated_memo_template,
    attach_generated_outgoing_template,
    reserve_correspondence_number,
)
from .services import (
    approve_task,
    delegate_task,
    log_action,
    reject_task,
    return_for_revision,
    resubmit_parallel_approval,
    start_approval,
    create_notification,
)


def custom_404(request, exception):
    return render(request, "404.html", status=404)


def is_admin_user(user):
    return user.is_active and (user.is_staff or user.is_superuser)


def notify_admins_about_password_reset(reset_request, request):
    admins = User.objects.filter(is_active=True).filter(Q(is_staff=True) | Q(is_superuser=True)).distinct()
    link_url = reverse("documents:password_reset_admin_detail", args=[reset_request.pk])
    title = f"Запрос сброса пароля: {reset_request.user.username}"
    message = (
        f"Пользователь {reset_request.user.get_full_name() or reset_request.user.username} запросил смену пароля. "
        f"Код подтверждения: {reset_request.code}. Код действует до {reset_request.expires_at:%d.%m.%Y %H:%M}."
    )
    for admin_user in admins:
        Notification.objects.create(
            recipient=admin_user,
            notification_type=Notification.PASSWORD_RESET,
            title=title,
            message=message,
            link_url=link_url,
        )


def visible_documents_for(user):
    queryset = Document.objects.select_related(
        "document_type",
        "author",
        "author__userprofile",
        "responsible",
        "responsible__userprofile",
        "department",
        "route",
    ).prefetch_related(
        "attachments",
        "approval_tasks",
        "approval_tasks__step",
    )
    if user.is_superuser or user.has_perm("documents.view_all_documents"):
        return queryset
    return queryset.filter(
        Q(author=user)
        | Q(responsible=user)
        | Q(approval_tasks__approver=user)
    ).distinct()


def password_reset_request(request):
    if request.user.is_authenticated:
        return redirect("documents:my_documents")
    form = PasswordResetRequestForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        if form.user:
            reset_request = PasswordResetRequest.create_for_user(form.user)
            notify_admins_about_password_reset(reset_request, request)
        messages.success(
            request,
            "Если пользователь найден, администратор получит уведомление с 4-значным кодом подтверждения.",
        )
        return redirect("documents:password_reset_confirm")
    return render(request, "registration/password_reset_request.html", {"form": form})


def password_reset_confirm(request):
    if request.user.is_authenticated:
        return redirect("documents:my_documents")
    form = PasswordResetConfirmForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.user.set_password(form.cleaned_data["new_password1"])
        form.user.save(update_fields=["password"])
        form.reset_request.mark_used()
        messages.success(request, "Пароль изменен. Теперь можно войти в систему.")
        return redirect("login")
    return render(request, "registration/password_reset_confirm.html", {"form": form})


@login_required
@user_passes_test(is_admin_user)
def password_reset_admin_detail(request, pk):
    reset_request = get_object_or_404(
        PasswordResetRequest.objects.select_related("user", "user__userprofile"),
        pk=pk,
    )
    return render(request, "documents/password_reset_admin_detail.html", {"reset_request": reset_request})


def save_configured_approvers(document, request):
    approver_ids = request.POST.getlist("approver_user")
    due_days = request.POST.getlist("approver_due_days")
    names = request.POST.getlist("approver_name")
    document.configured_approvers.all().delete()

    order = 1
    for index, approver_id in enumerate(approver_ids):
        if not approver_id:
            continue
        due_days_value = due_days[index] if index < len(due_days) and due_days[index] else 3
        name = names[index] if index < len(names) else ""
        DocumentApprover.objects.create(
            document=document,
            approver_id=approver_id,
            name=name or f"Согласование {order}",
            order=order,
            due_days=due_days_value,
        )
        order += 1


def document_form_context(form, title, selected_type_id="", document=None):
    users = User.objects.filter(is_active=True).select_related("userprofile").order_by("last_name", "first_name", "username")
    routes = ApprovalRoute.objects.filter(is_active=True).select_related("document_type").prefetch_related(
        "steps",
        "steps__approver",
        "steps__approver__userprofile",
    )
    route_templates = {}
    for route in routes:
        route_templates[str(route.id)] = {
            "route_type": route.route_type,
            "steps": [
                {
                    "user_id": step.approver_id,
                    "name": step.name,
                    "due_days": step.due_days,
                }
                for step in route.steps.all().order_by("order")
            ],
        }

    configured_approvers = []
    if document:
        configured_approvers = list(document.configured_approvers.select_related("approver", "approver__userprofile").order_by("order"))

    return {
        "form": form,
        "title": title,
        "document": document,
        "document_types": DocumentType.objects.filter(is_active=True).order_by("name"),
        "selected_type_id": str(selected_type_id or ""),
        "users": users,
        "configured_approvers": configured_approvers,
        "route_templates_json": json.dumps(route_templates, ensure_ascii=False),
    }


@login_required
def dashboard(request):
    my_documents = visible_documents_for(request.user).filter(is_deleted=False)
    approval_tasks = ApprovalTask.objects.filter(approver=request.user, status=ApprovalTask.PENDING)
    context = {
        "created_count": my_documents.count(),
        "pending_count": approval_tasks.count(),
        "overdue_count": approval_tasks.filter(due_date__lt=timezone.localdate()).count(),
        "recent_documents": my_documents[:5],
        "approval_tasks": approval_tasks.select_related("document", "document__document_type", "approver", "approver__userprofile")[:5],
    }
    return render(request, "documents/dashboard.html", context)


@login_required
def correspondence_registry(request, section="outgoing"):
    section_kinds = {
        "outgoing": CorrespondenceRecord.OUTGOING,
        "incoming": CorrespondenceRecord.INCOMING,
        "memos": CorrespondenceRecord.MEMO,
    }
    if section not in section_kinds:
        raise Http404("Раздел корреспонденции не найден.")

    scope = request.GET.get("scope", "mine")
    query = request.GET.get("q", "").strip()[:200]
    records = (
        CorrespondenceRecord.objects.select_related(
            "department",
            "executor",
            "executor__userprofile",
            "created_by",
            "created_by__userprofile",
            "reply_to",
            "related_outgoing",
        )
        .filter(
            kind=section_kinds[section],
            status=CorrespondenceRecord.REGISTERED,
        )
    )
    if scope != "all":
        scope = "mine"
        records = records.filter(Q(created_by=request.user) | Q(executor=request.user)).distinct()
    if query:
        records = records.filter(
            Q(registration_number__icontains=query)
            | Q(external_document_number__icontains=query)
            | Q(related_document_number__icontains=query)
            | Q(subject__icontains=query)
            | Q(addressee__icontains=query)
            | Q(addressee_person__icontains=query)
            | Q(sender__icontains=query)
        )

    return render(
        request,
        "documents/correspondence_registry.html",
        {
            "active_section": section,
            "scope": scope,
            "query": query,
            "records": records,
        },
    )


@login_required
def correspondence_guide(request):
    return render(
        request,
        "documents/correspondence_guide.html",
        {"active_section": "guide"},
    )


@login_required
def incoming_correspondence_create(request):
    if request.method == "POST":
        record = get_object_or_404(
            CorrespondenceRecord,
            pk=request.POST.get("reservation_id"),
            kind=CorrespondenceRecord.INCOMING,
            status=CorrespondenceRecord.RESERVED,
            created_by=request.user,
        )
        form = IncomingCorrespondenceForm(request.POST, request.FILES, instance=record)
        if form.is_valid():
            incoming_file = form.cleaned_data.get("incoming_file")
            record = form.save(commit=False)
            record.executor = request.user
            record.registration_number = record.build_registration_number()
            if incoming_file:
                record.incoming_original_name = incoming_file.name
            record.status = CorrespondenceRecord.REGISTERED
            record.registered_at = timezone.now()
            record.save()
            messages.success(request, f"Входящее письмо {record.registration_number} зарегистрировано.")
            return redirect("documents:incoming_correspondence_detail", pk=record.pk)
    else:
        record = reserve_correspondence_number(request.user, CorrespondenceRecord.INCOMING)
        form = IncomingCorrespondenceForm(instance=record)

    return render(
        request,
        "documents/incoming_correspondence_form.html",
        {
            "record": record,
            "form": form,
        },
    )


@login_required
def incoming_correspondence_detail(request, pk):
    record = get_object_or_404(
        CorrespondenceRecord.objects.select_related(
            "department",
            "executor",
            "executor__userprofile",
            "created_by",
            "created_by__userprofile",
            "related_outgoing",
        ),
        pk=pk,
        kind=CorrespondenceRecord.INCOMING,
        status=CorrespondenceRecord.REGISTERED,
    )
    can_update = request.user.is_superuser or request.user == record.created_by
    return render(
        request,
        "documents/incoming_correspondence_detail.html",
        {
            "record": record,
            "incoming_file_form": IncomingCorrespondenceFileForm(instance=record),
            "can_update": can_update,
        },
    )


@login_required
def incoming_correspondence_file_upload(request, pk):
    record = get_object_or_404(
        CorrespondenceRecord,
        pk=pk,
        kind=CorrespondenceRecord.INCOMING,
        status=CorrespondenceRecord.REGISTERED,
    )
    if not (request.user.is_superuser or request.user == record.created_by):
        messages.error(request, "Заменить файл может только регистратор или администратор.")
        return redirect("documents:incoming_correspondence_detail", pk=record.pk)
    if request.method == "POST":
        previous_file_name = record.incoming_file.name if record.incoming_file else ""
        file_storage = record.incoming_file.storage
        form = IncomingCorrespondenceFileForm(request.POST, request.FILES, instance=record)
        if form.is_valid():
            uploaded_file = form.cleaned_data["incoming_file"]
            record = form.save(commit=False)
            record.incoming_original_name = uploaded_file.name
            record.save(update_fields=["incoming_file", "incoming_original_name", "updated_at"])
            if previous_file_name and previous_file_name != record.incoming_file.name:
                file_storage.delete(previous_file_name)
            messages.success(request, "Файл входящего письма сохранен.")
        else:
            messages.error(request, "Файл не загружен. Проверьте выбранный файл и его размер.")
    return redirect("documents:incoming_correspondence_detail", pk=record.pk)


@login_required
def memo_correspondence_create(request):
    if request.method == "POST":
        record = get_object_or_404(
            CorrespondenceRecord,
            pk=request.POST.get("reservation_id"),
            kind=CorrespondenceRecord.MEMO,
            status=CorrespondenceRecord.RESERVED,
            created_by=request.user,
        )
        form = MemoCorrespondenceForm(request.POST, request.FILES, instance=record)
        if form.is_valid():
            signed_file = form.cleaned_data.get("signed_file")
            record = form.save(commit=False)
            record.registration_number = record.build_registration_number()
            if record.draft_file:
                attach_generated_memo_template(record)
            if signed_file:
                record.signed_original_name = signed_file.name
            record.status = CorrespondenceRecord.REGISTERED
            record.registered_at = timezone.now()
            record.save()
            messages.success(request, f"Служебная записка {record.registration_number} зарегистрирована.")
            return redirect("documents:memo_correspondence_detail", pk=record.pk)
    else:
        record = reserve_correspondence_number(request.user, CorrespondenceRecord.MEMO)
        form = MemoCorrespondenceForm(instance=record)

    return render(
        request,
        "documents/memo_correspondence_form.html",
        {
            "record": record,
            "form": form,
        },
    )


@login_required
def memo_template_download(request, pk):
    if request.method != "POST":
        return redirect("documents:memo_correspondence_create")

    record = get_object_or_404(
        CorrespondenceRecord,
        pk=pk,
        kind=CorrespondenceRecord.MEMO,
        status=CorrespondenceRecord.RESERVED,
        created_by=request.user,
    )
    department = CorrespondenceDepartment.objects.filter(
        pk=request.POST.get("department"),
        is_active=True,
    ).first()
    if not department:
        return JsonResponse({"error": "Сначала выберите подразделение."}, status=400)
    subject = request.POST.get("subject", "").strip() or record.subject.strip()
    if not subject:
        return JsonResponse({"error": "Сначала заполните поле «Наименование»."}, status=400)
    addressee_person = request.POST.get("addressee_person", "").strip() or record.addressee_person.strip()
    if not addressee_person:
        return JsonResponse({"error": "Сначала заполните поле «Кому адресовано»."}, status=400)
    registration_date = parse_date(request.POST.get("registration_date", "")) or record.registration_date
    if not registration_date:
        return JsonResponse({"error": "Сначала укажите дату служебной записки."}, status=400)

    record.department = department
    record.registration_date = registration_date
    record.subject = subject
    record.addressee_person = addressee_person
    try:
        payload, file_name = attach_generated_memo_template(record)
    except (FileNotFoundError, ValueError) as exc:
        return JsonResponse({"error": str(exc)}, status=500)
    return FileResponse(BytesIO(payload), as_attachment=True, filename=file_name)


@login_required
def memo_correspondence_detail(request, pk):
    record = get_object_or_404(
        CorrespondenceRecord.objects.select_related(
            "department",
            "executor",
            "executor__userprofile",
            "created_by",
            "created_by__userprofile",
        ),
        pk=pk,
        kind=CorrespondenceRecord.MEMO,
        status=CorrespondenceRecord.REGISTERED,
    )
    can_update = request.user.is_superuser or request.user in {record.created_by, record.executor}
    return render(
        request,
        "documents/memo_correspondence_detail.html",
        {
            "record": record,
            "signed_file_form": SignedCorrespondenceFileForm(instance=record),
            "can_update": can_update,
        },
    )


@login_required
def memo_signed_file_upload(request, pk):
    record = get_object_or_404(
        CorrespondenceRecord,
        pk=pk,
        kind=CorrespondenceRecord.MEMO,
        status=CorrespondenceRecord.REGISTERED,
    )
    if not (request.user.is_superuser or request.user in {record.created_by, record.executor}):
        messages.error(request, "Заменить подписанный документ может только регистратор или исполнитель.")
        return redirect("documents:memo_correspondence_detail", pk=record.pk)
    if request.method == "POST":
        previous_file_name = record.signed_file.name if record.signed_file else ""
        file_storage = record.signed_file.storage
        form = SignedCorrespondenceFileForm(request.POST, request.FILES, instance=record)
        if form.is_valid():
            uploaded_file = form.cleaned_data["signed_file"]
            record = form.save(commit=False)
            record.signed_original_name = uploaded_file.name
            record.save(update_fields=["signed_file", "signed_original_name", "updated_at"])
            if previous_file_name and previous_file_name != record.signed_file.name:
                file_storage.delete(previous_file_name)
            messages.success(request, "Подписанный документ прикреплен.")
        else:
            messages.error(request, "Файл не загружен. Проверьте выбранный файл и его размер.")
    return redirect("documents:memo_correspondence_detail", pk=record.pk)


@login_required
def outgoing_correspondence_create(request):
    if request.method == "POST":
        record = get_object_or_404(
            CorrespondenceRecord,
            pk=request.POST.get("reservation_id"),
            kind=CorrespondenceRecord.OUTGOING,
            status=CorrespondenceRecord.RESERVED,
            created_by=request.user,
        )
        previous_number = record.registration_number
        form = OutgoingCorrespondenceForm(request.POST, request.FILES, instance=record)
        if form.is_valid():
            signed_file = form.cleaned_data.get("signed_file")
            record = form.save(commit=False)
            record.registration_number = record.build_registration_number()
            if record.draft_file and previous_number != record.registration_number:
                attach_generated_outgoing_template(record)
            if signed_file:
                record.signed_original_name = signed_file.name
            record.status = CorrespondenceRecord.REGISTERED
            record.registered_at = timezone.now()
            record.save()
            messages.success(request, f"Исходящее письмо {record.registration_number} зарегистрировано.")
            return redirect("documents:outgoing_correspondence_detail", pk=record.pk)
    else:
        record = reserve_correspondence_number(request.user, CorrespondenceRecord.OUTGOING)
        form = OutgoingCorrespondenceForm(instance=record)

    return render(
        request,
        "documents/outgoing_correspondence_form.html",
        {
            "record": record,
            "form": form,
        },
    )


@login_required
def outgoing_template_download(request, pk):
    if request.method != "POST":
        return redirect("documents:outgoing_correspondence_create")

    record = get_object_or_404(
        CorrespondenceRecord,
        pk=pk,
        kind=CorrespondenceRecord.OUTGOING,
        status=CorrespondenceRecord.RESERVED,
        created_by=request.user,
    )
    department = CorrespondenceDepartment.objects.filter(
        pk=request.POST.get("department"),
        is_active=True,
    ).first()
    if not department:
        return JsonResponse({"error": "Сначала выберите подразделение."}, status=400)
    subject = request.POST.get("subject", "").strip() or record.subject.strip()
    if not subject:
        return JsonResponse({"error": "Сначала заполните поле «Наименование»."}, status=400)
    addressee = request.POST.get("addressee", "").strip() or record.addressee.strip()
    if not addressee:
        return JsonResponse({"error": "Сначала заполните поле «Адресат»."}, status=400)
    addressee_person = request.POST.get("addressee_person", "").strip() or record.addressee_person.strip()
    if not addressee_person:
        return JsonResponse({"error": "Сначала заполните поле «Кому»."}, status=400)

    record.department = department
    record.subject = subject
    record.addressee = addressee
    record.addressee_person = addressee_person
    try:
        payload, file_name = attach_generated_outgoing_template(record)
    except (FileNotFoundError, ValueError) as exc:
        return JsonResponse({"error": str(exc)}, status=500)
    return FileResponse(BytesIO(payload), as_attachment=True, filename=file_name)


@login_required
def outgoing_correspondence_detail(request, pk):
    record = get_object_or_404(
        CorrespondenceRecord.objects.select_related(
            "department",
            "executor",
            "executor__userprofile",
            "created_by",
            "created_by__userprofile",
            "reply_to",
        ).prefetch_related("linked_incoming_records"),
        pk=pk,
        kind=CorrespondenceRecord.OUTGOING,
        status=CorrespondenceRecord.REGISTERED,
    )
    can_update = request.user.is_superuser or request.user in {record.created_by, record.executor}
    return render(
        request,
        "documents/outgoing_correspondence_detail.html",
        {
            "record": record,
            "signed_file_form": SignedCorrespondenceFileForm(instance=record),
            "can_update": can_update,
        },
    )


@login_required
def outgoing_signed_file_upload(request, pk):
    record = get_object_or_404(
        CorrespondenceRecord,
        pk=pk,
        kind=CorrespondenceRecord.OUTGOING,
        status=CorrespondenceRecord.REGISTERED,
    )
    if not (request.user.is_superuser or request.user in {record.created_by, record.executor}):
        messages.error(request, "Заменить подписанный документ может только регистратор или исполнитель.")
        return redirect("documents:outgoing_correspondence_detail", pk=record.pk)
    if request.method == "POST":
        previous_file_name = record.signed_file.name if record.signed_file else ""
        file_storage = record.signed_file.storage
        form = SignedCorrespondenceFileForm(request.POST, request.FILES, instance=record)
        if form.is_valid():
            uploaded_file = form.cleaned_data["signed_file"]
            record = form.save(commit=False)
            record.signed_original_name = uploaded_file.name
            record.save(update_fields=["signed_file", "signed_original_name", "updated_at"])
            if previous_file_name and previous_file_name != record.signed_file.name:
                file_storage.delete(previous_file_name)
            messages.success(request, "Подписанный документ прикреплен.")
        else:
            messages.error(request, "Файл не загружен. Проверьте выбранный файл и его размер.")
    return redirect("documents:outgoing_correspondence_detail", pk=record.pk)


@login_required
def correspondence_file_download(request, pk, file_kind):
    record = get_object_or_404(
        CorrespondenceRecord,
        pk=pk,
        status=CorrespondenceRecord.REGISTERED,
    )
    if file_kind == "draft":
        stored_file = record.draft_file
        file_name = record.draft_original_name
    elif file_kind == "signed":
        stored_file = record.signed_file
        file_name = record.signed_original_name
    elif file_kind == "incoming":
        stored_file = record.incoming_file
        file_name = record.incoming_original_name
    else:
        raise Http404("Файл не найден.")
    if not stored_file:
        raise Http404("Файл не прикреплен.")
    try:
        return FileResponse(stored_file.open("rb"), as_attachment=True, filename=file_name)
    except FileNotFoundError as exc:
        raise Http404("Файл не найден на диске сервера.") from exc


@login_required
def my_documents(request):
    documents = visible_documents_for(request.user).filter(is_deleted=False)
    form = DocumentSearchForm(request.GET or None)
    if form.is_valid():
        query = form.cleaned_data.get("query")
        status = form.cleaned_data.get("status")
        if query:
            documents = documents.filter(
                Q(title__icontains=query)
                | Q(system_number__icontains=query)
                | Q(internal_number__icontains=query)
                | Q(counterparty__icontains=query)
            )
        if status:
            documents = documents.filter(status=status)
    return render(request, "documents/document_list.html", {"documents": documents, "form": form, "title": "Мои документы"})


@login_required
def approval_inbox(request):
    tasks = ApprovalTask.objects.select_related(
        "document",
        "document__document_type",
        "document__author",
        "document__responsible",
        "document__author__userprofile",
        "document__responsible__userprofile",
        "approver",
        "approver__userprofile",
        "step",
    ).prefetch_related(
        "document__approval_tasks",
        "document__approval_tasks__approver",
        "document__approval_tasks__approver__userprofile",
        "document__approval_tasks__step",
    ).filter(
        approver=request.user,
        status=ApprovalTask.PENDING,
    )
    only_overdue = request.GET.get("only_overdue")
    if only_overdue:
        tasks = tasks.filter(due_date__lt=timezone.localdate())
    overdue_count = tasks.filter(due_date__lt=timezone.localdate()).count()
    today_count = tasks.filter(due_date=timezone.localdate()).count()
    return render(
        request,
        "documents/approval_inbox.html",
        {
            "tasks": tasks,
            "only_overdue": only_overdue,
            "overdue_count": overdue_count,
            "today_count": today_count,
        },
    )


@login_required
def notification_open(request, pk):
    notification = get_object_or_404(Notification, pk=pk, recipient=request.user)
    if not notification.is_read:
        notification.is_read = True
        notification.read_at = timezone.now()
        notification.save(update_fields=["is_read", "read_at", "updated_at"])
    return redirect(notification.link_url or "documents:approval_inbox")


@login_required
def all_documents(request):
    documents = visible_documents_for(request.user).filter(is_deleted=False)
    form = DocumentSearchForm(request.GET or None)
    if form.is_valid():
        query = form.cleaned_data.get("query")
        status = form.cleaned_data.get("status")
        if query:
            documents = documents.filter(
                Q(title__icontains=query)
                | Q(system_number__icontains=query)
                | Q(internal_number__icontains=query)
                | Q(counterparty__icontains=query)
            )
        if status:
            documents = documents.filter(status=status)
    return render(request, "documents/document_list.html", {"documents": documents, "form": form, "title": "Журнал документов"})


@login_required
def archive(request):
    documents = visible_documents_for(request.user).filter(status=Document.ARCHIVED, is_deleted=False)
    return render(request, "documents/document_list.html", {"documents": documents, "title": "Архив документов"})


@login_required
def document_detail(request, pk):
    document = get_object_or_404(
        visible_documents_for(request.user).prefetch_related(
            "approval_tasks",
            "approval_tasks__approver",
            "approval_tasks__approver__userprofile",
            "approval_tasks__configured_approver",
            "approval_tasks__step",
            "comments",
            "comments__author",
            "comments__author__userprofile",
            "auditlog_set",
            "auditlog_set__user",
            "auditlog_set__user__userprofile",
            "revision_requests",
            "revision_requests__requested_by",
            "revision_requests__requested_by__userprofile",
            "revision_requests__resolved_by",
            "revision_requests__resolved_by__userprofile",
            "revision_requests__approval_task",
        ),
        pk=pk,
    )
    comment_form = CommentForm()
    attachment_form = AttachmentForm()
    revision_form = RevisionCorrectionForm()
    open_revision_requests = list(
        document.revision_requests.filter(status=RevisionRequest.OPEN).order_by("created_at", "id")
    )
    resolved_revision_requests = list(
        document.revision_requests.filter(status=RevisionRequest.RESOLVED).order_by("-resolved_at", "-id")
    )
    user_task = document.approval_tasks.filter(approver=request.user, status=ApprovalTask.PENDING).first()
    can_work_on_revision = document.status == Document.RETURNED and (
        request.user.is_superuser or document.responsible_id == request.user.id
    )
    can_edit_document = request.user.is_superuser or (
        document.status == Document.DRAFT and document.author_id == request.user.id
    ) or (
        document.status == Document.RETURNED and document.responsible_id == request.user.id
    )
    can_manage_attachments = can_edit_document
    parallel_revision_form = None
    parallel_revision_items = []
    if document.approval_route_type == ApprovalRoute.PARALLEL and open_revision_requests:
        parallel_revision_form = ParallelRevisionCorrectionForm(revision_requests=open_revision_requests)
        parallel_revision_items = [
            {
                "revision_request": revision_request,
                "field": parallel_revision_form[f"correction_{revision_request.pk}"],
            }
            for revision_request in open_revision_requests
        ]
    action_form = ApprovalActionForm()
    return_form = ReturnForRevisionForm()
    delegate_form = DelegateForm()
    log_action(request.user, document, AuditLog.VIEW, "Просмотр карточки документа.", request)
    return render(
        request,
        "documents/document_detail.html",
        {
            "document": document,
            "comment_form": comment_form,
            "attachment_form": attachment_form,
            "revision_form": revision_form,
            "open_revision_requests": open_revision_requests,
            "resolved_revision_requests": resolved_revision_requests,
            "parallel_revision_form": parallel_revision_form,
            "parallel_revision_items": parallel_revision_items,
            "user_task": user_task,
            "can_work_on_revision": can_work_on_revision,
            "can_edit_document": can_edit_document,
            "can_manage_attachments": can_manage_attachments,
            "action_form": action_form,
            "return_form": return_form,
            "delegate_form": delegate_form,
        },
    )


@login_required
def document_create(request):
    selected_type_id = request.POST.get("document_type") or request.GET.get("document_type")
    custom_fields = CustomFieldDefinition.objects.none()
    if selected_type_id:
        custom_fields = CustomFieldDefinition.objects.filter(document_type_id=selected_type_id, is_active=True)

    if request.method == "POST":
        form = DocumentForm(request.POST, custom_field_definitions=custom_fields)
        if form.is_valid():
            document = form.save(commit=False)
            document.author = request.user
            if not document.responsible:
                document.responsible = request.user
            document.save()
            save_configured_approvers(document, request)
            log_action(request.user, document, AuditLog.CREATE, "Документ создан.", request)
            messages.success(request, f"Документ {document.system_number} создан.")
            return redirect("documents:detail", pk=document.pk)
    else:
        initial = {}
        if selected_type_id:
            initial["document_type"] = selected_type_id
        form = DocumentForm(initial=initial, custom_field_definitions=custom_fields)
    if selected_type_id:
        form.fields["document_type"].widget = HiddenInput()
    return render(request, "documents/document_form.html", document_form_context(form, "Создание документа", selected_type_id))


@login_required
def document_edit(request, pk):
    document = get_object_or_404(visible_documents_for(request.user), pk=pk)
    if document.status not in [Document.DRAFT, Document.RETURNED] and not request.user.is_superuser:
        messages.error(request, "Редактировать можно только черновик или документ, возвращенный на доработку.")
        return redirect("documents:detail", pk=document.pk)
    if document.status == Document.RETURNED and not request.user.is_superuser and document.responsible_id != request.user.id:
        messages.error(request, "Редактировать документ на доработке может только ответственный пользователь.")
        return redirect("documents:detail", pk=document.pk)
    if document.status == Document.DRAFT and not request.user.is_superuser and document.author_id != request.user.id:
        messages.error(request, "Редактировать черновик может только инициатор документа.")
        return redirect("documents:detail", pk=document.pk)
    custom_fields = document.document_type.custom_fields.filter(is_active=True)
    if request.method == "POST":
        form = DocumentForm(request.POST, instance=document, custom_field_definitions=custom_fields)
        if form.is_valid():
            document = form.save()
            save_configured_approvers(document, request)
            log_action(request.user, document, AuditLog.UPDATE, "Документ изменен.", request)
            messages.success(request, "Изменения сохранены.")
            return redirect("documents:detail", pk=document.pk)
    else:
        form = DocumentForm(instance=document, custom_field_definitions=custom_fields)
    return render(
        request,
        "documents/document_form.html",
        document_form_context(form, "Редактирование документа", document.document_type_id, document),
    )


@login_required
def submit_for_approval(request, pk):
    document = get_object_or_404(visible_documents_for(request.user), pk=pk)
    if request.method == "POST":
        if document.status == Document.RETURNED:
            messages.error(request, "Для повторной отправки документа на согласование используйте блок доработки.")
            return redirect("documents:detail", pk=document.pk)
        try:
            start_approval(document, request.user, request)
            messages.success(request, "Документ отправлен на согласование.")
        except ValueError as exc:
            messages.error(request, str(exc))
    return redirect("documents:detail", pk=document.pk)


@login_required
def resubmit_after_revision(request, pk):
    document = get_object_or_404(visible_documents_for(request.user), pk=pk, status=Document.RETURNED)
    if not request.user.is_superuser and document.responsible_id != request.user.id:
        messages.error(request, "Повторно отправить документ может только ответственный пользователь.")
        return redirect("documents:detail", pk=document.pk)

    if request.method == "POST":
        if document.approval_route_type == ApprovalRoute.PARALLEL:
            revision_requests = list(
                document.revision_requests.select_related("requested_by", "requested_by__userprofile")
                .filter(status=RevisionRequest.OPEN)
                .order_by("created_at", "id")
            )
            form = ParallelRevisionCorrectionForm(request.POST, revision_requests=revision_requests)
            if form.is_valid():
                try:
                    resubmit_parallel_approval(
                        document,
                        request.user,
                        form.corrections_by_request(),
                        request,
                    )
                    messages.success(
                        request,
                        "Создана новая версия. Повторное согласование направлено только участникам, оставившим замечания.",
                    )
                except ValueError as exc:
                    messages.error(request, str(exc))
            else:
                messages.error(request, "Опишите внесенные корректировки по каждому замечанию.")
            return redirect("documents:detail", pk=document.pk)

        form = RevisionCorrectionForm(request.POST)
        if form.is_valid():
            corrections = form.cleaned_data["corrections"]
            document.version += 1
            document.save(update_fields=["version", "updated_at"])
            DocumentComment.objects.create(
                document=document,
                author=request.user,
                text=f"Ответственным пользователем внесены правки. Версия документа: {document.version}.\n\nКорректировки: {corrections}",
            )
            log_action(
                request.user,
                document,
                AuditLog.UPDATE,
                f"Внесены корректировки по возврату на доработку. Документ переведен в версию {document.version}.",
                request,
            )
            try:
                start_approval(document, request.user, request)
                messages.success(request, "Корректировки сохранены, документ повторно отправлен на согласование.")
            except ValueError as exc:
                messages.error(request, str(exc))
            return redirect("documents:detail", pk=document.pk)
        messages.error(request, "Укажите внесенные корректировки.")
    return redirect("documents:detail", pk=document.pk)


@login_required
def upload_attachment(request, pk):
    document = get_object_or_404(visible_documents_for(request.user), pk=pk)
    if request.method == "POST":
        can_upload = request.user.is_superuser or (
            document.status == Document.DRAFT and document.author_id == request.user.id
        ) or (
            document.status == Document.RETURNED and document.responsible_id == request.user.id
        )
        if not can_upload:
            messages.error(request, "Нет прав на загрузку вложения для этого документа.")
            return redirect("documents:detail", pk=document.pk)
        form = AttachmentForm(request.POST, request.FILES)
        if form.is_valid():
            uploaded_file = form.cleaned_data["file"]
            file_hash = hashlib.sha256()
            for chunk in uploaded_file.chunks():
                file_hash.update(chunk)
            uploaded_file.seek(0)
            attachment = form.save(commit=False)
            attachment.document = document
            attachment.uploaded_by = request.user
            attachment.original_name = uploaded_file.name
            attachment.size = uploaded_file.size
            attachment.content_hash = file_hash.hexdigest()
            attachment.save()
            log_action(request.user, document, AuditLog.UPDATE, f"Загружен файл {attachment.original_name}.", request)
            messages.success(request, "Файл загружен.")
        else:
            messages.error(request, "Файл не загружен. Проверьте размер и формат.")
    return redirect("documents:detail", pk=document.pk)


@login_required
def download_attachment(request, pk, attachment_id):
    document = get_object_or_404(visible_documents_for(request.user), pk=pk)
    attachment = get_object_or_404(Attachment, pk=attachment_id, document=document)
    if not attachment.file:
        raise Http404("Attachment file not found.")
    try:
        return FileResponse(attachment.file.open("rb"), as_attachment=True, filename=attachment.original_name)
    except FileNotFoundError as exc:
        raise Http404("Attachment file not found.") from exc


@login_required
def delete_attachment(request, pk, attachment_id):
    document = get_object_or_404(visible_documents_for(request.user), pk=pk)
    attachment = get_object_or_404(Attachment, pk=attachment_id, document=document)
    can_delete = request.user.is_superuser or (
        document.status == Document.DRAFT and document.author_id == request.user.id
    ) or (
        document.status == Document.RETURNED and document.responsible_id == request.user.id
    )
    if not can_delete:
        messages.error(request, "Нет прав на удаление вложения.")
        return redirect("documents:detail", pk=document.pk)
    if request.method == "POST":
        original_name = attachment.original_name
        if attachment.file:
            attachment.file.delete(save=False)
        attachment.delete()
        log_action(request.user, document, AuditLog.DELETE, f"Удалено вложение {original_name}.", request)
        messages.success(request, "Вложение удалено.")
    return redirect("documents:detail", pk=document.pk)


@login_required
def add_comment(request, pk):
    document = get_object_or_404(visible_documents_for(request.user), pk=pk)
    if request.method == "POST":
        form = CommentForm(request.POST)
        if form.is_valid():
            comment = form.save(commit=False)
            comment.document = document
            comment.author = request.user
            comment.save()
            log_action(request.user, document, AuditLog.UPDATE, "Добавлен комментарий.", request)
            recipients = {document.author, document.responsible}
            recipients.update(task.approver for task in document.approval_tasks.all())
            recipients.discard(None)
            recipients.discard(request.user)
            for recipient in recipients:
                create_notification(
                    recipient,
                    document,
                    Notification.COMMENT_ADDED,
                    f"К документу {document.system_number} добавлен комментарий",
                    comment.text,
                )
    return redirect("documents:detail", pk=document.pk)


@login_required
def approval_action(request, task_id, action):
    task = get_object_or_404(ApprovalTask, pk=task_id, approver=request.user, status=ApprovalTask.PENDING)
    if request.method != "POST":
        return redirect("documents:detail", pk=task.document_id)

    if action == "approve":
        form = ApprovalActionForm(request.POST)
        if form.is_valid():
            approve_task(task, request.user, form.cleaned_data["comment"], request)
            messages.success(request, "Документ согласован.")
    elif action == "reject":
        form = ApprovalActionForm(request.POST)
        if form.is_valid():
            reject_task(task, request.user, form.cleaned_data["comment"], request)
            messages.success(request, "Документ отклонен.")
    elif action == "return":
        form = ReturnForRevisionForm(request.POST)
        if form.is_valid():
            return_for_revision(task, request.user, form.cleaned_data["responsible"], form.cleaned_data["comment"], request)
            messages.success(request, "Документ возвращен на доработку.")
    elif action == "delegate":
        form = DelegateForm(request.POST)
        if form.is_valid():
            delegate_task(task, request.user, form.cleaned_data["delegated_to"], form.cleaned_data["comment"], request)
            messages.success(request, "Согласование делегировано.")
    return redirect("documents:detail", pk=task.document_id)


@login_required
def soft_delete_document(request, pk):
    document = get_object_or_404(visible_documents_for(request.user), pk=pk)
    if not request.user.is_superuser and not request.user.has_perm("documents.soft_delete_document"):
        messages.error(request, "Нет прав на удаление документа.")
        return redirect("documents:detail", pk=document.pk)
    if request.method == "POST":
        document.is_deleted = True
        document.save(update_fields=["is_deleted", "updated_at"])
        log_action(request.user, document, AuditLog.DELETE, "Документ помечен на удаление.", request)
        messages.success(request, "Документ помечен на удаление.")
        return redirect("documents:my_documents")
    return redirect("documents:detail", pk=document.pk)


@login_required
def reports(request):
    documents = visible_documents_for(request.user).filter(is_deleted=False)
    period_created = documents.values("document_type__name").annotate(total=Count("id")).order_by("document_type__name")
    pending_documents = documents.filter(status=Document.ON_APPROVAL).count()
    overdue_tasks = ApprovalTask.objects.select_related("document", "approver", "approver__userprofile").filter(
        document__in=documents,
        status=ApprovalTask.PENDING,
        due_date__lt=timezone.localdate(),
    )
    context = {
        "total_documents": documents.count(),
        "period_created": period_created,
        "pending_documents": pending_documents,
        "overdue_tasks": overdue_tasks,
        "approval_history": ApprovalTask.objects.select_related("document", "approver", "approver__userprofile").filter(document__in=documents).exclude(status=ApprovalTask.PENDING)[:50],
        "archive_count": documents.filter(status=Document.ARCHIVED).count(),
    }
    return render(request, "documents/reports.html", context)

# Create your views here.
