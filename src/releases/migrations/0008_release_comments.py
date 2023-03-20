# -*- coding: utf-8 -*-
# Generated by Django 1.9.3 on 2016-08-22 09:41
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('releases', '0007_fuga_import_trends')]

    operations = [
        migrations.CreateModel(
            name='Comments',
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
                ('text', models.TextField()),
                (
                    'release',
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='comments',
                        to='releases.Release',
                    ),
                ),
            ],
        )
    ]