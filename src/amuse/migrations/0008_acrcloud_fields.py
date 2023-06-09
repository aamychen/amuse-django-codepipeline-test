# Generated by Django 2.0.8 on 2018-11-22 13:18

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('amuse', '0007_acrcloudmatch')]

    operations = [
        migrations.AlterModelOptions(
            name='acrcloudmatch',
            options={
                'verbose_name': 'ACRCloud match',
                'verbose_name_plural': 'ACRCloud matches',
            },
        ),
        migrations.AlterField(
            model_name='acrcloudmatch',
            name='match_isrc',
            field=models.CharField(max_length=32, null=True),
        ),
        migrations.AlterField(
            model_name='acrcloudmatch',
            name='match_upc',
            field=models.CharField(max_length=32, null=True),
        ),
    ]
