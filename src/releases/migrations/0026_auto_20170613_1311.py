# -*- coding: utf-8 -*-
# Generated by Django 1.9.3 on 2017-06-13 13:11
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [('releases', '0025_auto_20170608_1031')]

    operations = [
        migrations.RenameField(
            model_name='release', old_name='rejection_flags', new_name='error_flags'
        ),
        migrations.RenameField(
            model_name='song', old_name='rejection_flags', new_name='error_flags'
        ),
    ]
