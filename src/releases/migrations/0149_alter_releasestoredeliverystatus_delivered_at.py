# Generated by Django 3.2.15 on 2022-12-01 15:58

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('releases', '0148_releasestoredeliverystatus_delivered_at')]

    operations = [
        migrations.AlterField(
            model_name='releasestoredeliverystatus',
            name='delivered_at',
            field=models.DateTimeField(),
        )
    ]
