# -*- coding: utf-8 -*-
# Generated by Django 1.9.3 on 2017-01-05 07:11
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [('releases', '0017_songfileupload')]

    operations = [migrations.RemoveField(model_name='songfileupload', name='file')]
