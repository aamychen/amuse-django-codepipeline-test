# Generated by Django 2.0.13 on 2020-06-23 08:30

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('subscriptions', '0014_set_sub_plan_price_to_8_max_digits'),
    ]

    operations = [
        migrations.AlterField(
            model_name='subscriptionplan',
            name='currency',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT, to='countries.Currency'
            ),
        ),
    ]