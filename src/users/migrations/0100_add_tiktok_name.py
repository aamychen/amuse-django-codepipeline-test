# Generated by Django 3.2.15 on 2022-12-07 09:51

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('users', '0099_gdprremovalrequest')]

    operations = [
        migrations.AddField(
            model_name='artistv2',
            name='tiktok_name',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='historicalartistv2',
            name='tiktok_name',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
    ]
