# Generated by Django 3.2.15 on 2023-02-13 14:43

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('releases', '0159_add_release_schedule_type')]

    operations = [
        migrations.CreateModel(
            name='FugaMigrationWave',
            fields=[
                (
                    'id',
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name='ID',
                    ),
                ),
                (
                    'description',
                    models.CharField(
                        blank=True, editable=False, max_length=120, null=True
                    ),
                ),
            ],
        ),
        migrations.AddField(
            model_name='fugametadata',
            name='fuga_migration_wave',
            field=models.ForeignKey(
                blank=True,
                editable=False,
                null=True,
                on_delete=django.db.models.deletion.DO_NOTHING,
                to='releases.fugamigrationwave',
            ),
        ),
    ]
