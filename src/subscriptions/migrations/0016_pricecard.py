# Generated by Django 2.0.13 on 2020-06-29 13:29

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('countries', '0006_currency'),
        ('subscriptions', '0015_make_currency_required_on_subplan'),
    ]

    operations = [
        migrations.CreateModel(
            name='PriceCard',
            fields=[
                (
                    'id',
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name='ID',
                    ),
                ),
                (
                    'price',
                    models.DecimalField(
                        decimal_places=2, help_text='Including VAT', max_digits=8
                    ),
                ),
                (
                    'countries',
                    models.ManyToManyField(blank=True, to='countries.Country'),
                ),
                (
                    'currency',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        to='countries.Currency',
                    ),
                ),
                (
                    'plan',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        to='subscriptions.SubscriptionPlan',
                    ),
                ),
            ],
        ),
    ]
