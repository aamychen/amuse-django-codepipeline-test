# Generated by Django 3.2.15 on 2022-09-12 15:35

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('releases', '0126_fix_warnings')]

    operations = [
        migrations.AlterField(
            model_name='fugadeliveryhistory',
            name='executed_by',
            field=models.CharField(
                blank=True, db_index=True, editable=False, max_length=256, null=True
            ),
        )
    ]
