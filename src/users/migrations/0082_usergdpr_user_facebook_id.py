# Generated by Django 2.0.13 on 2020-10-14 14:56

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('users', '0081_usergdpr_user_apple_signin_id'),
    ]

    operations = [
        migrations.AddField(
            model_name='usergdpr',
            name='user_facebook_id',
            field=models.BooleanField(default=False),
        ),
    ]
