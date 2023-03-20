from django.conf import settings
from django.db import migrations, models, transaction
import django.db.models.deletion


@transaction.atomic
def migrate_data(apps, schema_editor):
    AmuseMinfraudResult = apps.get_model("amuse", "MinfraudResult")
    for item in apps.get_model("users", "MinfraudResult").objects.all():
        AmuseMinfraudResult.objects.create(
            user=item.user,
            response_body=item.response_body,
            risk_score=item.risk_score,
            event_time=item.event_time,
            event_type=item.event_type,
        )


@transaction.atomic
def migrate_data_back(apps, schema_editor):
    UsersMinfraudResult = apps.get_model("users", "MinfraudResult")
    for item in apps.get_model("amuse", "MinfraudResult").objects.all():
        UsersMinfraudResult.objects.create(
            user=item.user,
            response_body=item.response_body,
            risk_score=item.risk_score,
            event_time=item.event_time,
            event_type=item.event_type,
        )


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('amuse', '0013_batchdeliveryrelease_excluded_stores'),
        ('users', '0042_auto_20190729_0855'),
    ]

    operations = [
        migrations.CreateModel(
            name='MinfraudResult',
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
                ('response_body', models.TextField()),
                ('risk_score', models.DecimalField(decimal_places=2, max_digits=5)),
                ('event_time', models.DateTimeField()),
                (
                    'event_type',
                    models.PositiveSmallIntegerField(
                        choices=[
                            (0, 'Default'),
                            (1, 'Account creation'),
                            (2, 'Release'),
                            (3, 'Email change'),
                            (4, 'Password reset'),
                        ],
                        default=0,
                    ),
                ),
                (
                    'user',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to=settings.AUTH_USER_MODEL,
                        null=True,
                    ),
                ),
                (
                    'release',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to='releases.Release',
                        null=True,
                    ),
                ),
            ],
        ),
        migrations.RunPython(migrate_data, migrate_data_back),
    ]
