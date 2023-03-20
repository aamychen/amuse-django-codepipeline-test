# Generated by Django 2.2.25 on 2022-01-24 10:20

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('releases', '0115_alter_song_artist_roles'),
        ('amuse', '0043_bulkdeliveryjob_update'),
    ]

    operations = [
        migrations.CreateModel(
            name='BulkDeliveryJobResult',
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
                    'status',
                    models.PositiveSmallIntegerField(
                        choices=[
                            (0, 'unprocessed'),
                            (1, 'failed'),
                            (2, 'prevented'),
                            (3, 'successful'),
                        ],
                        db_index=True,
                        default=0,
                        editable=False,
                    ),
                ),
                (
                    'description',
                    models.CharField(editable=False, max_length=512, null=True),
                ),
                ('date_created', models.DateTimeField(auto_now_add=True)),
                ('date_updated', models.DateTimeField(auto_now=True)),
                (
                    'delivery',
                    models.ForeignKey(
                        default=None,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to='amuse.BatchDelivery',
                    ),
                ),
                (
                    'job',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to='amuse.BulkDeliveryJob',
                    ),
                ),
                (
                    'release',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to='releases.Release',
                    ),
                ),
            ],
            options={
                'verbose_name_plural': 'Bulk Delivery Job Results',
                'unique_together': {('job', 'release')},
            },
        )
    ]
