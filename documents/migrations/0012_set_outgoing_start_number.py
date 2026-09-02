from django.db import migrations


def set_outgoing_start_number(apps, schema_editor):
    Sequence = apps.get_model("documents", "CorrespondenceSequence")
    Sequence.objects.filter(kind="outgoing", next_number__lt=657).update(next_number=657)


class Migration(migrations.Migration):

    dependencies = [
        ("documents", "0011_correspondence_registry"),
    ]

    operations = [
        migrations.RunPython(set_outgoing_start_number, migrations.RunPython.noop),
    ]
