# Generated by Django 2.0.13 on 2021-03-15 16:32

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('releases', '0108_store_parent'),
    ]

    operations = [
        migrations.CreateModel(
            name='ReleaseStoresHistory',
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
                ('created', models.DateTimeField(auto_now_add=True)),
                (
                    'release',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to='releases.Release',
                    ),
                ),
                ('stores', models.ManyToManyField(to='releases.Store')),
            ],
        ),
    ]
