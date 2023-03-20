# Generated by Django 2.2.25 on 2022-05-12 08:46

from django.db import migrations, models

UPDATE_ADMIN_ACTIVE_SQL = '''
    UPDATE releases_store
    SET admin_active = FALSE
    WHERE NOT active;
'''


class Migration(migrations.Migration):
    dependencies = [('releases', '0116_store_extra_info')]

    operations = [
        migrations.AddField(
            model_name='store',
            name='admin_active',
            field=models.BooleanField(default=True),
        ),
        migrations.RunSQL(UPDATE_ADMIN_ACTIVE_SQL),
    ]
