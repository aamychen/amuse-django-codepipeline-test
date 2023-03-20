# Generated by Django 2.0.10 on 2020-03-09 10:42

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('amuse', '0019_add_soundcloud_delivery_channel'),
    ]

    operations = [
        migrations.AddField(
            model_name='transcoding',
            name='transcoder_name',
            field=models.PositiveIntegerField(
                choices=[(1, 'elastictranscoder'), (2, 'audio-transcoder-service')],
                default=1,
            ),
        ),
    ]
