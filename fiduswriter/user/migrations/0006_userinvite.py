# Generated by Django 3.1.4 on 2021-05-24 17:07

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ("user", "0005_delete_teammember"),
    ]

    operations = [
        migrations.CreateModel(
            name="UserInvite",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "key",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, unique=True
                    ),
                ),
                (
                    "email",
                    models.EmailField(
                        max_length=254, verbose_name="email address"
                    ),
                ),
                ("username", models.CharField(max_length=150)),
                (
                    "by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="invites_by",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
    ]
