from django.urls import path

from . import views

app_name = "documents"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("my/", views.my_documents, name="my_documents"),
    path("inbox/", views.approval_inbox, name="approval_inbox"),
    path("all/", views.all_documents, name="all_documents"),
    path("archive/", views.archive, name="archive"),
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
