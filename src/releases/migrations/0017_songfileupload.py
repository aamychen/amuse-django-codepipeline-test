# -*- coding: utf-8 -*-
# Generated by Django 1.9.3 on 2017-01-05 06:56
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion

# from releases.models import SongFileUpload


def migrate_uploads(apps, schema_editor):
    SongFileUpload = apps.get_model('releases.SongFileUpload')
    for upload in SongFileUpload.objects.all():
        upload.filename = upload.file.name
        upload.status = 1 if upload.file and len(upload.file.name) else 0
        upload.save()


def reverse_uploads(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [('releases', '0016_song_filename')]

    operations = [
        migrations.AlterField(
            model_name='songfileupload',
            name='song',
            field=models.OneToOneField(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='upload',
                to='releases.Song',
            ),
        ),
        migrations.AddField(
            model_name='songfileupload',
            name='status',
            field=models.PositiveSmallIntegerField(
                choices=[(0, 'Created'), (1, 'Completed')], default=0
            ),
        ),
        migrations.AddField(
            model_name='songfileupload',
            name='filename',
            field=models.CharField(db_index=True, max_length=64, null=True),
        ),
        migrations.RunPython(migrate_uploads, reverse_uploads),
    ]