# -*- coding: utf-8 -*-
# Generated by Django 1.9.3 on 2018-04-28 15:27
from __future__ import unicode_literals

from django.db import migrations, models


def migrate_countries(apps, schema_editor):
    Release = apps.get_model('releases', 'Release')
    Country = apps.get_model('countries', 'Country')
    for release in Release.objects.all():
        release.excluded_countries = Country.objects.exclude(
            code__in=release.countries.values_list('code', flat=True)
        )
        release.save()


def rollback_countries(apps, schema_editor):
    Release = apps.get_model('releases', 'Release')
    Country = apps.get_model('countries', 'Country')
    for release in Release.objects.all():
        release.countries = Country.objects.exclude(
            code__in=release.excluded_countries.values_list('code', flat=True)
        )
        release.save()


class Migration(migrations.Migration):
    dependencies = [
        ('countries', '0001_initial'),
        ('releases', '0047_contributor_role_str'),
    ]

    operations = [
        migrations.RenameField(
            model_name='release', old_name='stores', new_name='excluded_stores'
        ),
        migrations.AddField(
            model_name='release',
            name='excluded_countries',
            field=models.ManyToManyField(
                blank=True,
                help_text='This is the countries to <strong>exclude</strong> from delivery.',
                to='countries.Country',
            ),
        ),
        migrations.AlterField(
            model_name='release',
            name='countries',
            field=models.ManyToManyField(
                help_text='This is the countries to <strong>include</strong> in delivery.',
                related_name='included_countries',
                to='countries.Country',
            ),
        ),
        migrations.RunPython(migrate_countries, rollback_countries),
    ]
