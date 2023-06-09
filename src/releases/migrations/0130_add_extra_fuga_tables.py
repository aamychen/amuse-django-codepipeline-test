# Generated by Django 3.2.15 on 2022-10-19 11:11

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('releases', '0129_fugametadata_update')]

    operations = [
        migrations.CreateModel(
            name='FugaArtist',
            fields=[
                (
                    'id',
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name='ID',
                    ),
                ),
                ('external_id', models.BigIntegerField(unique=True)),
                (
                    'name',
                    models.CharField(
                        blank=True,
                        db_index=True,
                        editable=False,
                        max_length=1024,
                        null=True,
                    ),
                ),
                (
                    'apple_id',
                    models.CharField(
                        blank=True,
                        db_index=True,
                        editable=False,
                        max_length=1024,
                        null=True,
                    ),
                ),
                (
                    'spotify_id',
                    models.CharField(
                        blank=True,
                        db_index=True,
                        editable=False,
                        max_length=1024,
                        null=True,
                    ),
                ),
                ('matched_artist', models.BigIntegerField()),
            ],
        ),
        migrations.CreateModel(
            name='FugaArtistToPerson',
            fields=[
                (
                    'id',
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name='ID',
                    ),
                ),
                ('fuga_artist_id', models.BigIntegerField(db_index=True)),
                ('fuga_person_id', models.BigIntegerField(db_index=True)),
                ('names_match', models.BooleanField(db_index=True)),
                ('verified', models.BooleanField(db_index=True)),
            ],
        ),
        migrations.CreateModel(
            name='FugaAsset',
            fields=[
                (
                    'id',
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name='ID',
                    ),
                ),
                ('external_id', models.BigIntegerField(unique=True)),
                (
                    'isrc',
                    models.CharField(
                        blank=True,
                        db_index=True,
                        editable=False,
                        max_length=16,
                        null=True,
                    ),
                ),
                (
                    'name',
                    models.CharField(
                        blank=True, editable=False, max_length=1024, null=True
                    ),
                ),
                (
                    'duration',
                    models.IntegerField(blank=True, editable=False, null=True),
                ),
                (
                    'language',
                    models.CharField(
                        blank=True, editable=False, max_length=32, null=True
                    ),
                ),
                (
                    'sequence',
                    models.IntegerField(blank=True, editable=False, null=True),
                ),
                (
                    'type',
                    models.CharField(
                        blank=True, editable=False, max_length=64, null=True
                    ),
                ),
                (
                    'genre',
                    models.CharField(
                        blank=True, editable=False, max_length=256, null=True
                    ),
                ),
                (
                    'subgenre',
                    models.CharField(
                        blank=True, editable=False, max_length=256, null=True
                    ),
                ),
                (
                    'has_video',
                    models.BooleanField(default=None, editable=False, null=True),
                ),
                (
                    'has_lyrics',
                    models.BooleanField(default=None, editable=False, null=True),
                ),
                (
                    'rights_claim',
                    models.CharField(
                        blank=True, editable=False, max_length=256, null=True
                    ),
                ),
                (
                    'modified_date',
                    models.DateTimeField(blank=True, editable=False, null=True),
                ),
                (
                    'created_date',
                    models.DateTimeField(blank=True, editable=False, null=True),
                ),
                (
                    'audio_id',
                    models.BigIntegerField(
                        blank=True, db_index=True, editable=False, null=True
                    ),
                ),
                (
                    'audio_duration',
                    models.IntegerField(blank=True, editable=False, null=True),
                ),
                (
                    'audio_bit_depth',
                    models.IntegerField(blank=True, editable=False, null=True),
                ),
                (
                    'audio_file_size',
                    models.BigIntegerField(blank=True, editable=False, null=True),
                ),
                (
                    'audio_mime_type',
                    models.CharField(
                        blank=True, editable=False, max_length=128, null=True
                    ),
                ),
                (
                    'audio_vault_hook',
                    models.CharField(
                        blank=True, editable=False, max_length=256, null=True
                    ),
                ),
                (
                    'audio_modified_date',
                    models.DateTimeField(blank=True, editable=False, null=True),
                ),
                (
                    'audio_created_date',
                    models.DateTimeField(blank=True, editable=False, null=True),
                ),
                (
                    'audio_has_uploaded',
                    models.BooleanField(default=None, editable=False, null=True),
                ),
                (
                    'audio_sampling_rate',
                    models.IntegerField(blank=True, editable=False, null=True),
                ),
                (
                    'audio_original_filename',
                    models.CharField(
                        blank=True, editable=False, max_length=256, null=True
                    ),
                ),
                (
                    'audio_number_of_channels',
                    models.IntegerField(blank=True, editable=False, null=True),
                ),
                (
                    'asset_version',
                    models.CharField(
                        blank=True, editable=False, max_length=256, null=True
                    ),
                ),
                (
                    'p_line_text',
                    models.CharField(
                        blank=True, editable=False, max_length=256, null=True
                    ),
                ),
                ('p_line_year', models.IntegerField()),
                (
                    'audio_locale',
                    models.CharField(
                        blank=True, editable=False, max_length=256, null=True
                    ),
                ),
                (
                    'preorder_type',
                    models.CharField(
                        blank=True, editable=False, max_length=256, null=True
                    ),
                ),
                (
                    'preview_start',
                    models.IntegerField(blank=True, editable=False, null=True),
                ),
                (
                    'preview_length',
                    models.IntegerField(blank=True, editable=False, null=True),
                ),
                (
                    'allow_preorder',
                    models.BooleanField(default=None, editable=False, null=True),
                ),
                (
                    'allow_preorder_preview',
                    models.BooleanField(default=None, editable=False, null=True),
                ),
                (
                    'available_separately',
                    models.BooleanField(default=None, editable=False, null=True),
                ),
                (
                    'display_artist',
                    models.CharField(
                        blank=True, editable=False, max_length=256, null=True
                    ),
                ),
                (
                    'parental_advisory',
                    models.BooleanField(default=None, editable=False, null=True),
                ),
                (
                    'parental_advisory_next',
                    models.CharField(
                        blank=True, editable=False, max_length=64, null=True
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name='FugaPerson',
            fields=[
                (
                    'id',
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name='ID',
                    ),
                ),
                ('external_id', models.BigIntegerField(unique=True)),
                (
                    'name',
                    models.CharField(
                        blank=True, editable=False, max_length=1024, null=True
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name='FugaProductArtist',
            fields=[
                (
                    'id',
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name='ID',
                    ),
                ),
                ('release_id', models.BigIntegerField(db_index=True)),
                ('fuga_product_id', models.BigIntegerField(db_index=True)),
                ('fuga_artist_id', models.BigIntegerField(db_index=True)),
                (
                    'primary',
                    models.DateTimeField(blank=True, editable=False, null=True),
                ),
                ('sequence', models.IntegerField()),
            ],
        ),
        migrations.CreateModel(
            name='FugaProductAssetArtist',
            fields=[
                (
                    'id',
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name='ID',
                    ),
                ),
                ('release_id', models.BigIntegerField(db_index=True)),
                ('fuga_product_id', models.BigIntegerField(db_index=True)),
                ('fuga_asset_id', models.BigIntegerField(db_index=True)),
                (
                    'fuga_artist_id',
                    models.CharField(
                        blank=True, editable=False, max_length=1024, null=True
                    ),
                ),
                (
                    'primary',
                    models.DateTimeField(blank=True, editable=False, null=True),
                ),
                (
                    'role',
                    models.CharField(
                        blank=True, editable=False, max_length=128, null=True
                    ),
                ),
                ('sequence', models.IntegerField()),
            ],
        ),
    ]
