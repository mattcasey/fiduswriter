# -*- coding: utf-8 -*-
# Generated by Django 1.10.4 on 2017-03-26 09:04
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('ojs', '0006_auto_20170325_0553'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='submission',
            unique_together=set([]),
        ),
        migrations.AlterUniqueTogether(
            name='submissionrevision',
            unique_together=set([]),
        ),
    ]
