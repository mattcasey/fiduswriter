# Generated by Django 3.1.4 on 2021-05-27 10:18

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("document", "0015_migrate_invites"),
    ]

    operations = [
        migrations.DeleteModel(
            name="AccessRightInvite",
        ),
    ]
