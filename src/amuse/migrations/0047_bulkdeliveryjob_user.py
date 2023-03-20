# Generated by Django 2.2.25 on 2022-02-03 13:30

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('amuse', '0046_batch_user'),
    ]

    operations = [
        migrations.AddField(
            model_name='bulkdeliveryjob',
            name='user',
            field=models.ForeignKey(
                blank=True,
                editable=False,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to=settings.AUTH_USER_MODEL,
            ),
        )
    ]
