# Generated by Django 2.0.13 on 2020-08-12 08:17

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('releases', '0100_adding_fuzzy_name_field_to_blacklisted_artist_name_model'),
    ]

    operations = [
        migrations.AddField(
            model_name='royaltysplit',
            name='is_locked',
            field=models.BooleanField(default=False),
        ),
    ]