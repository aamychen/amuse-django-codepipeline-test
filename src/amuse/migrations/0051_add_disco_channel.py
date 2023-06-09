# Generated by Django 2.2.25 on 2022-05-11 14:05

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('amuse', '0050_bulkdeliveryjob_checks_to_override')]

    operations = [
        migrations.AlterField(
            model_name='batchdelivery',
            name='channel',
            field=models.PositiveSmallIntegerField(
                choices=[
                    (1, 'fuga'),
                    (2, 'apple'),
                    (3, 'spotify'),
                    (4, 'tiktok'),
                    (5, 'soundcloud'),
                    (6, 'sevendigital'),
                    (7, 'amazon'),
                    (8, 'anghami'),
                    (9, 'claro_musica'),
                    (10, 'deezer'),
                    (11, 'nuuday'),
                    (12, 'tidal'),
                    (13, 'youtube_content_id'),
                    (14, 'youtube_music'),
                    (15, 'facebook'),
                    (16, 'twitch'),
                    (17, 'shazam'),
                    (18, 'audiomack'),
                    (19, 'boomplay'),
                    (20, 'pandora'),
                    (21, 'kkbox'),
                    (22, 'tencent'),
                    (23, 'iheart'),
                    (24, 'disco'),
                ],
                db_index=True,
            ),
        )
    ]
