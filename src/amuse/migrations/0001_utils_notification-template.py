# -*- coding: utf-8 -*-
# Generated by Django 1.9.3 on 2018-03-27 17:14
from __future__ import unicode_literals

import amuse.models.utils
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='NotificationTemplate',
            fields=[
                (
                    'id',
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name='ID',
                    ),
                ),
                ('data', amuse.models.utils.JSONTransformator()),
                ('name', models.CharField(max_length=240)),
            ],
            options={'db_table': 'notification_template'},
        )
    ]
