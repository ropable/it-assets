# Generated by Django 2.2.27 on 2022-03-03 02:59

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('organisation', '0010_auto_20211206_0739'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='departmentuser',
            name='username',
        ),
        migrations.RemoveField(
            model_name='departmentuser',
            name='working_hours',
        ),
    ]
