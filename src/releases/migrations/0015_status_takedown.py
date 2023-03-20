# -*- coding: utf-8 -*-
# Generated by Django 1.9.3 on 2016-12-06 09:05
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('releases', '0014_release_status')]

    operations = [
        migrations.AlterField(
            model_name='release',
            name='status',
            field=models.SmallIntegerField(
                choices=[
                    (1, 'Submitted'),
                    (2, 'Incomplete'),
                    (3, 'Pending Approval'),
                    (4, 'Approved'),
                    (5, 'Rejected'),
                    (6, 'Delivered'),
                    (7, 'Undeliverable'),
                    (8, 'Released'),
                    (9, 'Abandoned'),
                    (10, 'Taken down'),
                ],
                default=1,
            ),
        )
    ]