# Generated by Django 2.0.10 on 2020-01-08 12:22

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('users', '0061_usergdpr')]

    operations = [
        migrations.AddField(
            model_name='artistv2',
            name='spotify_image',
            field=models.CharField(blank=True, default=None, max_length=512, null=True),
        ),
        migrations.AddField(
            model_name='historicalartistv2',
            name='spotify_image',
            field=models.CharField(blank=True, default=None, max_length=512, null=True),
        ),
    ]