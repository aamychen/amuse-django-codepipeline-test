# Generated by Django 2.0.10 on 2019-03-27 14:17

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('releases', '0074_lyricsanalysisresult')]

    operations = [
        migrations.AddField(
            model_name='contributor',
            name='spotify_id',
            field=models.CharField(blank=True, max_length=120, null=True),
        ),
        migrations.AddField(
            model_name='historicalcontributor',
            name='spotify_id',
            field=models.CharField(blank=True, max_length=120, null=True),
        ),
    ]