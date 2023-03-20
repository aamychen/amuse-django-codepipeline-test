# Generated by Django 2.0.10 on 2019-11-20 14:50

from decimal import Decimal
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('countries', '0002_country_region_code')]

    operations = [
        migrations.AlterModelOptions(
            name='country', options={'verbose_name_plural': 'Countries'}
        ),
        migrations.AddField(
            model_name='country',
            name='is_adyen_enabled',
            field=models.BooleanField(
                default=False, help_text='Enable Adyen payments for this country'
            ),
        ),
        migrations.AddField(
            model_name='country',
            name='vat_percentage',
            field=models.DecimalField(
                decimal_places=4,
                default=Decimal('0.0'),
                help_text='VAT Percentage for this country, 0-1 (e.g. 10% = 0.1, 25% = 0.25)',
                max_digits=5,
            ),
        ),
    ]
