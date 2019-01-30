
from django.contrib.postgres.fields import JSONField
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.html import format_html

import datetime


class ScanRange(models.Model):
    name = models.CharField(max_length=256)
    range = models.CharField(max_length=2048)
    enabled = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class ScanPlugin(models.Model):
    PLUGIN_CHOICES = (
        ('monitor_prtg', 'Monitor - PRTG'),
        ('vulnerability_nessus', 'Vulnerability - Nessus'),
        ('backup_acronis', 'Backup - Acronis'),
        ('backup_aws', 'Backup - AWS snapshots'),
        ('backup_azure', 'Backup - Azure snapshots'),
        ('backup_veeam', 'Backup - Veeam'),
        ('backup_restic', 'Backup - Restic'),
        ('patching_oms', 'Patching - Azure OMS'),
    )
    PLUGIN_PARAMS = {
        'monitor_prtg': ('PRTG_BASE', 'PRTG_USERNAME', 'PRTG_PASSHASH', 'PRTG_URL'),
        'vulnerability_nessus': ('NESSUS_BASE', 'NESSUS_ACCESS_KEY', 'NESSUS_SECRET_KEY', 'NESSUS_SCAN_FOLDER', 'NESSUS_URL'),
        'backup_acronis': ('ACRONIS_BASE', 'ACRONIS_USERNAME', 'ACRONIS_PASSWORD', 'ACRONIS_URL'),
        'patching_oms': ('AZURE_TENANT', 'AZURE_APP_ID', 'AZURE_APP_KEY', 'AZURE_LOG_WORKSPACE'),
    }

    name = models.CharField(max_length=256)
    plugin = models.CharField(max_length=32, choices=PLUGIN_CHOICES)
    enabled = models.BooleanField(default=True)

    def run(self, date=None):
        import status.plugins as plugins
        if date is None:
            date = datetime.date.today()
        if hasattr(plugins, self.plugin):
            getattr(plugins, self.plugin)(self, date)
        else:
            print('STUB: {}'.format(self.plugin))

    def __str__(self):
        return self.name
    

class ScanPluginParameter(models.Model):
    scan_plugin = models.ForeignKey(ScanPlugin, on_delete=models.CASCADE, related_name='params')
    name = models.CharField(max_length=256)
    value = models.CharField(max_length=2048, blank=True)

    class Meta:
        unique_together = ('scan_plugin', 'name')

@receiver(post_save, sender=ScanPlugin)
def scan_plugin_post_save(sender, signal, instance, **kwargs):
    if instance.plugin in ScanPlugin.PLUGIN_PARAMS:
        for param in ScanPlugin.PLUGIN_PARAMS[instance.plugin]:
            obj, _ = ScanPluginParameter.objects.get_or_create(scan_plugin=instance, name=param)
            obj.save()


class Host(models.Model):
    TYPE_CHOICES = (
        (0, 'Server'),
        (1, 'Embedded device'),
    )
    name = models.CharField(max_length=256)
    type = models.SmallIntegerField(choices=TYPE_CHOICES, default=0)

    def __str__(self):
        return self.name

class HostStatus(models.Model):
    STATUS_CHOICES = (
        (0, 'N/A'),
        (1, 'Failure'),
        (2, 'Unhealthy'),
        (3, 'OK'),
    )

    STATUS_COLOURS = {
        0: ('inherit', 'inherit'),
        1: ('#fcd8d8', '#6f0000'),
        2: ('#fedfb3', '#8d3f00'),
        3: ('#ddf7c5', '#376d04'),
    }

    host = models.ForeignKey(Host, on_delete=models.CASCADE, related_name='statuses')
    date = models.DateField()

    ping_status = models.SmallIntegerField(choices=STATUS_CHOICES, default=0)
    ping_scan_range = models.ForeignKey(ScanRange, null=True, on_delete=models.SET_NULL, related_name='hosts')
    ping_url = None

    monitor_status = models.SmallIntegerField(choices=STATUS_CHOICES, default=0)
    monitor_info = JSONField(default=dict)
    monitor_url = models.URLField(max_length=256, null=True)

    vulnerability_status = models.SmallIntegerField(choices=STATUS_CHOICES, default=0)
    vulnerability_info = JSONField(default=dict)
    vulnerability_url = models.URLField(max_length=256, null=True)

    backup_status = models.SmallIntegerField(choices=STATUS_CHOICES, default=0)
    backup_info = JSONField(default=dict)
    backup_url = models.URLField(max_length=256, null=True)

    patching_status = models.SmallIntegerField(choices=STATUS_CHOICES, default=0)
    patching_info = JSONField(default=dict)
    patching_url = models.URLField(max_length=256, null=True)

    # HTML rendered statuses for the admin list view
    def _status_html(self, prefix):
        status = getattr(self, '{}_status'.format(prefix))
        status_url = getattr(self, '{}_url'.format(prefix))
        status_name = getattr(self, 'get_{}_status_display'.format(prefix))()
        if status_url:
            return format_html('<div style="text-align: center; font-weight: bold; background-color: {}; color: {}; border-radius: 2px;"><a href="{}">{}</a></div>',
                *self.STATUS_COLOURS[status],
                status_url,
                status_name,
            )
        return format_html('<div style="text-align: center; font-weight: bold; background-color: {}; color: {}; border-radius: 2px;">{}</div>',
            *self.STATUS_COLOURS[status],
            status_name
        )

    def ping_status_html(self):
        return self._status_html('ping')
    ping_status_html.admin_order_field = 'ping_status'
    ping_status_html.short_description = 'Ping'

    def monitor_status_html(self):
        return self._status_html('monitor')
    monitor_status_html.admin_order_field = 'monitor_status'
    monitor_status_html.short_description = 'Monitor'

    def vulnerability_status_html(self):
        return self._status_html('vulnerability')
    vulnerability_status_html.admin_order_field = 'vulnerability_status'
    vulnerability_status_html.short_description = 'Vulnerability'

    def backup_status_html(self):
        return self._status_html('backup')
    backup_status_html.admin_order_field = 'backup_status'
    backup_status_html.short_description = 'Backup'

    def patching_status_html(self):
        return self._status_html('patching')
    patching_status_html.admin_order_field = 'patching_status'
    patching_status_html.short_description = 'Patching'

    def __str__(self):
        return '{} - {}'.format(self.host.name, self.date.isoformat())


class HostIP(models.Model):
    ip = models.GenericIPAddressField(unique=True)
    last_seen = models.DateTimeField(auto_now=True)
    host = models.ForeignKey(Host, on_delete=models.CASCADE, related_name='host_ips')

    def __str__(self):
        return self.ip
