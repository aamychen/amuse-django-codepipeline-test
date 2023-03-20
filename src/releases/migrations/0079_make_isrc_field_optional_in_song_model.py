# Generated by Django 2.0.10 on 2019-08-15 12:19

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('releases', '0078_make_upc_field_optional_in_release_model')]

    operations = [
        migrations.AlterField(
            model_name='song',
            name='isrc',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to='codes.ISRC',
            ),
        )
    ]
