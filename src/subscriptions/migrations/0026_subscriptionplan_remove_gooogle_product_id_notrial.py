# Generated by Django 2.1.15 on 2021-04-06 12:28

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [('subscriptions', '0025_subscriptionplan_google_product_id_trial')]

    operations = [
        migrations.RemoveField(
            model_name='historicalsubscriptionplan', name='google_product_id_notrial'
        ),
        migrations.RemoveField(
            model_name='subscriptionplan', name='google_product_id_notrial'
        ),
    ]