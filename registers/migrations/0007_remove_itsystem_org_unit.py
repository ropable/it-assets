# Generated by Django 3.2.16 on 2022-11-14 02:49

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('registers', '0006_auto_20221103_1456'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='itsystem',
            name='org_unit',
        ),
    ]