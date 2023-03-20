# -*- coding: utf-8 -*-
# Generated by Django 1.9.3 on 2017-02-17 07:54
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [('releases', '0020_store_order')]

    operations = [
        migrations.AlterUniqueTogether(
            name='songdailydownloadstats', unique_together=set([])
        ),
        migrations.RemoveField(model_name='songdailydownloadstats', name='isrc'),
        migrations.AlterUniqueTogether(
            name='songdailystreamstats', unique_together=set([])
        ),
        migrations.RemoveField(model_name='songdailystreamstats', name='isrc'),
        migrations.DeleteModel(name='SongDailyDownloadStats'),
        migrations.DeleteModel(name='SongDailyStreamStats'),
    ]
