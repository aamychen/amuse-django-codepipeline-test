# -*- coding: utf-8 -*-
# Generated by Django 1.9.3 on 2017-01-08 20:02
from __future__ import unicode_literals

from django.db import migrations


def migrate_name(apps, schema_editor):
    User = apps.get_model('users', 'User')
    for user in User.objects.all():
        if not user.first_name or user.last_name:
            names = user.name.split(maxsplit=1)
            user.first_name = names[0]
            user.last_name = names[1] if len(names) == 2 else names[0]
            user.save()


def reverse_migrate_name(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [('users', '0011_auto_20161213_2102')]

    operations = [
        migrations.RunPython(migrate_name, reverse_migrate_name),
        migrations.RemoveField(model_name='user', name='name'),
    ]
