from django.urls import path

from . import views

app_name = "documents"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("password-reset/", views.password_reset_request, name="password_reset_request"),
    path("password-reset/confirm/", views.password_reset_confirm, name="password_reset_confirm"),
    path("password-reset/admin/<int:pk>/", views.password_reset_admin_detail, name="password_reset_admin_detail"),
    path("my/", views.my_documents, name="my_documents"),
    path("inbox/", views.approval_inbox, name="approval_inbox"),
    path("all/", views.all_documents, name="all_documents"),
    path("archive/", views.archive, name="archive"),
    path("correspondence/", views.correspondence_registry, name="correspondence"),
    path("correspondence/<str:section>/", views.correspondence_registry, name="correspondence_section"),
    path("correspondence/incoming/new/", views.incoming_correspondence_create, name="incoming_correspondence_create"),
    path(
        "correspondence/incoming/<int:pk>/",
        views.incoming_correspondence_detail,
        name="incoming_correspondence_detail",
    ),
    path(
        "correspondence/incoming/<int:pk>/file/",
        views.incoming_correspondence_file_upload,
        name="incoming_correspondence_file_upload",
    ),
    path("correspondence/outgoing/new/", views.outgoing_correspondence_create, name="outgoing_correspondence_create"),
    path(
        "correspondence/outgoing/<int:pk>/",
        views.outgoing_correspondence_detail,
        name="outgoing_correspondence_detail",
    ),
    path(
        "correspondence/outgoing/<int:pk>/template/",
        views.outgoing_template_download,
        name="outgoing_template_download",
    ),
    path(
        "correspondence/outgoing/<int:pk>/signed-file/",
        views.outgoing_signed_file_upload,
        name="outgoing_signed_file_upload",
    ),
    path(
        "correspondence/<int:pk>/files/<str:file_kind>/",
        views.correspondence_file_download,
        name="correspondence_file_download",
    ),
    path("reports/", views.reports, name="reports"),
    path("notifications/<int:pk>/", views.notification_open, name="notification_open"),
    path("documents/new/", views.document_create, name="create"),
    path("documents/<int:pk>/", views.document_detail, name="detail"),
    path("documents/<int:pk>/edit/", views.document_edit, name="edit"),
    path("documents/<int:pk>/submit/", views.submit_for_approval, name="submit"),
    path("documents/<int:pk>/resubmit/", views.resubmit_after_revision, name="resubmit_after_revision"),
    path("documents/<int:pk>/attachments/", views.upload_attachment, name="upload_attachment"),
    path("documents/<int:pk>/attachments/<int:attachment_id>/download/", views.download_attachment, name="download_attachment"),
    path("documents/<int:pk>/attachments/<int:attachment_id>/delete/", views.delete_attachment, name="delete_attachment"),
    path("documents/<int:pk>/comments/", views.add_comment, name="add_comment"),
    path("documents/<int:pk>/delete/", views.soft_delete_document, name="soft_delete"),
    path("tasks/<int:task_id>/<str:action>/", views.approval_action, name="approval_action"),
]
