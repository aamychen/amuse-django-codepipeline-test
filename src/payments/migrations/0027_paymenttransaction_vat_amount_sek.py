# Generated by Django 2.1.15 on 2021-12-21 09:08

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('payments', '0026_add_introductory_payment_type')]

    operations = [
        migrations.AddField(
            model_name='historicalpaymenttransaction',
            name='vat_amount_sek',
            field=models.DecimalField(
                decimal_places=2,
                help_text='VAT part of amount (in SEK)',
                max_digits=8,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='paymenttransaction',
            name='vat_amount_sek',
            field=models.DecimalField(
                decimal_places=2,
                help_text='VAT part of amount (in SEK)',
                max_digits=8,
                null=True,
            ),
        ),
    ]
