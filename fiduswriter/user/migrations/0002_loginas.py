# Generated by Django 3.1.4 on 2021-01-05 12:30

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("user", "0001_squashed_0003_auto_20151226_1110"),
    ]

    operations = [
        migrations.CreateModel(
            name="LoginAs",
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
            ],
            options={
                "permissions": (
                    ("can_login_as", "Can login as another user"),
                ),
                "managed": False,
                "default_permissions": (),
            },
        ),
    ]
