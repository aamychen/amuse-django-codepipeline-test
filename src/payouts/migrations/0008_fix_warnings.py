# Generated by Django 3.2.15 on 2022-09-08 17:06

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('payouts', '0007_add_payment_type'),
    ]

    operations = [
        migrations.AlterField(
            model_name='event',
            name='payload',
            field=models.JSONField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='transfermethodconfiguration',
            name='fee',
            field=models.JSONField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='transfermethodconfiguration',
            name='limits',
            field=models.JSONField(blank=True, null=True),
        ),
    ]
