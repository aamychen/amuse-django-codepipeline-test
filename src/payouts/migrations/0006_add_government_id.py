# Generated by Django 2.1.15 on 2021-11-02 12:39

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('payouts', '0005_trm_external_id_unique'),
    ]

    operations = [
        migrations.AddField(
            model_name='payee',
            name='government_id',
            field=models.CharField(
                blank=True,
                help_text='Government issued user id',
                max_length=125,
                null=True,
            ),
        ),
    ]
