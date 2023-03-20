from django.db import migrations

from codes.models import ISRC as RealISRC


def assign_isrc_to_songs(apps, schema_editor):
    Song = apps.get_model("releases", "Song")
    FakeISRC = apps.get_model("codes", "ISRC")

    for song in Song.objects.filter(isrc=None):
        # Since the use method belongs to the Code we can only use it if we
        # import the real ISRC class.
        isrc = RealISRC.objects.use(None)
        # We need to convert the real ISRC to fake ISRC in order to assign it
        # to the Song
        song.isrc = FakeISRC.objects.get(id=isrc.id)
        song.save()


class Migration(migrations.Migration):
    dependencies = [('releases', '0080_auto_20190829_0754')]

    operations = [migrations.RunPython(assign_isrc_to_songs, migrations.RunPython.noop)]
