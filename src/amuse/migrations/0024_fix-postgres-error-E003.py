# Generated by Django 2.0.13 on 2021-01-28 10:25

import django.contrib.postgres.fields
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('amuse', '0023_add_amazon_delivery_channel'),
    ]

    operations = [
        migrations.AlterField(
            model_name='transcoding',
            name='errors',
            field=django.contrib.postgres.fields.ArrayField(
                base_field=models.CharField(max_length=512), default=list, size=None
            ),
        ),
        migrations.AlterField(
            model_name='transcoding',
            name='warnings',
            field=django.contrib.postgres.fields.ArrayField(
                base_field=models.CharField(max_length=512), default=list, size=None
            ),
        ),
    ]
