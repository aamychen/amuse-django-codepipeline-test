# Generated by Django 2.0.8 on 2018-10-02 12:00

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('releases', '0070_metdata_language_override_sort_order'),
        ('contenttollgate', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='DeliveredRelease',
            fields=[],
            options={'proxy': True, 'indexes': []},
            bases=('releases.release',),
        )
    ]