# Generated by Django 2.1.9 on 2019-06-20 06:23

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('registers', '0025_auto_20190620_1213'),
    ]

    operations = [
        migrations.AlterField(
            model_name='itsystem',
            name='custody',
            field=models.PositiveSmallIntegerField(blank=True, choices=[(1, 'Migrate records and maintain for the life of agency'), (2, 'Retain in agency, migrate records to new database or transfer to SRO when superseded'), (3, 'Destroy datasets when superseded, migrate records and maintain for life of agency'), (4, 'Retain 12 months after data migration and decommission (may retain for reference)')], help_text='Period the records will be retained before they are archived or destroyed', null=True),
        ),
        migrations.AlterField(
            model_name='itsystem',
            name='disposal_action',
            field=models.PositiveSmallIntegerField(blank=True, choices=[(1, 'Retain in agency'), (2, 'Required as State Archive'), (3, 'Destroy')], help_text='Final disposal action required once the custody period has expired', null=True, verbose_name='Disposal action'),
        ),
    ]
