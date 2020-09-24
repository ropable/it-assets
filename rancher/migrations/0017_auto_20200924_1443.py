# Generated by Django 2.2.16 on 2020-09-24 06:43

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('rancher', '0016_auto_20200924_1354'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='ingressrule',
            unique_together={('ingress', 'protocol', 'hostname', 'path'), ('ingress', 'servicename')},
        ),
        migrations.AlterUniqueTogether(
            name='workloadlistening',
            unique_together={('workload', 'servicename', 'ingress_rule')},
        ),
        migrations.AlterIndexTogether(
            name='ingressrule',
            index_together={('cluster', 'servicename')},
        ),
    ]
