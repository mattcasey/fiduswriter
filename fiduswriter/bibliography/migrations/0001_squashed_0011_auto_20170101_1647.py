# Generated by Django 1.11.13 on 2018-08-14 17:32
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    replaces = [
        ("bibliography", "0001_initial"),
        ("bibliography", "0002_entry_bib_type"),
        ("bibliography", "0003_auto_20161113_1534"),
        ("bibliography", "0004_remove_entry_entry_type"),
        ("bibliography", "0005_auto_20161115_0310"),
        ("bibliography", "0006_auto_20161122_0304"),
        ("bibliography", "0007_auto_20161201_0209"),
        ("bibliography", "0008_auto_20161201_0545"),
        ("bibliography", "0009_auto_20161207_0130"),
        ("bibliography", "0010_auto_20161207_0133"),
        ("bibliography", "0011_auto_20170101_1647"),
    ]

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Entry",
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
                ("entry_key", models.CharField(max_length=64)),
                ("entry_cat", models.CharField(default="", max_length=255)),
                ("last_modified", models.DateTimeField(auto_now=True)),
                ("fields", models.TextField(default="{}")),
                (
                    "entry_owner",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                ("bib_type", models.CharField(default="", max_length=30)),
            ],
        ),
        migrations.CreateModel(
            name="EntryCategory",
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
                ("category_title", models.CharField(max_length=100)),
                (
                    "category_owner",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name_plural": "Entry categories",
            },
        ),
        migrations.AlterUniqueTogether(
            name="entry",
            unique_together=set([]),
        ),
        migrations.AlterField(
            model_name="entry",
            name="entry_cat",
            field=models.TextField(default="[]"),
        ),
    ]
