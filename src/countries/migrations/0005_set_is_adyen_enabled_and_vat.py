from decimal import Decimal

from django.db import migrations, models


VAT_COUNTRIES = (
    (
        Decimal('0.0'),
        (
            'AU',
            'BR',
            'CA',
            'CN',
            'GH',
            'HK',
            'IN',
            'ID',
            'JP',
            'KE',
            'MY',
            'MX',
            'NZ',
            'NO',
            'PH',
            'RU',
            'SG',
            'KR',
            'CH',
            'TZ',
            'TH',
            'TR',
            'UG',
            'US',
            'VN',
        ),
    ),
    (Decimal('0.17'), ('LU',)),
    (Decimal('0.18'), ('MT',)),
    (Decimal('0.19'), ('CY', 'DE', 'RO')),
    (Decimal('0.20'), ('AT', 'BG', 'EE', 'FR', 'SK', 'GB')),
    (Decimal('0.21'), ('BE', 'CZ', 'LV', 'LT', 'NL', 'ES')),
    (Decimal('0.22'), ('IT', 'SI')),
    (Decimal('0.23'), ('IE', 'PL', 'PT')),
    (Decimal('0.24'), ('FI', 'EL')),
    (Decimal('0.25'), ('HR', 'DK', 'SE')),
    (Decimal('0.27'), ('HU',)),
)


def set_adyen_enabled_and_vat(apps, schema_editor):
    Country = apps.get_model("countries", "Country")
    for vat_percentage, countries in VAT_COUNTRIES:
        Country.objects.filter(code__in=countries).update(
            vat_percentage=vat_percentage, is_adyen_enabled=True
        )


def unset_adyen_enabled_and_vat(apps, schema_editor):
    Country = apps.get_model("countries", "Country")
    for vat_percentage, countries in VAT_COUNTRIES:
        Country.objects.filter(code__in=countries).update(
            vat_percentage=0, is_adyen_enabled=False
        )


class Migration(migrations.Migration):
    dependencies = [('countries', '0004_is_adyen_enabled_index')]

    operations = [
        migrations.RunPython(set_adyen_enabled_and_vat, unset_adyen_enabled_and_vat)
    ]
