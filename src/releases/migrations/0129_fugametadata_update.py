# Generated by Django 3.2.15 on 2022-10-13 09:15

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('releases', '0128_fugametadata_add_fields')]

    operations = [
        migrations.AlterField(
            model_name='fugametadata',
            name='language',
            field=models.CharField(
                blank=True, editable=False, max_length=32, null=True
            ),
        ),
        migrations.AlterField(
            model_name='fugametadata',
            name='parental_advisory_next',
            field=models.CharField(
                blank=True, editable=False, max_length=32, null=True
            ),
        ),
    ]
