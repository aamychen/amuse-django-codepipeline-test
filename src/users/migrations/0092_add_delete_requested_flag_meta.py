# Generated by Django 2.2.25 on 2022-01-19 12:34

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('users', '0091_add_audiomack_vendor')]

    operations = [
        migrations.AddField(
            model_name='usermetadata',
            name='delete_requested_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='usermetadata',
            name='is_delete_requested',
            field=models.BooleanField(default=False),
        ),
    ]
