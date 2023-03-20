# Generated by Django 2.0.13 on 2021-01-10 22:47

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('subscriptions', '0018_add_tier_column')]

    operations = [
        migrations.AddField(
            model_name='historicalsubscriptionplan',
            name='google_product_id',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
        migrations.AddField(
            model_name='subscriptionplan',
            name='google_product_id',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
    ]