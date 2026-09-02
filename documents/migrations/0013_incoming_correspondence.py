import django.db.models.deletion
from django.db import migrations, models

import documents.models


class Migration(migrations.Migration):

    dependencies = [
        ("documents", "0012_set_outgoing_start_number"),
    ]

    operations = [
        migrations.AddField(
            model_name="correspondencerecord",
            name="incoming_file",
            field=models.FileField(
                blank=True,
                upload_to=documents.models.correspondence_upload_path,
                verbose_name="Входящее письмо",
            ),
        ),
        migrations.AddField(
            model_name="correspondencerecord",
            name="incoming_original_name",
            field=models.CharField(blank=True, max_length=255, verbose_name="Имя файла входящего письма"),
        ),
        migrations.AddField(
            model_name="correspondencerecord",
            name="related_document_number",
            field=models.CharField(
                blank=True,
                max_length=100,
                verbose_name="Номер связанного документа из старого реестра",
            ),
        ),
        migrations.AddField(
            model_name="correspondencerecord",
            name="related_outgoing",
            field=models.ForeignKey(
                blank=True,
                limit_choices_to={"kind": "outgoing", "status": "registered"},
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="linked_incoming_records",
                to="documents.correspondencerecord",
                verbose_name="Связанное исходящее письмо",
            ),
        ),
        migrations.AddField(
            model_name="correspondencerecord",
            name="resolution",
            field=models.TextField(blank=True, verbose_name="Резолюция"),
        ),
        migrations.AddField(
            model_name="correspondencerecord",
            name="sender",
            field=models.CharField(blank=True, max_length=250, verbose_name="Отправитель"),
        ),
    ]
