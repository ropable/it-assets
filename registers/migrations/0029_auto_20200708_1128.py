# Generated by Django 2.2.14 on 2020-07-08 03:28

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('registers', '0028_auto_20200706_1209'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='itsystem',
            name='platforms',
        ),
        migrations.DeleteModel(
            name='Platform',
        ),
    ]
