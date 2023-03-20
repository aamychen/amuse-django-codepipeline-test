# Generated by Django 2.0.10 on 2020-01-27 12:32

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('amuse', '0018_add_tiktok_as_batch_delivery_channel'),
    ]

    operations = [
        migrations.AlterField(
            model_name='batchdelivery',
            name='channel',
            field=models.PositiveSmallIntegerField(
                choices=[
                    (1, 'fuga'),
                    (2, 'apple'),
                    (3, 'spotify'),
                    (4, 'tiktok'),
                    (5, 'soundcloud'),
                ]
            ),
        ),
    ]
