# Generated by Django 2.0.8 on 2018-11-12 15:51

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('amuse', '0005_image')]

    operations = [
        migrations.AddField(
            model_name='batchdeliveryrelease',
            name='type',
            field=models.PositiveSmallIntegerField(
                choices=[(0, 'INSERT'), (1, 'UPDATE')], default=0
            ),
        )
    ]