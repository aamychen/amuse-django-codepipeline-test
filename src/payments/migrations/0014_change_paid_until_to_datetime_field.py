# Generated by Django 2.0.10 on 2020-02-20 12:47

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('payments', '0013_paymentmethod'),
    ]

    operations = [
        migrations.AlterField(
            model_name='paymenttransaction',
            name='paid_until',
            field=models.DateTimeField(),
        ),
    ]
