import traceback
import logging

from django.contrib import admin
from django.contrib import messages
from django.utils.html import format_html, mark_safe
from django.urls import reverse

from django_q.tasks import async_task

# Register your models here.
from . import models
from . import rancher_harvester
from nginx.models import WebApp

logger = logging.getLogger(__name__)


class ClusterLinkMixin(object):
    cluster_change_url_name = 'admin:{}_{}_change'.format(models.Cluster._meta.app_label,models.Cluster._meta.model_name)
    get_cluster = staticmethod(lambda obj:obj.cluster)

    def _cluster(self,obj):
        if not obj :
            return ""
        else:
            cluster = self.get_cluster(obj)
            url = reverse(self.cluster_change_url_name, args=(cluster.id,))
            return mark_safe("<A href='{}'>{}</A>".format(url,cluster.name))
    _cluster.short_description = "Cluster"


class ProjectLinkMixin(object):
    project_change_url_name = 'admin:{}_{}_change'.format(models.Project._meta.app_label,models.Project._meta.model_name)
    get_project = staticmethod(lambda obj:obj.project)

    def _project(self,obj):
        if not obj :
            return ""
        else:
            project = self.get_project(obj)
            url = reverse(self.project_change_url_name, args=(project.id,))
            return mark_safe("<A href='{}'>{}</A>".format(url,project.name or project.projectid))
    _project.short_description = "Project"


class NamespaceLinkMixin(object):
    namespace_change_url_name = 'admin:{}_{}_change'.format(models.Namespace._meta.app_label,models.Namespace._meta.model_name)
    get_namespace = staticmethod(lambda obj:obj.namespace)
    def _namespace(self,obj):
        if not obj :
            return ""
        else:
            namespace = self.get_namespace(obj)
            url = reverse(self.namespace_change_url_name, args=(namespace.id,))
            return mark_safe("<A href='{}'>{}</A>".format(url,namespace.name))
    _namespace.short_description = "Namespace"


class VolumeLinkMixin(object):
    volume_change_url_name = 'admin:{}_{}_change'.format(models.PersistentVolume._meta.app_label,models.PersistentVolume._meta.model_name)
    get_volume = staticmethod(lambda obj:obj.volume)
    def _volume(self,obj):
        if not obj or not obj.volume:
            return ""
        else:
            volume = self.get_volume(obj)
            url = reverse(self.volume_change_url_name, args=(volume.id,))
            return mark_safe("<A href='{}'>volume</A>".format(url))
    _volume.short_description = "Volume"


class DatabaseLinkMixin(object):
    database_change_url_name = 'admin:{}_{}_change'.format(models.Database._meta.app_label,models.Database._meta.model_name)
    get_database = staticmethod(lambda obj:obj.database)
    def _database(self,obj):
        if not obj :
            return ""
        else:
            database = self.get_database(obj)
            url = reverse(self.database_change_url_name, args=(database.id,))
            return mark_safe("<A href='{}'>{}</A>".format(url,database.name))
    _database.short_description = "Database"


class WorkloadLinkMixin(object):
    workload_change_url_name = 'admin:{}_{}_change'.format(models.Workload._meta.app_label,models.Workload._meta.model_name)
    get_workload = staticmethod(lambda obj:obj.workload)
    def _workload(self,obj):
        """
        Used for foreign key
        """
        if not obj :
            return ""
        else:
            workload = self.get_workload(obj)
            if workload.is_deleted:
                return mark_safe("<A href='{}'>{}</A>".format(url,workload.name))
            else:
                url = reverse(self.workload_change_url_name, args=(workload.id,))
                return mark_safe("<A href='{}'>{}</A><A href='{}' style='margin-left:50px' target='manage_workload'><img src='/static/img/view.jpg' width=16 height=16></A><A href='{}' target='manage_workload' style='margin-left:20px'><img src='/static/img/setting.jpg' width=16 height=16></A>".format(url,workload.name,workload.viewurl,workload.managementurl))
    _workload.short_description = "Workload"

    def _manage(self,obj):
        if not obj :
            return ""
        else:
            workload = self.get_workload(obj)
            if workload.is_deleted:
                return ""
            else:
                return mark_safe("<A href='{}' target='manage_workload'><img src='/static/img/view.jpg' width=16 height=16></A><A href='{}' target='manage_workload' style='margin-left:20px'><img src='/static/img/setting.jpg' width=16 height=16></A>".format(workload.viewurl,workload.managementurl))
    _manage.short_description = ""

    def _name(self,workload):
        if not workload :
            return ""
        elif workload.is_deleted:
            return workload.name
        else:
            return mark_safe("{}<A href='{}' style='margin-left:50px' target='manage_workload'><img src='/static/img/view.jpg' width=16 height=16></A><A href='{}' target='manage_workload' style='margin-left:20px'><img src='/static/img/setting.jpg' width=16 height=16></A>".format(workload.name,workload.viewurl,workload.managementurl))
    _name.short_description = "Name"

    def _name_with_link(self,obj):
        return self._workload(obj)
    _name_with_link.short_description = "Name"


class WorkloadInlineMixin(ClusterLinkMixin,ProjectLinkMixin,NamespaceLinkMixin,WorkloadLinkMixin):
    readonly_fields = ('_workload','_cluster','_project','_namespace','user',"password",'config_items')
    fields = readonly_fields
    ordering = ('workload',)

    def has_change_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(models.Cluster)
class ClusterAdmin(admin.ModelAdmin):
    list_display = ('name','ip', 'clusterid','succeed_resources','failed_resources','refreshed','modified')
    readonly_fields = ('ip','clusterid','succeed_resources','failed_resources','refreshed','modified','created','_refresh_message')
    ordering = ('name',)
    actions = ('refresh','enforce_refresh')

    def _refresh_message(self,obj):
        if not obj :
            return ""
        else:
            return mark_safe("<pre>{}</pre>".format(obj.refresh_message))
    _refresh_message.short_description = "Refresh Message"

    def has_add_permission(self, request, obj=None):
        return True

    def has_delete_permission(self, request, obj=None):
        return False

    def enforce_refresh(self, request, queryset):
        for cluster in queryset:
            try:
                async_task("rancher.rancher_harvester.harvest",cluster,reconsume=True)
                self.message_user(request, "The process to harvest all configuration files of the cluster({}) has been scheduled.".format(cluster))
            except Exception as ex:
                self.message_user(request, "Failed to schedule the process to harvest all configuration files of the cluster({}).{}".format(cluster,str(ex)),level=messages.ERROR)

    enforce_refresh.short_description = 'Enforce refresh'

    def refresh(self, request, queryset):
        for cluster in queryset:
            try:
                async_task("rancher.rancher_harvester.harvest",cluster)
                self.message_user(request, "The process to harvest the changed configuration files of the cluster({}) has been scheduled.".format(cluster))
            except Exception as ex:
                self.message_user(request, "Failed to schedule the process to harvest the changed configuration files of the cluster({}).{}".format(cluster,str(ex)),level=messages.ERROR)

    refresh.short_description = 'Refresh'

class DeletedMixin(object):
    def _deleted(self,obj):
        if not obj :
            return ""
        elif obj.deleted:
            return mark_safe("<img src='/static/admin/img/icon-yes.svg'> {}".format(obj.deleted))
        else:
            return mark_safe("<img src='/static/admin/img/icon-no.svg'>")
    _deleted.short_description = "Deleted"


@admin.register(models.Project)
class ProjectAdmin(ClusterLinkMixin,admin.ModelAdmin):
    list_display = ('projectid','_cluster','name')
    readonly_fields = ('projectid','_cluster')
    fields = ('projectid','_cluster','name')
    ordering = ('cluster__name','name',)
    list_filter = ('cluster',)

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class WorkloadInline(DeletedMixin,WorkloadLinkMixin,admin.TabularInline):
    model = models.Workload
    readonly_fields = ('_name_with_link', 'kind','image',"modified","_deleted")
    fields = readonly_fields
    ordering = ('name',)
    get_workload = staticmethod(lambda obj:obj)

    def has_change_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

class DeletedFilter(admin.SimpleListFilter):
    # Human-readable title which will be displayed in the
    # right admin sidebar just above the filter options.
    title = 'Existing Status'

    # Parameter for the filter that will be used in the URL query.
    parameter_name = 'is_deleted'

    def lookups(self, request, model_admin):
        """
        Returns a list of tuples. The first element in each
        tuple is the coded value for the option that will
        appear in the URL query. The second element is the
        human-readable name for the option that will appear
        in the right sidebar.
        """
        return [(False,"Existing"),(True,"Deleted")]


    def queryset(self, request, queryset):
        """
        Returns the filtered queryset based on the value
        provided in the query string and retrievable via
        `self.value()`.
        """
        # Compare the requested value (either '80s' or '90s')
        # to decide how to filter the queryset.
        val = self.value()
        if not val:
            return queryset
        elif val == 'True':
            return queryset.filter(deleted__isnull=False)
        else:
            return queryset.filter(deleted__isnull=True)

@admin.register(models.Namespace)
class NamespaceAdmin(DeletedMixin,ClusterLinkMixin,ProjectLinkMixin,admin.ModelAdmin):
    list_display = ('name','_cluster','_project','_deleted')
    readonly_fields = ('name','_cluster','_project','_deleted')
    fields = readonly_fields
    ordering = ('cluster__name','project__name','name')
    list_filter = ('project',DeletedFilter)

    inlines = [WorkloadInline]

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


class WorkloadVolumeInline(DeletedMixin,WorkloadInlineMixin,admin.TabularInline):
    model = models.WorkloadVolume
    readonly_fields = ('_workload','_cluster','_project','_namespace','_deleted')
    fields = readonly_fields
    ordering = ('workload',)
    get_cluster = staticmethod(lambda obj:obj.workload.cluster)
    get_project = staticmethod(lambda obj:obj.workload.project)
    get_namespace = staticmethod(lambda obj:obj.workload.namespace)


@admin.register(models.PersistentVolume)
class PersistentVolumeAdmin(DeletedMixin,ClusterLinkMixin,admin.ModelAdmin):
    list_display = ('name','_cluster', 'kind','storage_class_name','volumepath','_capacity','writable',"modified",'_deleted')
    readonly_fields = ('name','_cluster', 'kind','storage_class_name','volumepath','_capacity',"volume_mode","uuid",'writable','reclaim_policy','_node_affinity',"modified","created",'_deleted')
    ordering = ('cluster','name',)
    list_filter = ('cluster',DeletedFilter)
    inlines = [WorkloadVolumeInline]

    def _capacity(self,obj):
        if not obj :
            return ""
        if obj.capacity > 1024:
            if obj.capacity % 1024 == 0:
                return "{}G".format(int(obj.capacity / 1024))
            else:
                return "{}G".format(round(obj.capacity / 1024),2)
        else:
            return "{}M".format(obj.capacity)
    _capacity.short_description = "Capacity"

    def _node_affinity(self,obj):
        if not obj :
            return ""
        else:
            return mark_safe("<pre>{}</pre>".format(obj.node_affinity))
    _node_affinity.short_description = "Node Affinity"

    def has_change_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class WorkloadEnvInline(admin.TabularInline):
    readonly_fields = ('name','value','modified','created')
    fields = ('name','value','modified')
    model = models.WorkloadEnv
    classes = ["collapse"]

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class WorkloadListeningInline(DeletedMixin,admin.TabularInline):
    readonly_fields = ('_listen','protocol','container_port','modified','_deleted')
    fields = ('_listen','protocol','container_port','modified','_deleted')
    model = models.WorkloadListening
    classes = ["collapse"]

    def _listen(self,obj):
        if not obj :
            return ""
        else:
            return obj.listen
    _listen.short_description = "Listen"

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class WorkloadVolumeInline(DeletedMixin,VolumeLinkMixin,admin.TabularInline):
    readonly_fields = ('name','mountpath','subpath','writable','volumepath','_capacity','_volume','_other_config','_deleted')
    fields = ('name','mountpath','subpath','writable','volumepath','_capacity','_volume','_other_config','_deleted')
    model = models.WorkloadVolume
    classes = ["collapse"]

    def _other_config(self,obj):
        if not obj :
            return ""
        elif obj.other_config:
            return mark_safe("<pre>{}</pre>".format(obj.other_config))
        else:
            return ""
    _other_config.short_description = "Other Config"

    def _capacity(self,obj):
        if not obj or not obj.volume:
            return ""
        else:
            return "{}G".format(obj.volume.capacity)
    _capacity.short_description = "Capacity"

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class WorkloadDatabaseInline1(DeletedMixin,DatabaseLinkMixin,admin.TabularInline):
    model = models.WorkloadDatabase
    readonly_fields = ('_server','_port','_database','schema','user',"password",'config_items','_deleted')
    fields = readonly_fields
    ordering = ('workload',)

    def _server(self,obj):
        if not obj :
            return ""
        else:
            return obj.database.server.host
    _server.short_description = "Server"

    def _port(self,obj):
        if not obj :
            return ""
        else:
            return obj.database.server.port
    _port.short_description = "Port"

    def has_change_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(models.Workload)
class WorkloadAdmin(DeletedMixin,ClusterLinkMixin, ProjectLinkMixin, NamespaceLinkMixin, WorkloadLinkMixin, admin.ModelAdmin):
    list_display = ('_manage', 'name', '_cluster', '_project', '_namespace', 'kind', 'image', '_image_vulns_str', 'modified','_deleted')
    list_display_links = ('name',)
    readonly_fields = ('_name', '_cluster', '_project', '_namespace', 'kind', 'image', '_webapps', 'modified')
    fields = ('_name', '_cluster', '_project', '_namespace', 'kind', 'image', '_image_vulns_str', 'image_scan_timestamp', '_webapps', 'modified','_deleted')
    ordering = ('cluster__name', 'project__name', 'namespace__name', 'name',)
    list_filter = ('cluster',DeletedFilter, 'namespace', 'kind')
    search_fields = ['name', 'project__name', 'namespace__name']
    get_workload = staticmethod(lambda obj: obj)

    inlines = [WorkloadDatabaseInline1, WorkloadListeningInline, WorkloadEnvInline, WorkloadVolumeInline]
    webapp_change_url_name = 'admin:{}_{}_change'.format(WebApp._meta.app_label, WebApp._meta.model_name)

    def _webapps(self, obj):
        if not obj:
            return ""
        else:
            apps = obj.webapps
            if apps:
                result = None
                for app in apps:
                    url = reverse(self.webapp_change_url_name, args=(app.id,))
                    if result:
                        result = "{}\n<A href='{}'>{}</A>".format(result, url, app.name)
                    else:
                        result = "<A href='{}'>{}</A>".format(url, app.name)
                return mark_safe("<pre>{}</pre>".format(result))
            else:
                return ""
    _webapps.short_description = "Web Applications"

    def has_change_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class WorkloadDatabaseInline2(DeletedMixin,WorkloadInlineMixin,admin.TabularInline):
    model = models.WorkloadDatabase
    readonly_fields = ('_workload','_cluster','_project','_namespace','user',"password",'config_items','_deleted')
    fields = readonly_fields
    ordering = ('workload',)
    get_cluster = staticmethod(lambda obj:obj.workload.cluster)
    get_project = staticmethod(lambda obj:obj.workload.project)
    get_namespace = staticmethod(lambda obj:obj.workload.namespace)


@admin.register(models.Database)
class DatabaseAdmin(admin.ModelAdmin):
    list_display = ('name','_server','_ip','_internal_name','_internal_port')
    readonly_fields = ('name','_server_name','_ip','_internal_name','_internal_port','_workload')
    ordering = ('server__host','name')
    list_filter = ('server','name')
    search_fields = ['name']

    inlines = [WorkloadDatabaseInline2]

    def _ip(self,obj):
        if not obj :
            return ""
        else:
            return obj.server.ip
    _ip.short_description = "IP"

    def _server_name(self,obj):
        if not obj :
            return ""
        elif obj.server.other_names:
            return "{} :[{}]".format(obj.server.host," , ".join(obj.server.other_names))
        else:
            return obj.server.host
    _server_name.short_description = "Server"

    def _server(self,obj):
        if not obj :
            return ""
        elif obj.server.other_names:
            return "{} , {}".format(obj.server.host," , ".join(obj.server.other_names))
        else:
            return obj.server.host
    _server.short_description = "server"

    def _internal_name(self,obj):
        if not obj :
            return ""
        else:
            return obj.server.internal_name
    _internal_name.short_descrinternal_nametion = "Internal Name"

    def _internal_port(self,obj):
        if not obj :
            return ""
        else:
            return obj.server.internal_port
    _internal_port.short_descrinternal_porttion = "Internal Port"

    workload_change_url_name = 'admin:{}_{}_change'.format(models.Workload._meta.app_label,models.Workload._meta.model_name)
    def _workload(self,obj):
        if not obj :
            return ""
        elif not obj.server.workload:
            return ""
        else:
            url = reverse(self.workload_change_url_name, args=(obj.server.workload.id,))
            return mark_safe("<A href='{}'>{}</A><A href='{}' style='margin-left:50px' target='manage_workload'><img src='/static/img/view.jpg' width=16 height=16></A><A href='{}' target='manage_workload' style='margin-left:20px'><img src='/static/img/setting.jpg' width=16 height=16></A>".format(url,obj.server.workload.name,obj.server.workload.viewurl,obj.server.workload.managementurl))
    _workload.short_description = "Workload"

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False
