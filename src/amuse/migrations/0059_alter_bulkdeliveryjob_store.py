# Generated by Django 3.2.15 on 2023-02-06 12:08

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('releases', '0157_fugametadata_spotify_flags'),
        ('amuse', '0058_bulkdeliveryjob_store'),
    ]

    operations = [
        migrations.AlterField(
            model_name='bulkdeliveryjob',
            name='store',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='store_selected',
                to='releases.store',
            ),
        )
    ]