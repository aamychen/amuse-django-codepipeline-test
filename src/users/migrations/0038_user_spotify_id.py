# Generated by Django 2.0.10 on 2019-03-27 11:09

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('users', '0037_royalty_advance_rate_decimals')]

    operations = [
        migrations.AddField(
            model_name='user',
            name='spotify_id',
            field=models.CharField(blank=True, max_length=120, null=True),
        )
    ]