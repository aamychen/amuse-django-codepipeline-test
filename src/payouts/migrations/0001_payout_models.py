# Generated by Django 2.1.15 on 2021-06-17 20:04

from django.conf import settings
import django.contrib.postgres.fields.jsonb
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ('users', '0090_usermetadata_gdpr_wiped_at'),
        ('countries', '0007_exchange_rate'),
    ]

    operations = [
        migrations.CreateModel(
            name='Event',
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
                    'object_id',
                    models.CharField(
                        help_text='Payee, TransferMethod or Payment token identifiers',
                        max_length=255,
                    ),
                ),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('reason', models.CharField(help_text='eg. WEBHOOK', max_length=125)),
                (
                    'initiator',
                    models.CharField(
                        help_text='eg SYSTEM, JARVI5, BATCH_TASK', max_length=125
                    ),
                ),
                (
                    'payload',
                    django.contrib.postgres.fields.jsonb.JSONField(
                        blank=True, null=True
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name='Payee',
            fields=[
                (
                    'user',
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        primary_key=True,
                        serialize=False,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    'external_id',
                    models.CharField(
                        help_text='External user identifier', max_length=255
                    ),
                ),
                ('status', models.CharField(max_length=125)),
                ('verification_status', models.CharField(max_length=124)),
                (
                    'type',
                    models.PositiveSmallIntegerField(
                        choices=[(1, 'individual'), (2, 'business')], default=1
                    ),
                ),
                ('created', models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name='Payment',
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
                    'external_id',
                    models.CharField(
                        help_text='External payment identifier', max_length=255
                    ),
                ),
                (
                    'amount',
                    models.DecimalField(
                        decimal_places=2, help_text='Total amount paid ', max_digits=8
                    ),
                ),
                ('status', models.CharField(max_length=125)),
                ('created', models.DateTimeField(auto_now_add=True)),
                (
                    'currency',
                    models.ForeignKey(
                        default=5,
                        on_delete=django.db.models.deletion.PROTECT,
                        to='countries.Currency',
                    ),
                ),
                (
                    'payee',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='payments',
                        to='payouts.Payee',
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name='Provider',
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
                ('name', models.TextField()),
                (
                    'external_id',
                    models.CharField(
                        help_text='External provider identifier eg Hyperwallet program token',
                        max_length=255,
                    ),
                ),
                ('active', models.BooleanField(default=True)),
                ('created', models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name='TransferMethod',
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
                    'external_id',
                    models.CharField(
                        help_text='External transfer method identifier', max_length=255
                    ),
                ),
                ('type', models.CharField(max_length=125)),
                ('status', models.CharField(max_length=125)),
                ('active', models.BooleanField(default=True)),
                ('created', models.DateTimeField(auto_now_add=True)),
                (
                    'payee',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='transfer_methods',
                        to='payouts.Payee',
                    ),
                ),
                (
                    'provider',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        to='payouts.Provider',
                    ),
                ),
            ],
        ),
        migrations.AddField(
            model_name='payment',
            name='transfer_method',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.DO_NOTHING,
                to='payouts.TransferMethod',
            ),
        ),
        migrations.AddField(
            model_name='payee',
            name='provider',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.DO_NOTHING, to='payouts.Provider'
            ),
        ),
    ]