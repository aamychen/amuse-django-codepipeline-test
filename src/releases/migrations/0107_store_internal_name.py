# Generated by Django 2.0.13 on 2021-02-11 14:20

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('releases', '0106_release_stores_verbose_name'),
    ]

    operations = [
        migrations.AddField(
            model_name='store',
            name='internal_name',
            field=models.CharField(blank=True, max_length=64, null=True),
        ),
    ]