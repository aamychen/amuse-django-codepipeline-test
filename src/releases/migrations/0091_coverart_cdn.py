# Generated by Django 2.0.10 on 2020-01-23 09:18

import amuse.db.models
import amuse.storages
from django.conf import settings
from django.db import migrations
import releases.models.coverart


class Migration(migrations.Migration):
    dependencies = [
        ('releases', '0090_add_created_by_column'),
    ]

    operations = [
        migrations.AlterField(
            model_name='coverart',
            name='file',
            field=amuse.db.models.ImageWithThumbsField(
                height_field='height',
                storage=amuse.storages.S3Storage(
                    bucket_name=settings.AWS_COVER_ART_UPLOADED_BUCKET_NAME,
                    custom_domain=settings.ASSETS_CDN_DOMAIN,
                    querystring_auth=False,
                ),
                upload_to=releases.models.coverart.uploaded_directory_path,
                width_field='width',
            ),
        ),
    ]
