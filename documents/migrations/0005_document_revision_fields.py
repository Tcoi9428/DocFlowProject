from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("documents", "0004_notification"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="document",
            name="revision_comment",
            field=models.TextField(blank=True, verbose_name="Комментарий возврата на доработку"),
        ),
        migrations.AddField(
            model_name="document",
            name="revision_requested_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="Дата возврата на доработку"),
        ),
        migrations.AddField(
            model_name="document",
            name="revision_requested_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="revision_requested_documents",
                to=settings.AUTH_USER_MODEL,
                verbose_name="Кто вернул на доработку",
            ),
        ),
        migrations.AddField(
            model_name="document",
            name="version",
            field=models.PositiveIntegerField(default=1, verbose_name="Версия"),
        ),
    ]
