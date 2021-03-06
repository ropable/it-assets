# Generated by Django 2.2.14 on 2020-08-24 03:27

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('rancher', '0007_auto_20200820_1424'),
    ]

    operations = [
        migrations.AddField(
            model_name='ingress',
            name='deleted',
            field=models.DateTimeField(editable=False, null=True),
        ),
        migrations.AddField(
            model_name='namespace',
            name='deleted',
            field=models.DateTimeField(editable=False, null=True),
        ),
        migrations.AddField(
            model_name='persistentvolume',
            name='deleted',
            field=models.DateTimeField(editable=False, null=True),
        ),
        migrations.AddField(
            model_name='persistentvolumeclaim',
            name='deleted',
            field=models.DateTimeField(editable=False, null=True),
        ),
        migrations.AddField(
            model_name='workload',
            name='deleted',
            field=models.DateTimeField(editable=False, null=True),
        ),
    ]
