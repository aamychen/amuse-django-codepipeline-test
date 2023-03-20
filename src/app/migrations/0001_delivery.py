# -*- coding: utf-8 -*-
# Generated by Django 1.9.3 on 2018-01-29 18:28
from __future__ import unicode_literals

from django.conf import settings
import django.contrib.postgres.fields
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ('releases', '0039_genre_apple_code'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Delivery',
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
                ('batch_job', models.CharField(max_length=120)),
                ('store', models.PositiveSmallIntegerField(choices=[(3, 'APPLE')])),
                (
                    'status',
                    models.PositiveSmallIntegerField(
                        choices=[(0, 'SUBMITTED'), (1, 'SUCCEEDED'), (99, 'FAILED')],
                        default=0,
                    ),
                ),
                (
                    'errors',
                    django.contrib.postgres.fields.ArrayField(
                        base_field=models.CharField(max_length=512),
                        default=[],
                        size=None,
                    ),
                ),
                (
                    'warnings',
                    django.contrib.postgres.fields.ArrayField(
                        base_field=models.CharField(max_length=512),
                        default=[],
                        size=None,
                    ),
                ),
                ('date_created', models.DateTimeField(auto_now_add=True)),
                ('date_updated', models.DateTimeField(auto_now=True)),
                (
                    'release',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to='releases.Release',
                    ),
                ),
                (
                    'user',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={'db_table': 'delivery'},
        )
    ]
