from django.db import migrations


def restore_legacy_parallel_remarks(apps, schema_editor):
    Document = apps.get_model("documents", "Document")
    ApprovalTask = apps.get_model("documents", "ApprovalTask")
    RevisionRequest = apps.get_model("documents", "RevisionRequest")
    alias = schema_editor.connection.alias

    documents = Document.objects.using(alias).filter(
        approval_route_type="parallel", status="returned", is_deleted=False
    )
    for document in documents:
        if RevisionRequest.objects.using(alias).filter(
            document_id=document.pk, status="open"
        ).exists():
            continue

        tasks = ApprovalTask.objects.using(alias).filter(
            document_id=document.pk,
            document_version=document.version,
            status__in=("returned", "rejected"),
            revision_request__isnull=True,
        )
        for task in tasks:
            comment = task.comment.strip()
            if not comment:
                continue
            remark = RevisionRequest.objects.using(alias).create(
                document_id=document.pk,
                approval_task_id=task.pk,
                requested_by_id=task.approver_id,
                document_version=task.document_version,
                comment=comment,
                status="open",
            )
            if task.completed_at:
                RevisionRequest.objects.using(alias).filter(pk=remark.pk).update(
                    created_at=task.completed_at
                )


class Migration(migrations.Migration):
    dependencies = [
        ("documents", "0016_enable_existing_parallel_revisions"),
    ]

    operations = [
        migrations.RunPython(restore_legacy_parallel_remarks, migrations.RunPython.noop),
    ]
