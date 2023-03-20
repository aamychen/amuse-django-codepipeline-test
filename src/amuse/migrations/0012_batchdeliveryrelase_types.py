# Generated by Django 2.0.10 on 2019-02-22 14:36

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('amuse', '0011_support')]

    operations = [
        migrations.AlterField(
            model_name='batchdeliveryrelease',
            name='type',
            field=models.PositiveSmallIntegerField(
                choices=[(0, 'insert'), (1, 'update'), (2, 'takedown')], default=0
            ),
        )
    ]
