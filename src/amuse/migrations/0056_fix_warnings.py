# Generated by Django 3.2.15 on 2022-09-08 17:06

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('amuse', '0055_add_netease_channel'),
    ]

    operations = [
        migrations.AlterField(
            model_name='acrcloudmatch',
            name='external_metadata',
            field=models.JSONField(null=True),
        ),
        migrations.AlterField(
            model_name='batchdeliveryrelease',
            name='redeliver',
            field=models.BooleanField(
                blank=True,
                default=False,
                help_text='Mark this for re-delivery.',
                null=True,
            ),
        ),
    ]
