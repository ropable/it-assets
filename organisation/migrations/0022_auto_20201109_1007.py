# Generated by Django 2.2.16 on 2020-11-09 02:07

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('organisation', '0021_auto_20201104_1252'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='orgunit',
            name='level',
        ),
        migrations.RemoveField(
            model_name='orgunit',
            name='lft',
        ),
        migrations.RemoveField(
            model_name='orgunit',
            name='parent',
        ),
        migrations.RemoveField(
            model_name='orgunit',
            name='rght',
        ),
        migrations.RemoveField(
            model_name='orgunit',
            name='tree_id',
        ),
    ]
