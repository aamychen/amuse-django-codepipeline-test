# Generated by Django 2.0.7 on 2018-08-01 10:57

from django.db import migrations
import logging

logger = logging.getLogger(__name__)

GROOVE_MUSIC_DB_ID = 23


def update_groove_store(apps, active):
    Store = apps.get_model('releases', 'Store')

    try:
        store = Store.objects.get(pk=GROOVE_MUSIC_DB_ID)
    except Store.DoesNotExist:
        logger.warning(f'Did not find store with ID %s', GROOVE_MUSIC_DB_ID)
        return

    if 'Groove' in store.name:
        store.active = active
        store.save()
    else:
        logger.warning(
            f'Store with ID %s does not seem to be Groove Music', GROOVE_MUSIC_DB_ID
        )


def inactivate_groove_store(apps, schema_editor):
    update_groove_store(apps, active=False)


def activate_groove_store(apps, schema_editor):
    update_groove_store(apps, active=True)


class Migration(migrations.Migration):
    dependencies = [('releases', '0057_store_active_field')]

    operations = [migrations.RunPython(inactivate_groove_store, activate_groove_store)]