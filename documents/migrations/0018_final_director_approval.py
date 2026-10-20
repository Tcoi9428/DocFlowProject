from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("documents", "0017_restore_legacy_parallel_remarks"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="document",
            name="requires_general_director_approval",
            field=models.BooleanField(default=False, verbose_name="Требуется согласование генерального директора"),
        ),
        migrations.AddField(
            model_name="document",
            name="general_director",
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                related_name="documents_for_final_approval", to=settings.AUTH_USER_MODEL,
                verbose_name="Генеральный директор",
            ),
        ),
        migrations.AddField(
            model_name="approvaltask",
            name="is_final_director_approval",
            field=models.BooleanField(default=False, verbose_name="Финальное согласование директора"),
        ),
    ]
