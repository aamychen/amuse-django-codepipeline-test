# Generated by Django 3.2.15 on 2022-12-28 16:43

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('users', '0100_add_tiktok_name')]

    operations = [
        migrations.AddField(
            model_name='artistv2',
            name='is_auto_generated',
            field=models.BooleanField(blank=True, editable=False, null=True),
        ),
        migrations.AddField(
            model_name='historicalartistv2',
            name='is_auto_generated',
            field=models.BooleanField(blank=True, editable=False, null=True),
        ),
    ]
