# Generated by Django 3.1.4 on 2021-04-11 12:40

from django.conf import settings
from django.db import migrations, models


def change_user_type(apps, schema_editor):
    ContentType = apps.get_model("contenttypes", "ContentType")
    ct = ContentType.objects.filter(app_label="auth", model="user").first()
    if ct:
        ct.app_label = "user"
        ct.save()


class Migration(migrations.Migration):

    dependencies = [
        ("user", "0002_loginas"),
    ]

    operations = [
        migrations.RunPython(change_user_type),
        migrations.RemoveField(
            model_name="userprofile",
            name="user",
        ),
        migrations.AlterModelOptions(
            name="user",
            options={"verbose_name": "user", "verbose_name_plural": "users"},
        ),
        migrations.AddField(
            model_name="user",
            name="contacts",
            field=models.ManyToManyField(
                related_name="_user_contacts_+", to=settings.AUTH_USER_MODEL
            ),
        ),
        migrations.AlterModelTable(
            name="user",
            table=None,
        ),
        migrations.DeleteModel(
            name="UserProfile",
        ),
    ]
