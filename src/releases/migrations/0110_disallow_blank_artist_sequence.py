# Generated by Django 2.1.15 on 2021-03-31 08:45

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('releases', '0109_releasestoreshistory'),
    ]

    operations = [
        migrations.AlterField(
            model_name='releaseartistrole',
            name='artist_sequence',
            field=models.SmallIntegerField(null=True),
        ),
        migrations.AlterField(
            model_name='songartistrole',
            name='artist_sequence',
            field=models.SmallIntegerField(null=True),
        ),
    ]
