# Generated by Django 2.0.6 on 2018-06-27 09:28

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('users', '0024_artists_data_migration'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('releases', '0060_cover_art_checksum_field'),
    ]

    operations = [
        migrations.AddField(
            model_name='contributor',
            name='artist',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to='users.Artist',
            ),
        ),
        migrations.AddField(
            model_name='contributor',
            name='royalty_split',
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                max_digits=5,
                verbose_name='Royalty split percentage',
            ),
        ),
        migrations.AddField(
            model_name='contributor',
            name='user',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name='historicalcontributor',
            name='artist',
            field=models.ForeignKey(
                blank=True,
                db_constraint=False,
                null=True,
                on_delete=django.db.models.deletion.DO_NOTHING,
                related_name='+',
                to='users.Artist',
            ),
        ),
        migrations.AddField(
            model_name='historicalcontributor',
            name='royalty_split',
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                max_digits=5,
                verbose_name='Royalty split percentage',
            ),
        ),
        migrations.AddField(
            model_name='historicalcontributor',
            name='user',
            field=models.ForeignKey(
                blank=True,
                db_constraint=False,
                null=True,
                on_delete=django.db.models.deletion.DO_NOTHING,
                related_name='+',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterField(
            model_name='contributor',
            name='role',
            field=models.SmallIntegerField(
                choices=[
                    (1, 'featured_artist'),
                    (2, 'writer'),
                    (3, 'producer'),
                    (4, 'mixer'),
                    (5, 'remixer'),
                    (6, 'primary_artist'),
                    (7, 'performer'),
                    (8, 'other'),
                ]
            ),
        ),
        migrations.AlterField(
            model_name='historicalcontributor',
            name='role',
            field=models.SmallIntegerField(
                choices=[
                    (1, 'featured_artist'),
                    (2, 'writer'),
                    (3, 'producer'),
                    (4, 'mixer'),
                    (5, 'remixer'),
                    (6, 'primary_artist'),
                    (7, 'performer'),
                    (8, 'other'),
                ]
            ),
        ),
    ]
