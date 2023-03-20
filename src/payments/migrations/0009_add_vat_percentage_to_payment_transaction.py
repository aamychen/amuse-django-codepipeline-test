# Generated by Django 2.0.10 on 2020-01-07 12:34

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('payments', '0008_plan_required_for_subscription')]

    operations = [
        migrations.AddField(
            model_name='paymenttransaction',
            name='vat_percentage',
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                help_text='VAT percentage of amount',
                max_digits=5,
            ),
            preserve_default=False,
        )
    ]