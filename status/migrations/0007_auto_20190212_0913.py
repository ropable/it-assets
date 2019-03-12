# Generated by Django 2.1.5 on 2019-02-12 01:13

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('status', '0006_auto_20190131_1447'),
    ]

    operations = [
        migrations.AlterField(
            model_name='hoststatus',
            name='backup_status',
            field=models.SmallIntegerField(choices=[(0, 'N/A'), (1, 'No record'), (2, 'Unhealthy'), (3, 'OK')], default=0),
        ),
        migrations.AlterField(
            model_name='hoststatus',
            name='monitor_status',
            field=models.SmallIntegerField(choices=[(0, 'N/A'), (1, 'No record'), (2, 'Unhealthy'), (3, 'OK')], default=0),
        ),
        migrations.AlterField(
            model_name='hoststatus',
            name='patching_status',
            field=models.SmallIntegerField(choices=[(0, 'N/A'), (1, 'No record'), (2, 'Unhealthy'), (3, 'OK')], default=0),
        ),
        migrations.AlterField(
            model_name='hoststatus',
            name='ping_status',
            field=models.SmallIntegerField(choices=[(0, 'N/A'), (1, 'No record'), (2, 'Unhealthy'), (3, 'OK')], default=0),
        ),
        migrations.AlterField(
            model_name='hoststatus',
            name='vulnerability_status',
            field=models.SmallIntegerField(choices=[(0, 'N/A'), (1, 'No record'), (2, 'Unhealthy'), (3, 'OK')], default=0),
        ),
    ]