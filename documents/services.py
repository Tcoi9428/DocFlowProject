from datetime import timedelta

from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

from .models import ApprovalRoute, ApprovalTask, AuditLog, Document, Notification
from .user_display import user_identity


def log_action(user, document, action, message, request=None):
    ip_address = None
    if request:
        ip_address = request.META.get("HTTP_X_FORWARDED_FOR", request.META.get("REMOTE_ADDR", ""))
        if ip_address and "," in ip_address:
            ip_address = ip_address.split(",", 1)[0].strip()
    AuditLog.objects.create(
        user=user if user and user.is_authenticated else None,
        document=document,
        action=action,
        message=message,
        ip_address=ip_address or None,
    )


def notify_user(user, subject, message):
    if user.email:
        send_mail(subject, message, None, [user.email], fail_silently=True)


def create_notification(recipient, document, notification_type, title, message, link_url=""):
    if not recipient:
        return None
    return Notification.objects.create(
        recipient=recipient,
        document=document,
        notification_type=notification_type,
        title=title,
        message=message,
        link_url=link_url or f"/documents/{document.id}/",
    )


def notify_approval_required(user, document):
    notify_user(
        user,
        f"Документ {document.system_number} поступил на согласование",
        f"Необходимо согласовать документ: {document.title}.",
    )
    create_notification(
        user,
        document,
        Notification.APPROVAL_REQUIRED,
        f"Требуется согласование {document.system_number}",
        f"Документ '{document.title}' поступил вам на согласование.",
        f"/documents/{document.id}/",
    )


def notify_status_change(user, document, title, message):
    notify_user(user, title, message)
    create_notification(user, document, Notification.STATUS_CHANGED, title, message)


@transaction.atomic
def start_approval(document, user, request=None):
    route = document.route or ApprovalRoute.objects.filter(
        document_type=document.document_type,
        is_default=True,
        is_active=True,
    ).first()
    configured_approvers = list(document.configured_approvers.select_related("approver").order_by("order"))
    if not route and not configured_approvers:
        raise ValueError("Для документа не выбран и не настроен маршрут согласования.")

    if route:
        document.route = route
    document.status = Document.ON_APPROVAL
    document.save(update_fields=["route", "status", "updated_at"])
    document.approval_tasks.all().delete()

    if configured_approvers:
        active_approvers = configured_approvers if route and route.route_type == ApprovalRoute.PARALLEL else [configured_approvers[0]]
        for item in active_approvers:
            ApprovalTask.objects.create(
                document=document,
                configured_approver=item,
                approver=item.approver,
                due_date=timezone.localdate() + timedelta(days=item.due_days),
            )
            notify_approval_required(item.approver, document)
        log_action(user, document, AuditLog.UPDATE, "Документ отправлен на пользовательское согласование.", request)
        return

    steps = list(route.steps.select_related("approver").order_by("order"))
    if not steps:
        raise ValueError("В маршруте согласования нет этапов.")

    active_steps = steps if route.route_type == ApprovalRoute.PARALLEL else [steps[0]]
    for step in active_steps:
        task = ApprovalTask.objects.create(
            document=document,
            step=step,
            approver=step.approver,
            due_date=timezone.localdate() + timedelta(days=step.due_days),
        )
        notify_approval_required(step.approver, document)

    log_action(user, document, AuditLog.UPDATE, f"Документ отправлен на согласование по маршруту '{route}'.", request)


@transaction.atomic
def approve_task(task, user, comment="", request=None):
    task.status = ApprovalTask.APPROVED
    task.comment = comment
    task.completed_at = timezone.now()
    task.save(update_fields=["status", "comment", "completed_at", "updated_at"])
    document = task.document
    route = document.route
    approver_name = user_identity(user)

    log_action(user, document, AuditLog.APPROVE, f"Согласовано: {comment}".strip(), request)
    notify_status_change(
        document.author,
        document,
        f"Документ {document.system_number}: этап согласован",
        f"Документ согласован пользователем {approver_name}.",
    )

    if task.configured_approver_id:
        if route and route.route_type == ApprovalRoute.PARALLEL:
            if not document.approval_tasks.filter(status=ApprovalTask.PENDING).exists():
                _finish_document_approval(document)
            return

        next_approver = document.configured_approvers.filter(
            order__gt=task.configured_approver.order
        ).order_by("order").first()
        if next_approver:
            ApprovalTask.objects.create(
                document=document,
                configured_approver=next_approver,
                approver=next_approver.approver,
                due_date=timezone.localdate() + timedelta(days=next_approver.due_days),
            )
            notify_approval_required(next_approver.approver, document)
        else:
            _finish_document_approval(document)
        return

    if route.route_type == ApprovalRoute.PARALLEL:
        if not document.approval_tasks.filter(status=ApprovalTask.PENDING).exists():
            _finish_document_approval(document)
        return

    next_step = route.steps.filter(order__gt=task.step.order).order_by("order").first()
    if next_step:
        ApprovalTask.objects.create(
            document=document,
            step=next_step,
            approver=next_step.approver,
            due_date=timezone.localdate() + timedelta(days=next_step.due_days),
        )
        notify_approval_required(next_step.approver, document)
    else:
        _finish_document_approval(document)


def _finish_document_approval(document):
    document.status = Document.APPROVED
    document.save(update_fields=["status", "updated_at"])
    notify_status_change(
        document.author,
        document,
        f"Документ {document.system_number} согласован всеми участниками",
        "Документ согласован всеми участниками маршрута.",
    )


@transaction.atomic
def reject_task(task, user, comment="", request=None):
    task.status = ApprovalTask.REJECTED
    task.comment = comment
    task.completed_at = timezone.now()
    task.save(update_fields=["status", "comment", "completed_at", "updated_at"])
    document = task.document
    document.status = Document.REJECTED
    document.save(update_fields=["status", "updated_at"])
    log_action(user, document, AuditLog.REJECT, f"Отклонено: {comment}".strip(), request)
    notify_status_change(
        document.author,
        document,
        f"Документ {document.system_number} отклонен",
        comment or "Документ отклонен согласующим.",
    )


@transaction.atomic
def return_for_revision(task, user, responsible=None, comment="", request=None):
    task.status = ApprovalTask.RETURNED
    task.comment = comment
    task.completed_at = timezone.now()
    task.save(update_fields=["status", "comment", "completed_at", "updated_at"])
    document = task.document
    document.status = Document.RETURNED
    document.responsible = responsible or document.author
    document.save(update_fields=["status", "responsible", "updated_at"])
    log_action(user, document, AuditLog.RETURN, f"Возвращено на доработку: {comment}".strip(), request)
    notify_status_change(
        document.responsible,
        document,
        f"Документ {document.system_number} отправлен на доработку",
        comment or "Документ возвращен на доработку.",
    )


@transaction.atomic
def delegate_task(task, user, delegated_to, comment="", request=None):
    old_approver = task.approver
    old_approver_name = user_identity(old_approver)
    delegated_to_name = user_identity(delegated_to)
    task.status = ApprovalTask.DELEGATED
    task.delegated_to = delegated_to
    task.comment = comment
    task.completed_at = timezone.now()
    task.save(update_fields=["status", "delegated_to", "comment", "completed_at", "updated_at"])
    ApprovalTask.objects.create(
        document=task.document,
        step=task.step,
        configured_approver=task.configured_approver,
        approver=delegated_to,
        due_date=task.due_date,
    )
    log_action(
        user,
        task.document,
        AuditLog.DELEGATE,
        f"Согласование делегировано от {old_approver_name} к {delegated_to_name}. {comment}".strip(),
        request,
    )
    notify_approval_required(delegated_to, task.document)
