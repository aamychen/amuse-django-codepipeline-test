# Generated by Django 2.0.10 on 2019-11-01 14:15

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('users', '0054_song_artist_invitation')]

    operations = [
        migrations.AddField(
            model_name='user',
            name='subscription',
            field=models.PositiveSmallIntegerField(
                choices=[(0, 'free'), (1, 'pro')], default=0
            ),
        )
    ]
