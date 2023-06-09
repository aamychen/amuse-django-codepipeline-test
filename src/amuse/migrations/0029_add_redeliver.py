# Generated by Django 2.0.13 on 2021-04-06 08:55

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('amuse', '0028_batchdeliveryrelease_stores')]

    operations = [
        migrations.AddField(
            model_name='batchdeliveryrelease',
            name='redeliver',
            field=models.NullBooleanField(
                default=False, help_text='Mark this for re-delivery.'
            ),
        ),
        migrations.AlterField(
            model_name='batchdeliveryrelease',
            name='status',
            field=models.PositiveSmallIntegerField(
                choices=[
                    (0, 'created'),
                    (1, 'started'),
                    (2, 'succeeded'),
                    (10, 'storing'),
                    (11, 'redelivered'),
                    (99, 'failed'),
                ],
                default=0,
            ),
        ),
    ]
