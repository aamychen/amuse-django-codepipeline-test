# Generated by Django 2.2.25 on 2022-02-07 15:31

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('payouts', '0006_add_government_id'),
    ]

    operations = [
        migrations.AddField(
            model_name='payment',
            name='payment_type',
            field=models.PositiveSmallIntegerField(
                choices=[(0, 'unknown'), (1, 'royalty'), (2, 'advance')], default=0
            ),
        ),
    ]
