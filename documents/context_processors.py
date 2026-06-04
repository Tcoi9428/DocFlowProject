from .models import ApprovalTask, Notification


def notification_context(request):
    if not request.user.is_authenticated:
        return {}

    unread_notifications = Notification.objects.filter(recipient=request.user, is_read=False)
    approval_badge_count = ApprovalTask.objects.filter(
        approver=request.user,
        status=ApprovalTask.PENDING,
    ).count()

    return {
        "unread_notifications_count": unread_notifications.count(),
        "approval_badge_count": approval_badge_count,
        "recent_notifications": Notification.objects.filter(recipient=request.user).select_related("document")[:10],
    }
