# Generated by Django 2.1.15 on 2021-05-11 09:35

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('users', '0089_add_new_flag_reason'),
    ]

    operations = [
        migrations.AddField(
            model_name='usermetadata',
            name='gdpr_wiped_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
