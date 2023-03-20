# Generated by Django 2.0.10 on 2019-06-13 11:53

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('users', '0039_auto_20190527_1149')]

    operations = [
        migrations.AlterField(
            model_name='artistv2',
            name='owner',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to=settings.AUTH_USER_MODEL,
            ),
        )
    ]
