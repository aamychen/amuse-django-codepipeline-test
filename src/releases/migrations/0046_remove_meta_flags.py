# -*- coding: utf-8 -*-
# Generated by Django 1.9.3 on 2018-04-28 09:13
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('releases', '0045_add_explicit_origin')]

    operations = [migrations.RemoveField(model_name='song', name='meta_flags')]