# Generated by Django 2.0.8 on 2018-10-12 07:46

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [('releases', '0071_releaseartist')]

    operations = [
        migrations.AlterModelOptions(name='contributor', options={'ordering': ['id']}),
        migrations.AlterModelOptions(
            name='contributorrole', options={'ordering': ['id']}
        ),
    ]