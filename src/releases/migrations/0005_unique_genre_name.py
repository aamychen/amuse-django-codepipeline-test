# -*- coding: utf-8 -*-
# Generated by Django 1.9.3 on 2016-07-07 09:02
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('releases', '0004_songfile_bucket')]

    operations = [
        migrations.AlterField(
            model_name='genre',
            name='name',
            field=models.CharField(max_length=120, unique=True),
        )
    ]