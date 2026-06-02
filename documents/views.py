import hashlib

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.forms import HiddenInput
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import (
    ApprovalActionForm,
    AttachmentForm,
    CommentForm,
    DelegateForm,
    DocumentForm,
    DocumentSearchForm,
    ReturnForRevisionForm,
)
from .models import ApprovalTask, Attachment, AuditLog, CustomFieldDefinition, Document, DocumentType
from .services import (
    approve_task,
    delegate_task,
    log_action,
    reject_task,
    return_for_revision,
    start_approval,
)


def visible_documents_for(user):
    queryset = Document.objects.select_related("document_type", "author", "responsible", "department", "route")
    if user.is_superuser or user.has_perm("documents.view_all_documents"):
        return queryset
    return queryset.filter(
        Q(author=user)
        | Q(responsible=user)
        | Q(approval_tasks__approver=user)
    ).distinct()


@login_required
def dashboard(request):
    my_documents = visible_documents_for(request.user).filter(is_deleted=False)
    approval_tasks = ApprovalTask.objects.filter(approver=request.user, status=ApprovalTask.PENDING)
    context = {
        "created_count": my_documents.count(),
        "pending_count": approval_tasks.count(),
        "overdue_count": approval_tasks.filter(due_date__lt=timezone.localdate()).count(),
        "recent_documents": my_documents[:5],
        "approval_tasks": approval_tasks.select_related("document", "document__document_type")[:5],
    }
    return render(request, "documents/dashboard.html", context)


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
    tasks = ApprovalTask.objects.select_related("document", "document__document_type").filter(
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
    document = get_object_or_404(visible_documents_for(request.user), pk=pk)
    comment_form = CommentForm()
    attachment_form = AttachmentForm()
    user_task = document.approval_tasks.filter(approver=request.user, status=ApprovalTask.PENDING).first()
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
            "user_task": user_task,
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
    return render(
        request,
        "documents/document_form.html",
        {
            "form": form,
            "title": "Создание документа",
            "document_types": DocumentType.objects.filter(is_active=True).order_by("name"),
            "selected_type_id": str(selected_type_id or ""),
        },
    )


@login_required
def document_edit(request, pk):
    document = get_object_or_404(visible_documents_for(request.user), pk=pk)
    if document.status not in [Document.DRAFT, Document.RETURNED] and not request.user.is_superuser:
        messages.error(request, "Редактировать можно только черновик или документ, возвращенный на доработку.")
        return redirect("documents:detail", pk=document.pk)
    custom_fields = document.document_type.custom_fields.filter(is_active=True)
    if request.method == "POST":
        form = DocumentForm(request.POST, instance=document, custom_field_definitions=custom_fields)
        if form.is_valid():
            document = form.save()
            log_action(request.user, document, AuditLog.UPDATE, "Документ изменен.", request)
            messages.success(request, "Изменения сохранены.")
            return redirect("documents:detail", pk=document.pk)
    else:
        form = DocumentForm(instance=document, custom_field_definitions=custom_fields)
    return render(request, "documents/document_form.html", {"form": form, "title": "Редактирование документа"})


@login_required
def submit_for_approval(request, pk):
    document = get_object_or_404(visible_documents_for(request.user), pk=pk)
    if request.method == "POST":
        try:
            start_approval(document, request.user, request)
            messages.success(request, "Документ отправлен на согласование.")
        except ValueError as exc:
            messages.error(request, str(exc))
    return redirect("documents:detail", pk=document.pk)


@login_required
def upload_attachment(request, pk):
    document = get_object_or_404(visible_documents_for(request.user), pk=pk)
    if request.method == "POST":
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
    overdue_tasks = ApprovalTask.objects.select_related("document", "approver").filter(
        document__in=documents,
        status=ApprovalTask.PENDING,
        due_date__lt=timezone.localdate(),
    )
    context = {
        "total_documents": documents.count(),
        "period_created": period_created,
        "pending_documents": pending_documents,
        "overdue_tasks": overdue_tasks,
        "approval_history": ApprovalTask.objects.select_related("document", "approver").filter(document__in=documents).exclude(status=ApprovalTask.PENDING)[:50],
        "archive_count": documents.filter(status=Document.ARCHIVED).count(),
    }
    return render(request, "documents/reports.html", context)

# Create your views here.
