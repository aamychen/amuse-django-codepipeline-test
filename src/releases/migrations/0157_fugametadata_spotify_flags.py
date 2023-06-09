# Generated by Django 3.2.15 on 2023-01-26 14:30

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('releases', '0156_fugametadata_spotify_migration')]

    operations = [
        migrations.AddField(
            model_name='fugametadata',
            name='has_spotify_ids',
            field=models.BooleanField(
                db_index=True, default=None, editable=False, null=True
            ),
        ),
        migrations.AddField(
            model_name='fugametadata',
            name='spotify_roles_match',
            field=models.BooleanField(
                db_index=True, default=None, editable=False, null=True
            ),
        ),
        migrations.AddField(
            model_name='fugaproductasset',
            name='has_spotify_ids',
            field=models.BooleanField(
                db_index=True, default=None, editable=False, null=True
            ),
        ),
        migrations.AddField(
            model_name='fugaproductasset',
            name='spotify_roles_match',
            field=models.BooleanField(
                db_index=True, default=None, editable=False, null=True
            ),
        ),
    ]
