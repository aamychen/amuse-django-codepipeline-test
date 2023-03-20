# -*- coding: utf-8 -*-
# Generated by Django 1.9.3 on 2018-05-16 12:50
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('releases', '0050_song_filename_default')]

    operations = [
        migrations.AddField(
            model_name='song', name='cover_licensor', field=models.TextField(blank=True)
        ),
        migrations.AddField(
            model_name='song',
            name='youtube_content_id',
            field=models.PositiveSmallIntegerField(
                choices=[(0, 'none'), (1, 'block'), (2, 'monetize')], default=0
            ),
        ),
    ]