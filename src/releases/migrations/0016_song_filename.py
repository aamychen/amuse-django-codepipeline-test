# -*- coding: utf-8 -*-
# Generated by Django 1.9.3 on 2016-12-06 09:25
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('releases', '0015_status_takedown')]

    operations = [
        migrations.AddField(
            model_name='song',
            name='filename',
            field=models.CharField(blank=True, max_length=255, null=True),
        )
    ]
