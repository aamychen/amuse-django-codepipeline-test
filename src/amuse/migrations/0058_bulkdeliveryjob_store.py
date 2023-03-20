# Generated by Django 3.2.15 on 2023-02-03 13:51

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('releases', '0157_fugametadata_spotify_flags'),
        ('amuse', '0057_bulkdeliveryjob_ignore_release_status'),
    ]

    operations = [
        migrations.AddField(
            model_name='bulkdeliveryjob',
            name='store',
            field=models.ForeignKey(
                blank=True,
                editable=False,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='store_selected',
                to='releases.store',
            ),
        )
    ]
