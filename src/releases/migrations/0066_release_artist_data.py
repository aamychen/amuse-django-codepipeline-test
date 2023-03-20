# Generated by Django 2.0.8 on 2018-08-28 06:45

from django.db import migrations


def migrate_forwards(apps, schema_editor):
    """
    Connect Release.user.artist_set.first() to Release.artist for:
                !~*`^´*~REALLY MAIN PRIMARY ARTIST~*`^´*~!
    """
    Release = apps.get_model('releases', 'Release')
    for r in Release.objects.select_related('user'):
        # use cached relation by not using first
        r.artist = r.user.artist_set.all()[0]
        r.save()


def migrate_backwards(apps, schema_editor):
    """
    Disconnect Release artists (pretty unneseccary really since previous migrations
    backwards action is to drop this column, but it might be nice to have when testing
    etc..)
    """
    Release = apps.get_model('releases', 'Release')
    Release.objects.update(artist=None)


class Migration(migrations.Migration):
    dependencies = [('releases', '0065_release_artist')]

    operations = [migrations.RunPython(migrate_forwards, migrate_backwards)]