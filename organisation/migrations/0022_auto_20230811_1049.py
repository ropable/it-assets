# Generated by Django 3.2.20 on 2023-08-11 02:49

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('organisation', '0021_auto_20230222_0902'),
    ]

    operations = [
        migrations.AddField(
            model_name='departmentuser',
            name='maiden_name',
            field=models.CharField(blank=True, help_text='Optional maiden name value, for the purposes of setting display name', max_length=128, null=True),
        ),
        migrations.AlterField(
            model_name='departmentuser',
            name='name',
            field=models.CharField(help_text='Display name within AD / Outlook', max_length=128, verbose_name='display name'),
        ),
    ]
