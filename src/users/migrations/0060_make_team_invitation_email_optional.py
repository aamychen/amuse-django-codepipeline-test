# Generated by Django 2.0.10 on 2019-11-22 10:38

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('users', '0059_remove_user_subscription'),
    ]

    operations = [
        migrations.AlterField(
            model_name='teaminvitation',
            name='email',
            field=models.EmailField(blank=True, max_length=120, null=True),
        ),
    ]