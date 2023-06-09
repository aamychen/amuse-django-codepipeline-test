# Generated by Django 2.1.15 on 2021-11-25 08:49

from django.conf import settings
from django.db import migrations, models

import amuse.models.bulk_delivery_job
import amuse.storages


class Migration(migrations.Migration):
    dependencies = [
        ('releases', '0115_alter_song_artist_roles'),
        ('amuse', '0038_add_indexes'),
    ]

    operations = [
        migrations.CreateModel(
            name='BulkDeliveryJob',
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
                (
                    'input_file',
                    models.FileField(
                        help_text='Upload csv file with all the release ids to be handled',
                        storage=amuse.storages.S3Storage(
                            bucket_name=settings.AWS_BULK_DELIVERY_JOB_BUCKET_NAME
                        ),
                        upload_to=amuse.models.bulk_delivery_job.BulkDeliveryJob.generate_file_name,
                        validators=[
                            amuse.models.bulk_delivery_job.validate_file_extension
                        ],
                    ),
                ),
                (
                    'type',
                    models.PositiveSmallIntegerField(
                        choices=[(0, 'insert'), (1, 'update'), (2, 'takedown')],
                        db_index=True,
                        default=0,
                        help_text='Type of bulk operation to perform',
                    ),
                ),
                (
                    'output_file',
                    models.FileField(
                        editable=False,
                        help_text='Results of the bulk delivery job will be available here after processing',
                        storage=amuse.storages.S3Storage(
                            bucket_name=settings.AWS_BULK_DELIVERY_JOB_BUCKET_NAME
                        ),
                        upload_to='',
                    ),
                ),
                (
                    'status',
                    models.PositiveSmallIntegerField(
                        choices=[
                            (0, 'created'),
                            (1, 'processing'),
                            (2, 'completed'),
                            (3, 'failed'),
                        ],
                        db_index=True,
                        default=0,
                        editable=False,
                    ),
                ),
                (
                    'description',
                    models.CharField(editable=False, max_length=256, null=True),
                ),
                ('date_created', models.DateTimeField(auto_now_add=True)),
                ('date_updated', models.DateTimeField(auto_now=True)),
                (
                    'stores',
                    models.ManyToManyField(
                        help_text='Stores to perform the bulk operation towards.',
                        to='releases.Store',
                    ),
                ),
            ],
            options={'verbose_name_plural': 'Bulk Delivery Jobs'},
        )
    ]
