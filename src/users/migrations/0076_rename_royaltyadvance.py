# Generated by Django 2.0.13 on 2020-07-01 10:12

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('users', '0075_otpdevice_is_verified')]

    operations = [migrations.RenameModel('RoyaltyAdvance', 'LegacyRoyaltyAdvance')]
