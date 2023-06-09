# Generated by Django 2.0.13 on 2020-07-10 12:49

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('countries', '0006_currency'),
        ('payments', '0021_transaction_limit'),
    ]

    operations = [
        migrations.AddField(
            model_name='historicalpaymenttransaction',
            name='currency',
            field=models.ForeignKey(
                blank=True,
                db_constraint=False,
                null=True,
                on_delete=django.db.models.deletion.DO_NOTHING,
                related_name='+',
                to='countries.Currency',
            ),
        ),
        migrations.AddField(
            model_name='paymenttransaction',
            name='currency',
            field=models.ForeignKey(
                default=5,
                on_delete=django.db.models.deletion.PROTECT,
                to='countries.Currency',
            ),
        ),
    ]
