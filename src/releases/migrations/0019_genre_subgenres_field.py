# -*- coding: utf-8 -*-
# Generated by Django 1.9.3 on 2017-01-16 11:34
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('releases', '0018_remove_songfileupload_file')]

    operations = [
        migrations.AlterField(
            model_name='genre',
            name='parent',
            field=models.ForeignKey(
                null=True,
                blank=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='subgenres',
                to='releases.Genre',
            ),
        )
    ]
