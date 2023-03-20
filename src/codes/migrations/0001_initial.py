# -*- coding: utf-8 -*-
# Generated by Django 1.9.3 on 2016-04-15 14:27
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='ISRC',
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
                ('code', models.CharField(max_length=32)),
                (
                    'status',
                    models.SmallIntegerField(
                        choices=[(0, 'Unused'), (1, 'Used')], default=0
                    ),
                ),
            ],
            options={'verbose_name': 'ISRC', 'verbose_name_plural': 'ISRC'},
        ),
        migrations.CreateModel(
            name='UPC',
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
                ('code', models.CharField(max_length=32)),
                (
                    'status',
                    models.SmallIntegerField(
                        choices=[(0, 'Unused'), (1, 'Used')], default=0
                    ),
                ),
            ],
            options={'verbose_name': 'UPC', 'verbose_name_plural': 'UPC'},
        ),
    ]
