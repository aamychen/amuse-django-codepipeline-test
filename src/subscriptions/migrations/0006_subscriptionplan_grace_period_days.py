# Generated by Django 2.0.10 on 2020-01-17 09:05

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('subscriptions', '0005_payment_method_model')]

    operations = [
        migrations.AddField(
            model_name='subscription',
            name='grace_period_until',
            field=models.DateField(
                blank=True,
                help_text='Will retry renewal payments and consider Subscription as active until this date',
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='subscriptionplan',
            name='grace_period_days',
            field=models.IntegerField(
                default=0,
                help_text='Number of days subscription remains active if payment fails',
            ),
        ),
        migrations.AlterField(
            model_name='subscription',
            name='status',
            field=models.PositiveSmallIntegerField(
                choices=[
                    (0, 'Created'),
                    (1, 'Active'),
                    (2, 'Expired'),
                    (3, 'Pending'),
                    (4, 'Error'),
                    (5, 'Replaced (was never used)'),
                    (6, 'In expiry grace period (due to failed payment)'),
                ],
                default=0,
            ),
        ),
    ]
