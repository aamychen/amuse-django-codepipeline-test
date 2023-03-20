# Generated by Django 2.1.15 on 2021-03-26 12:30

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('subscriptions', '0023_subscription_free_trial_datetime')]

    operations = [
        migrations.AddField(
            model_name='historicalsubscriptionplan',
            name='google_product_id_notrial',
            field=models.CharField(
                blank=True,
                default='',
                help_text='Users that are not eligible for trial will be put on this plan',
                max_length=255,
            ),
        ),
        migrations.AddField(
            model_name='subscriptionplan',
            name='google_product_id_notrial',
            field=models.CharField(
                blank=True,
                default='',
                help_text='Users that are not eligible for trial will be put on this plan',
                max_length=255,
            ),
        ),
    ]
