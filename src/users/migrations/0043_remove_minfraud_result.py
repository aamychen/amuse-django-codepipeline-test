from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('users', '0042_auto_20190729_0855'),
        ('amuse', '0014_minfraud_result'),
    ]

    operations = [
        migrations.RemoveField(model_name='minfraudresult', name='user'),
        migrations.DeleteModel(name='MinfraudResult'),
    ]
