# Generated by Django 2.0.6 on 2018-07-23 10:38

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('releases', '0055_original_release_date')]

    operations = [
        migrations.AddField(
            model_name='historicalsong',
            name='original_release_date',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='song',
            name='original_release_date',
            field=models.DateField(blank=True, null=True),
        ),
    ]