# -*- coding: utf-8 -*-
# Generated by Django 1.9.3 on 2018-05-15 05:26
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('releases', '0049_remove_release_countries')]

    operations = [
        migrations.AlterField(
            model_name='song',
            name='filename',
            field=models.CharField(blank=True, default='', max_length=255),
        )
    ]