# -*- coding: utf-8 -*-
# Generated by Django 1.9.12 on 2017-03-31 15:18
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("councilmatic_core", "0028_event_media_url"),
    ]

    operations = [
        migrations.AlterField(
            model_name="event",
            name="media_url",
            field=models.CharField(default=None, max_length=555, null=True),
        ),
    ]
