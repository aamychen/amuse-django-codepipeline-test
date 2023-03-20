# Generated by Django 2.2.25 on 2022-02-08 08:12

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('countries', '0008_country_internal_numeric_code'),
    ]

    operations = [
        migrations.AddField(
            model_name='country',
            name='is_hyperwallet_enabled',
            field=models.BooleanField(
                default=True, help_text='Hyperwallet supports payments for this country'
            ),
        ),
    ]
