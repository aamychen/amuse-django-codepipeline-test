# Generated by Django 2.0.10 on 2019-11-18 12:12

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('countries', '0003_payment_info_on_country')]

    operations = [
        migrations.AlterField(
            model_name='country',
            name='is_adyen_enabled',
            field=models.BooleanField(
                db_index=True,
                default=False,
                help_text='Enable Adyen payments for this country',
            ),
        )
    ]
