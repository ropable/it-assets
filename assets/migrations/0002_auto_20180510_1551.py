# Generated by Django 2.0.4 on 2018-05-10 07:51

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('assets', '0001_initial'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='hardwaremodel',
            options={'ordering': ('model_no',)},
        ),
        migrations.AlterUniqueTogether(
            name='hardwaremodel',
            unique_together={('vendor', 'model_no')},
        ),
    ]
