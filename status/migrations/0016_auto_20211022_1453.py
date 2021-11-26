# Generated by Django 2.2.24 on 2021-10-22 06:53

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('status', '0015_auto_20210517_0824'),
    ]

    operations = [
        migrations.AlterField(
            model_name='scanplugin',
            name='plugin',
            field=models.CharField(choices=[('monitor_prtg', 'Monitor - PRTG'), ('vulnerability_nessus', 'Vulnerability - Nessus'), ('backup_azure', 'Backup - Azure snapshots'), ('backup_storagesync', 'Backup - Azure Storage Sync Services'), ('patching_oms', 'Patching - Azure OMS')], max_length=32),
        ),
    ]