# Generated by Django 2.0.13 on 2020-09-24 11:28

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('releases', '0103_remove_artist_from_releases'),
        ('contenttollgate', '0003_assignedpendingrelease_assignedpreparedrelease'),
    ]

    operations = [
        migrations.CreateModel(
            name='UrgentProRelease',
            fields=[],
            options={
                'proxy': True,
                'indexes': [],
            },
            bases=('releases.release',),
        ),
    ]
