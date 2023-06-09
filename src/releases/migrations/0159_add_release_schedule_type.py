# Generated by Django 3.2.15 on 2023-02-06 13:41

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('releases', '0158_fugametadata_additional_flags'),
    ]

    operations = [
        migrations.AddField(
            model_name='historicalrelease',
            name='schedule_type',
            field=models.SmallIntegerField(
                choices=[(1, 'static'), (2, 'asap')], default=1
            ),
        ),
        migrations.AddField(
            model_name='release',
            name='schedule_type',
            field=models.SmallIntegerField(
                choices=[(1, 'static'), (2, 'asap')], default=1
            ),
        ),
        migrations.AlterField(
            model_name='historicalrelease',
            name='release_date',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='release',
            name='release_date',
            field=models.DateField(blank=True, null=True),
        ),
    ]
