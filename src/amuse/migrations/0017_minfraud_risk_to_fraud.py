# Generated by Django 2.0.10 on 2019-09-06 14:25

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [('amuse', '0016_minfraud_blank_user_release')]

    operations = [
        migrations.RenameField(
            model_name='minfraudresult', old_name='risk_score', new_name='fraud_score'
        )
    ]
