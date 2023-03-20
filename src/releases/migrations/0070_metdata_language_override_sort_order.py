# Generated by Django 2.0.8 on 2018-09-20 08:55

from django.db import migrations, models


def fill_sort_order(apps, schema_editor):
    MetadataLanguage = apps.get_model('releases', 'MetadataLanguage')

    for lang in MetadataLanguage.objects.all():
        sort_order = {'zxx': 25, 'en': 50, 'sv': 100}

        lang.sort_order = sort_order.get(lang.fuga_code, 999)

        lang.save()


class Migration(migrations.Migration):
    dependencies = [('releases', '0069_contributor_invitation')]

    operations = [
        migrations.AddField(
            model_name='metadatalanguage',
            name='sort_order',
            field=models.PositiveSmallIntegerField(default=999),
        ),
        migrations.AlterModelOptions(
            name='metadatalanguage', options={'ordering': ['sort_order', 'name']}
        ),
        migrations.RunPython(fill_sort_order, migrations.RunPython.noop),
    ]
