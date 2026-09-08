from django.db import migrations
from django.db.models import F


def enable_existing_parallel_revisions(apps, schema_editor):
    Document = apps.get_model("documents", "Document")
    RevisionRequest = apps.get_model("documents", "RevisionRequest")
    alias = schema_editor.connection.alias
    open_document_ids = (
        RevisionRequest.objects.using(alias)
        .filter(status="open")
        .order_by()
        .values("document_id")
    )
    documents = Document.objects.using(alias).filter(
        approval_route_type="parallel",
        status="on_approval",
        is_deleted=False,
        pk__in=open_document_ids,
    )
    documents.filter(responsible_id__isnull=True).update(responsible_id=F("author_id"))
    documents.update(status="returned")


class Migration(migrations.Migration):
    dependencies = [
        ("documents", "0015_attachment_versions"),
    ]

    # Reversing code must not undo decisions made after this data repair.
    operations = [
        migrations.RunPython(enable_existing_parallel_revisions, migrations.RunPython.noop),
    ]
