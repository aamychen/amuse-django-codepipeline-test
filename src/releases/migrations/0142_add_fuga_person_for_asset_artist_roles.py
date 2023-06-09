# Generated by Django 3.2.15 on 2022-11-07 12:55

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('releases', '0141_add_more_fugametadata_indexes')]

    operations = [
        migrations.DeleteModel(name='FugaArtistToPerson'),
        migrations.AddField(
            model_name='fugaproductassetartist',
            name='fuga_artist_id_as_int',
            field=models.BigIntegerField(
                blank=True, db_index=True, editable=False, null=True
            ),
        ),
        migrations.AddField(
            model_name='fugaproductassetartist',
            name='fuga_person_id',
            field=models.BigIntegerField(
                blank=True, db_index=True, editable=False, null=True
            ),
        ),
    ]
