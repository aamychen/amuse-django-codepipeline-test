# Generated by Django 2.2.25 on 2022-06-21 21:54

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('releases', '0118_store_multi_batch_support'),
    ]

    operations = [
        migrations.AddField(
            model_name='store',
            name='slug',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
    ]
