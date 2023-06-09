# Generated by Django 2.0.10 on 2020-06-08 10:58

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('amuse', '0021_add_sevendigital_delivery_channel'),
    ]

    operations = [
        migrations.AlterField(
            model_name='batchdeliveryrelease',
            name='type',
            field=models.PositiveSmallIntegerField(
                choices=[
                    (0, 'insert'),
                    (1, 'update'),
                    (2, 'takedown'),
                    (3, 'pro_takedown'),
                ],
                default=0,
            ),
        ),
    ]
