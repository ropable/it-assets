# Generated by Django 2.2.16 on 2020-12-02 05:51

import django.contrib.postgres.fields.jsonb
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('organisation', '0024_auto_20201202_1110'),
    ]

    operations = [
        migrations.RenameField(
            model_name='departmentuser',
            old_name='alesco_data',
            new_name='ascender_data',
        ),
        migrations.RenameField(
            model_name='departmentuser',
            old_name='alesco_data_updated',
            new_name='ascender_data_updated',
        ),
    ]
