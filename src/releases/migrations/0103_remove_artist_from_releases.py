# Generated by Django 2.0.13 on 2020-08-21 13:01

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [('releases', '0102_remove_releaseartist')]

    operations = [
        migrations.RemoveField(model_name='historicalrelease', name='artist'),
        migrations.RemoveField(model_name='release', name='artist'),
    ]
