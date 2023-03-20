# Generated by Django 2.1.15 on 2021-09-02 06:13

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('payouts', '0004_trm_conf_add_country'),
    ]

    operations = [
        migrations.AlterField(
            model_name='transfermethod',
            name='external_id',
            field=models.CharField(
                help_text='External transfer method identifier',
                max_length=255,
                unique=True,
            ),
        ),
    ]