# Generated by Django 2.0.10 on 2019-09-18 12:09

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('users', '0046_make_inv_token_unique')]

    operations = [
        migrations.CreateModel(
            name='UserMetadata',
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
                (
                    'hyperwallet_user_token',
                    models.CharField(blank=True, max_length=50, null=True),
                ),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('updated', models.DateTimeField(auto_now=True)),
                (
                    'user',
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.AddField(
            model_name='transactionwithdrawal',
            name='hyperwallet_payment_token',
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
    ]
