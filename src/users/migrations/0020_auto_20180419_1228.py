# -*- coding: utf-8 -*-
# Generated by Django 1.9.3 on 2018-04-19 12:28
from __future__ import unicode_literals

import amuse.storages
from django.conf import settings
from django.db import migrations, models
import users.models


class Migration(migrations.Migration):
    dependencies = [('users', '0019_user_email_not_null')]

    operations = [
        migrations.AlterField(
            model_name='transactionfile',
            name='file',
            field=models.FileField(
                storage=amuse.storages.S3Storage(
                    bucket_name=settings.AWS_TRANSACTION_FILE_BUCKET_NAME
                ),
                upload_to=users.models.transaction_file_upload_path,
            ),
        )
    ]
