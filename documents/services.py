from datetime import timedelta

from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

from .models import ApprovalRoute, ApprovalTask, AuditLog, Document


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


@transaction.atomic
def start_approval(document, user, request=None):
    route = document.route or ApprovalRoute.objects.filter(
        document_type=document.document_type,
        is_default=True,
        is_active=True,
    ).first()
    if not route:
        raise ValueError("Для документа не выбран и не настроен маршрут согласования.")

    document.route = route
    document.status = Document.ON_APPROVAL
    document.save(update_fields=["route", "status", "updated_at"])
    document.approval_tasks.all().delete()

    steps = list(route.steps.select_related("approver").order_by("order"))
    if not steps:
        raise ValueError("В маршруте согласования нет этапов.")

    if route.route_type == ApprovalRoute.PARALLEL:
        active_steps = steps
    else:
        active_steps = [steps[0]]

    for step in active_steps:
        task = ApprovalTask.objects.create(
            document=document,
            step=step,
            approver=step.approver,
            due_date=timezone.localdate() + timedelta(days=step.due_days),
        )
        notify_user(
            step.approver,
            f"Документ {document.system_number} поступил на согласование",
            f"Необходимо согласовать документ: {document.title}. Срок: {task.due_date}.",
        )

    log_action(user, document, AuditLog.UPDATE, f"Документ отправлен на согласование по маршруту '{route}'.", request)


@transaction.atomic
def approve_task(task, user, comment="", request=None):
    task.status = ApprovalTask.APPROVED
    task.comment = comment
    task.completed_at = timezone.now()
    task.save(update_fields=["status", "comment", "completed_at", "updated_at"])
    log_action(user, task.document, AuditLog.APPROVE, f"Согласовано: {comment}".strip(), request)

    document = task.document
    route = document.route

    if route.route_type == ApprovalRoute.PARALLEL:
        if not document.approval_tasks.filter(status=ApprovalTask.PENDING).exists():
            document.status = Document.APPROVED
            document.save(update_fields=["status", "updated_at"])
            notify_user(document.author, f"Документ {document.system_number} согласован", document.title)
        return

    next_step = route.steps.filter(order__gt=task.step.order).order_by("order").first()
    if next_step:
        next_task = ApprovalTask.objects.create(
            document=document,
            step=next_step,
            approver=next_step.approver,
            due_date=timezone.localdate() + timedelta(days=next_step.due_days),
        )
        notify_user(
            next_step.approver,
            f"Документ {document.system_number} поступил на согласование",
            f"Необходимо согласовать документ: {document.title}. Срок: {next_task.due_date}.",
        )
    else:
        document.status = Document.APPROVED
        document.save(update_fields=["status", "updated_at"])
        notify_user(document.author, f"Документ {document.system_number} согласован", document.title)


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
    notify_user(document.author, f"Документ {document.system_number} отклонен", comment or document.title)


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
    notify_user(document.responsible, f"Документ {document.system_number} возвращен на доработку", comment)


@transaction.atomic
def delegate_task(task, user, delegated_to, comment="", request=None):
    old_approver = task.approver
    task.status = ApprovalTask.DELEGATED
    task.delegated_to = delegated_to
    task.comment = comment
    task.completed_at = timezone.now()
    task.save(update_fields=["status", "delegated_to", "comment", "completed_at", "updated_at"])
    ApprovalTask.objects.create(
        document=task.document,
        step=task.step,
        approver=delegated_to,
        due_date=task.due_date,
    )
    log_action(
        user,
        task.document,
        AuditLog.DELEGATE,
        f"Согласование делегировано от {old_approver} к {delegated_to}. {comment}".strip(),
        request,
    )
    notify_user(delegated_to, f"Вам делегировано согласование {task.document.system_number}", task.document.title)
