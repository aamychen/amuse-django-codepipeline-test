# -*- coding: utf-8 -*-
# Generated by Django 1.9.3 on 2018-06-25 09:38
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('codes', '0003_status_orphaned')]

    operations = [
        migrations.AddField(
            model_name='isrc',
            name='licensed',
            field=models.BooleanField(
                default=False,
                help_text='Denotes whether this ISRC has been licened by Amuse.',
            ),
        )
    ]
