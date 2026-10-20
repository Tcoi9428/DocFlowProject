from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("documents", "0018_final_director_approval"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="is_general_director",
            field=models.BooleanField(default=False, verbose_name="Генеральный директор"),
        ),
    ]
