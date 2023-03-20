# Generated by Django 2.1.15 on 2021-06-04 07:52

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('subscriptions', '0029_introductorypricecard')]

    operations = [
        migrations.AddField(
            model_name='historicalsubscriptionplan',
            name='google_product_id_introductory',
            field=models.CharField(
                blank=True,
                default='',
                help_text='Users that are eligible for introductory offers will be put on this plan',
                max_length=255,
            ),
        ),
        migrations.AddField(
            model_name='subscriptionplan',
            name='google_product_id_introductory',
            field=models.CharField(
                blank=True,
                default='',
                help_text='Users that are eligible for introductory offers will be put on this plan',
                max_length=255,
            ),
        ),
    ]
