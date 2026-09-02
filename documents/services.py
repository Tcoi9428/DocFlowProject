import logging
from datetime import timedelta
from html import escape

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import F, Q
from django.utils.html import linebreaks
from django.utils import timezone

from .models import (
    ApprovalRoute,
    ApprovalTask,
    AuditLog,
    Document,
    DocumentComment,
    EmailDelivery,
    Notification,
    RevisionRequest,
)
from .user_display import user_identity


logger = logging.getLogger(__name__)


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


def absolute_docflow_url(link_url):
    if not link_url:
        return settings.DOCFLOW_BASE_URL
    if link_url.startswith(("http://", "https://")):
        return link_url
    return f"{settings.DOCFLOW_BASE_URL}/{link_url.lstrip('/')}"


def queue_notification_email(notification, subject=None, message=None):
    recipient_email = (notification.recipient.email or "").strip()
    if not recipient_email:
        return None

    delivery = EmailDelivery.objects.create(
        notification=notification,
        recipient_email=recipient_email,
        subject=subject or notification.title,
        message=message or notification.message,
        link_url=absolute_docflow_url(notification.link_url),
    )
    if settings.DOCFLOW_EMAIL_SEND_IMMEDIATELY:
        transaction.on_commit(lambda delivery_id=delivery.pk: deliver_email(delivery_id))
    return delivery


def queue_notification_email_by_id(notification_id, subject=None, message=None):
    try:
        notification = Notification.objects.select_related("recipient").get(pk=notification_id)
    except Notification.DoesNotExist:
        logger.warning("Notification %s was deleted before email queueing", notification_id)
        return None
    return queue_notification_email(notification, subject, message)


def _email_bodies(delivery):
    text_body = delivery.message.strip()
    if delivery.link_url:
        text_body = f"{text_body}\n\nОткрыть документ в DocFlow:\n{delivery.link_url}"

    escaped_subject = escape(delivery.subject)
    escaped_message = linebreaks(escape(delivery.message))
    link_html = ""
    if delivery.link_url:
        escaped_link = escape(delivery.link_url, quote=True)
        link_html = (
            '<p style="margin:24px 0 0;">'
            f'<a href="{escaped_link}" style="display:inline-block;padding:11px 18px;'
            'background:#f58220;color:#ffffff;text-decoration:none;border-radius:4px;">'
            "Открыть документ</a></p>"
        )
    html_body = (
        '<div style="font-family:Arial,sans-serif;max-width:640px;color:#1f2933;line-height:1.5;">'
        f'<h2 style="font-size:20px;margin:0 0 16px;">{escaped_subject}</h2>'
        f"{escaped_message}{link_html}"
        '<p style="margin-top:28px;color:#667085;font-size:12px;">'
        "Письмо отправлено автоматически системой DocFlow. Отвечать на него не нужно.</p></div>"
    )
    return text_body, html_body


def deliver_email(delivery_id):
    delivery = EmailDelivery.objects.get(pk=delivery_id)
    if delivery.status == EmailDelivery.SENT:
        return True

    delivery.attempts += 1
    delivery.save(update_fields=["attempts", "updated_at"])
    text_body, html_body = _email_bodies(delivery)

    try:
        sent_count = send_mail(
            delivery.subject,
            text_body,
            None,
            [delivery.recipient_email],
            fail_silently=False,
            html_message=html_body,
        )
        if sent_count != 1:
            raise RuntimeError("Почтовый сервер не подтвердил отправку письма.")
    except Exception as exc:
        retry_minutes = min(5 * (2 ** max(delivery.attempts - 1, 0)), 60)
        delivery.status = EmailDelivery.FAILED
        delivery.last_error = str(exc)[:4000]
        delivery.next_attempt_at = timezone.now() + timedelta(minutes=retry_minutes)
        delivery.save(update_fields=["status", "last_error", "next_attempt_at", "updated_at"])
        logger.exception("Email delivery %s failed", delivery.pk)
        return False

    delivery.status = EmailDelivery.SENT
    delivery.last_error = ""
    delivery.next_attempt_at = None
    delivery.sent_at = timezone.now()
    delivery.save(
        update_fields=["status", "last_error", "next_attempt_at", "sent_at", "updated_at"]
    )
    return True


def process_email_queue(limit=50):
    now = timezone.now()
    deliveries = EmailDelivery.objects.filter(
        Q(status=EmailDelivery.PENDING) | Q(status=EmailDelivery.FAILED),
        attempts__lt=settings.DOCFLOW_EMAIL_MAX_ATTEMPTS,
    ).filter(Q(next_attempt_at__isnull=True) | Q(next_attempt_at__lte=now)).order_by("created_at")[:limit]

    sent = 0
    failed = 0
    for delivery in deliveries:
        if deliver_email(delivery.pk):
            sent += 1
        else:
            failed += 1
    return sent, failed


def notify_approval_deadline(task):
    due_date_text = task.due_date.strftime("%d.%m.%Y")
    create_notification(
        task.approver,
        task.document,
        Notification.APPROVAL_REMINDER,
        f"Истекает срок согласования {task.document.system_number}",
        f"Документ необходимо согласовать не позднее {due_date_text}.",
        f"/documents/{task.document_id}/",
        email_subject=f"Напоминание: документ {task.document.system_number} ожидает согласования",
        email_message=(
            f"Необходимо согласовать документ {task.document.system_number} "
            f"не позднее {due_date_text}."
        ),
    )
    task.reminder_sent_at = timezone.now()
    task.reminder_due_date = task.due_date
    task.save(update_fields=["reminder_sent_at", "reminder_due_date", "updated_at"])


def process_approval_reminders():
    deadline = timezone.localdate() + timedelta(days=1)
    tasks = ApprovalTask.objects.select_related("document", "approver").filter(
        status=ApprovalTask.PENDING,
        due_date__isnull=False,
        due_date__lte=deadline,
    ).filter(Q(reminder_due_date__isnull=True) | ~Q(reminder_due_date=F("due_date")))

    count = 0
    for task in tasks:
        notify_approval_deadline(task)
        count += 1
    return count


def create_notification(
    recipient,
    document,
    notification_type,
    title,
    message,
    link_url="",
    email_subject=None,
    email_message=None,
):
    if not recipient:
        return None
    notification = Notification.objects.create(
        recipient=recipient,
        document=document,
        notification_type=notification_type,
        title=title,
        message=message,
        link_url=link_url or f"/documents/{document.id}/",
    )
    if notification.recipient.email:
        transaction.on_commit(
            lambda notification_id=notification.pk: queue_notification_email_by_id(
                notification_id,
                email_subject,
                email_message,
            ),
            robust=True,
        )
    return notification


def notify_approval_required(user, document):
    create_notification(
        user,
        document,
        Notification.APPROVAL_REQUIRED,
        f"Требуется согласование {document.system_number}",
        f"Документ '{document.title}' поступил вам на согласование.",
        f"/documents/{document.id}/",
        email_subject=f"Документ {document.system_number} поступил на согласование",
        email_message=f"Необходимо согласовать документ: {document.title}.",
    )


def notify_status_change(user, document, title, message):
    create_notification(user, document, Notification.STATUS_CHANGED, title, message)


def _document_route_type(document):
    return document.approval_route_type or (
        document.route.route_type if document.route_id else ApprovalRoute.SEQUENTIAL
    )


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
        active_approvers = (
            configured_approvers
            if _document_route_type(document) == ApprovalRoute.PARALLEL
            else [configured_approvers[0]]
        )
        for item in active_approvers:
            ApprovalTask.objects.create(
                document=document,
                configured_approver=item,
                approver=item.approver,
                document_version=document.version,
                due_date=timezone.localdate() + timedelta(days=item.due_days),
            )
            notify_approval_required(item.approver, document)
        log_action(user, document, AuditLog.UPDATE, "Документ отправлен на пользовательское согласование.", request)
        return

    steps = list(route.steps.select_related("approver").order_by("order"))
    if not steps:
        raise ValueError("В маршруте согласования нет этапов.")

    active_steps = steps if _document_route_type(document) == ApprovalRoute.PARALLEL else [steps[0]]
    for step in active_steps:
        task = ApprovalTask.objects.create(
            document=document,
            step=step,
            approver=step.approver,
            document_version=document.version,
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
    if route is None and task.step_id:
        route = task.step.route
    approver_name = user_identity(user)

    log_action(user, document, AuditLog.APPROVE, f"Согласовано: {comment}".strip(), request)
    notify_status_change(
        document.author,
        document,
        f"Документ {document.system_number}: этап согласован",
        f"Документ согласован пользователем {approver_name}.",
    )

    if _document_route_type(document) == ApprovalRoute.PARALLEL:
        _complete_parallel_cycle(document)
        return

    configured_approver = task.configured_approver
    if configured_approver is None:
        configured_approver = document.configured_approvers.filter(
            approver_id=task.approver_id
        ).order_by("order").first()

    if configured_approver:
        next_approver = document.configured_approvers.filter(
            order__gt=configured_approver.order
        ).order_by("order").first()
        if next_approver:
            ApprovalTask.objects.create(
                document=document,
                configured_approver=next_approver,
                approver=next_approver.approver,
                document_version=document.version,
                due_date=timezone.localdate() + timedelta(days=next_approver.due_days),
            )
            notify_approval_required(next_approver.approver, document)
        else:
            _finish_document_approval(document)
        return

    if route and task.step_id:
        next_step = route.steps.filter(order__gt=task.step.order).order_by("order").first()
        if next_step:
            ApprovalTask.objects.create(
                document=document,
                step=next_step,
                approver=next_step.approver,
                document_version=document.version,
                due_date=timezone.localdate() + timedelta(days=next_step.due_days),
            )
            notify_approval_required(next_step.approver, document)
        else:
            _finish_document_approval(document)
        return

    logger.warning(
        "Approval task %s has no route, step, or configured approver; using pending tasks as fallback",
        task.pk,
    )
    if not document.approval_tasks.filter(status=ApprovalTask.PENDING).exists():
        _finish_document_approval(document)


def _complete_parallel_cycle(document):
    document = Document.objects.select_for_update().get(pk=document.pk)
    current_tasks = document.approval_tasks.filter(document_version=document.version)
    if current_tasks.filter(status=ApprovalTask.PENDING).exists():
        return
    if document.revision_requests.filter(
        document_version=document.version,
        status=RevisionRequest.OPEN,
    ).exists():
        document.status = Document.RETURNED
        document.save(update_fields=["status", "updated_at"])
        return
    _finish_document_approval(document)


def _finish_document_approval(document):
    document.status = Document.APPROVED
    document.save(update_fields=["status", "updated_at"])
    recipients = [document.author]
    if document.responsible_id and document.responsible_id != document.author_id:
        recipients.append(document.responsible)
    for recipient in recipients:
        notify_status_change(
            recipient,
            document,
            f"Документ {document.system_number} согласован всеми участниками",
            "Документ согласован всеми участниками маршрута.",
        )


def _record_parallel_revision(task, user, responsible, comment, request, task_status):
    task.status = task_status
    task.comment = comment
    task.completed_at = timezone.now()
    task.save(update_fields=["status", "comment", "completed_at", "updated_at"])

    document = task.document
    if responsible:
        document.responsible = responsible
    elif not document.responsible_id:
        document.responsible = document.author
    document.revision_requested_by = user
    document.revision_requested_at = timezone.now()
    document.revision_comment = comment
    document.save(
        update_fields=[
            "responsible",
            "revision_requested_by",
            "revision_requested_at",
            "revision_comment",
            "updated_at",
        ]
    )
    RevisionRequest.objects.update_or_create(
        approval_task=task,
        defaults={
            "document": document,
            "requested_by": user,
            "document_version": task.document_version,
            "comment": comment,
            "status": RevisionRequest.OPEN,
            "resolution_comment": "",
            "resolved_by": None,
            "resolved_at": None,
            "resolved_in_version": None,
        },
    )
    DocumentComment.objects.create(
        document=document,
        author=user,
        text=(
            f"Замечание к версии {task.document_version}. Документ возвращен на доработку.\n\n"
            f"Комментарий: {comment or '-'}"
        ),
    )
    action = AuditLog.REJECT if task_status == ApprovalTask.REJECTED else AuditLog.RETURN
    log_action(user, document, action, f"Замечание к версии {task.document_version}: {comment}".strip(), request)
    notify_status_change(
        document.responsible,
        document,
        f"Замечание к документу {document.system_number}",
        (
            f"Пользователь {user_identity(user)} вернул версию {task.document_version} на доработку. "
            f"Комментарий: {comment}"
        ),
    )
    _complete_parallel_cycle(document)


@transaction.atomic
def reject_task(task, user, comment="", request=None):
    if _document_route_type(task.document) == ApprovalRoute.PARALLEL:
        _record_parallel_revision(
            task,
            user,
            responsible=None,
            comment=comment,
            request=request,
            task_status=ApprovalTask.REJECTED,
        )
        return

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
    if _document_route_type(task.document) == ApprovalRoute.PARALLEL:
        _record_parallel_revision(
            task,
            user,
            responsible=responsible,
            comment=comment,
            request=request,
            task_status=ApprovalTask.RETURNED,
        )
        return

    task.status = ApprovalTask.RETURNED
    task.comment = comment
    task.completed_at = timezone.now()
    task.save(update_fields=["status", "comment", "completed_at", "updated_at"])
    document = task.document
    document.approval_tasks.filter(status=ApprovalTask.PENDING).exclude(pk=task.pk).update(
        status=ApprovalTask.RETURNED,
        completed_at=timezone.now(),
    )
    document.status = Document.RETURNED
    if responsible:
        document.responsible = responsible
    elif not document.responsible_id:
        document.responsible = document.author
    document.revision_requested_by = user
    document.revision_requested_at = timezone.now()
    document.revision_comment = comment
    document.save(update_fields=[
        "status",
        "responsible",
        "revision_requested_by",
        "revision_requested_at",
        "revision_comment",
        "updated_at",
    ])
    DocumentComment.objects.create(
        document=document,
        author=user,
        text=f"Документ возвращен на доработку.\n\nКомментарий: {comment or '-'}",
    )
    log_action(user, document, AuditLog.RETURN, f"Возвращено на доработку: {comment}".strip(), request)
    notify_status_change(
        document.responsible,
        document,
        f"Документ {document.system_number} отправлен на доработку",
        (
            f"Документ отправлен на доработку пользователем {user_identity(user)}. "
            f"Комментарий: {comment}"
            if comment
            else f"Документ отправлен на доработку пользователем {user_identity(user)}."
        ),
    )


@transaction.atomic
def resubmit_parallel_approval(document, user, corrections_by_request, request=None):
    document.refresh_from_db(fields=["status", "version", "approval_route_type"])
    if _document_route_type(document) != ApprovalRoute.PARALLEL:
        raise ValueError("Повторная параллельная отправка доступна только для параллельного маршрута.")
    if document.status != Document.RETURNED:
        raise ValueError("Документ еще не готов к повторной отправке.")

    revision_requests = list(
        document.revision_requests.select_for_update()
        .select_related(
            "approval_task",
            "approval_task__step",
            "approval_task__configured_approver",
            "approval_task__approver",
            "requested_by",
        )
        .filter(status=RevisionRequest.OPEN)
        .order_by("created_at", "id")
    )
    if not revision_requests:
        raise ValueError("Для документа нет открытых замечаний.")
    if set(corrections_by_request) != {item.pk for item in revision_requests}:
        raise ValueError("Необходимо описать корректировки по каждому замечанию.")

    participants = {document.author_id: document.author}
    if document.responsible_id:
        participants[document.responsible_id] = document.responsible
    for approval_task in document.approval_tasks.select_related("approver"):
        participants[approval_task.approver_id] = approval_task.approver

    document.version += 1
    document.status = Document.ON_APPROVAL
    document.revision_requested_by = None
    document.revision_requested_at = None
    document.revision_comment = ""
    document.save(
        update_fields=[
            "version",
            "status",
            "revision_requested_by",
            "revision_requested_at",
            "revision_comment",
            "updated_at",
        ]
    )

    correction_lines = []
    retry_tasks = []
    for revision_request in revision_requests:
        correction = corrections_by_request[revision_request.pk].strip()
        revision_request.status = RevisionRequest.RESOLVED
        revision_request.resolution_comment = correction
        revision_request.resolved_by = user
        revision_request.resolved_at = timezone.now()
        revision_request.resolved_in_version = document.version
        revision_request.save(
            update_fields=[
                "status",
                "resolution_comment",
                "resolved_by",
                "resolved_at",
                "resolved_in_version",
                "updated_at",
            ]
        )
        correction_lines.append(
            f"Замечание {user_identity(revision_request.requested_by)}: {revision_request.comment}\n"
            f"Корректировки: {correction}"
        )

        previous_task = revision_request.approval_task
        configured_approver = previous_task.configured_approver
        if configured_approver is None:
            configured_approver = document.configured_approvers.filter(
                approver_id=previous_task.approver_id
            ).order_by("order").first()
        due_days = 3
        if configured_approver:
            due_days = configured_approver.due_days
        elif previous_task.step_id:
            due_days = previous_task.step.due_days
        retry_tasks.append(
            ApprovalTask.objects.create(
                document=document,
                step=previous_task.step,
                configured_approver=configured_approver,
                approver=previous_task.approver,
                document_version=document.version,
                due_date=timezone.localdate() + timedelta(days=due_days),
            )
        )

    correction_summary = "\n\n".join(correction_lines)
    DocumentComment.objects.create(
        document=document,
        author=user,
        text=(
            f"Ответственным пользователем внесены правки. Версия документа: {document.version}.\n\n"
            f"{correction_summary}"
        ),
    )
    log_action(
        user,
        document,
        AuditLog.UPDATE,
        f"Замечания устранены. Создана версия {document.version}; повторное согласование направлено только авторам замечаний.",
        request,
    )

    for participant in participants.values():
        notify_status_change(
            participant,
            document,
            f"Документ {document.system_number} обновлен до версии {document.version}",
            f"Ответственный {user_identity(user)} внес корректировки.\n\n{correction_summary}",
        )
    for retry_task in retry_tasks:
        notify_approval_required(retry_task.approver, document)


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
        document_version=task.document_version,
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
