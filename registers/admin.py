from datetime import datetime
from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.admin import register, ModelAdmin, StackedInline, SimpleListFilter
from django.core.mail import EmailMultiAlternatives
from django.urls import path
from pytz import timezone
from reversion.admin import VersionAdmin

from .models import ITSystem, StandardChange, ChangeRequest, ChangeLog
from .views import ITSystemExport, ITSystemDiscrepancyReport, ChangeRequestExport


class ITSystemForm(forms.ModelForm):
    class Meta:
        model = ITSystem
        exclude = []

    def clean_biller_code(self):
        # Validation on the biller_code field - must be unique (ignore null values).
        data = self.cleaned_data['biller_code']
        if data and ITSystem.objects.filter(biller_code=data).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError('An IT System with this biller code already exists.')
        return data


@register(ITSystem)
class ITSystemAdmin(VersionAdmin):

    class PlatformFilter(SimpleListFilter):
        """SimpleListFilter to filter on True/False if an object has a value for platform.
        """
        title = 'platform'
        parameter_name = 'platform_boolean'

        def lookups(self, request, model_admin):
            return (
                ('true', 'Present'),
                ('false', 'Absent'),
            )

        def queryset(self, request, queryset):
            if self.value() == 'true':
                return queryset.filter(platform__isnull=False)
            if self.value() == 'false':
                return queryset.filter(platform__isnull=True)

    filter_horizontal = ('user_groups', 'dependencies')
    list_display = (
        'system_id', 'name', 'status', 'cost_centre', 'owner', 'technology_custodian', 'bh_support',
        'platform',
    )
    list_filter = (
        'status', 'system_type', 'availability', 'seasonality', 'recovery_category', PlatformFilter)
    search_fields = (
        'system_id', 'owner__username', 'owner__email', 'name', 'acronym', 'description',
        'technology_custodian__username', 'technology_custodian__email', 'link', 'documentation', 'cost_centre__code')
    raw_id_fields = (
        'owner', 'technology_custodian', 'information_custodian', 'cost_centre', 'bh_support', 'ah_support')
    fieldsets = (
        ('Overview', {
            'fields': (
                'system_id',
                ('name', 'acronym'),
                ('link', 'status'),
                ('owner', 'cost_centre'),
                ('technology_custodian', 'information_custodian'),
                ('bh_support', 'ah_support'),
                ('availability', 'seasonality'),
                'description',
                'system_type',
            )
        }),
        ('Technical information', {
            'fields': (
                ('backups', 'recovery_category'),
                ('emergency_operations', 'online_bookings', 'visitor_safety'),
                'user_notification',
                'documentation',
                'technical_documentation',
                'status_url',
                'user_groups',
                'application_server',
                'database_server',
                'network_storage',
                'system_reqs',
                'oim_internal_only',
                ('authentication', 'access'),
                'biller_code',
            )
        }),
        ('System dependencies', {
            'fields': ('platform', 'dependencies')
        }),
        ('Retention and disposal', {
            'fields': (
                'defunct_date',
                'retention_reference_no',
                'disposal_action',
                'custody',
                'retention_comments',
            )
        }),
    )
    # Override the default reversion/change_list.html template:
    change_list_template = 'admin/registers/itsystem/change_list.html'
    form = ITSystemForm  # Use the custom ModelForm.
    save_on_top = True

    def get_urls(self):
        urls = super(ITSystemAdmin, self).get_urls()
        urls = [
            path('export/', self.admin_site.admin_view(ITSystemExport.as_view()), name='itsystem_export'),
            path('discrepancies/', self.admin_site.admin_view(ITSystemDiscrepancyReport.as_view()), name='itsystem_discrepancies'),
        ] + urls
        return urls


@register(StandardChange)
class StandardChangeAdmin(ModelAdmin):
    date_hierarchy = 'created'
    filter_horizontal = ('it_systems',)
    list_display = ('id', 'name', 'endorser', 'expiry')
    raw_id_fields = ('endorser',)
    search_fields = ('id', 'name', 'endorser__email')


class ChangeLogInline(StackedInline):
    model = ChangeLog
    extra = 0
    fields = ('created', 'log')
    readonly_fields = ('created',)


class CompletionListFilter(SimpleListFilter):
    """A custom list filter to restrict displayed RFCs by completion status.
    """
    title = 'completion'
    parameter_name = 'completion'

    def lookups(self, request, model_admin):
        return (
            ('Complete', 'Complete'),
            ('Incomplete', 'Incomplete')
        )

    def queryset(self, request, queryset):
        if self.value() == 'Complete':
            return queryset.filter(completed__isnull=False)
        if self.value() == 'Incomplete':
            return queryset.filter(completed__isnull=True)


def email_endorser(modeladmin, request, queryset):
    """A custom admin action to (re)send an email to the endorser, requesting that they endorse an RFC.
    """
    for rfc in queryset:
        if rfc.is_submitted:
            rfc.email_endorser()
            msg = 'Request for approval emailed to {}.'.format(rfc.endorser.get_full_name())
            log = ChangeLog(change_request=rfc, log=msg)
            log.save()
            messages.success(request, msg)


email_endorser.short_description = 'Send email to the endorser requesting endorsement of a change'


def email_implementer(modeladmin, request, queryset):
    """A custom admin action to (re)send email to the implementer requesting that they record completion.
    """
    for rfc in queryset:
        if rfc.status == 3 and rfc.planned_end <= datetime.now().astimezone(timezone(settings.TIME_ZONE)) and rfc.completed is None:
            rfc.email_implementer()
            msg = 'Request for completion record-keeping emailed to {}.'.format(rfc.implementer.get_full_name())
            log = ChangeLog(change_request=rfc, log=msg)
            log.save()
            messages.success(request, msg)


email_implementer.short_description = 'Send email to the implementer to record completion of a finished change'


def cab_approve(modeladmin, request, queryset):
    """A custom admin action to bulk-approve RFCs at CAB.
    """
    for rfc in queryset:
        if rfc.is_scheduled:
            # Set the RFC status and record a log.
            rfc.status = 3
            rfc.save()
            msg = 'Change request {} has been approved at CAB; it may now be carried out as planned.'.format(rfc.pk)
            log = ChangeLog(change_request=rfc, log=msg)
            log.save()
            # Send an email to the requester.
            subject = 'Change request {} has been approved at CAB'.format(rfc.pk)
            detail_url = request.build_absolute_uri(rfc.get_absolute_url())
            text_content = """This is an automated message to let you know that change request
                {} ("{}") has been approved at CAB and may now be carried out as planned.\n
                Following completion, rollback or cancellation, please visit the following URL
                and record the outcome of the change:\n
                {}\n
                """.format(rfc.pk, rfc.title, detail_url)
            html_content = """<p>This is an automated message to let you know that change request
                {0} ("{1}") has been approved at CAB and may now be carried out as planned.</p>
                <p>Following completion, rollback or cancellation, please visit the following URL
                and record the outcome of the change:</p>
                <ul><li><a href="{2}">{2}</a></li></ul>
                """.format(rfc.pk, rfc.title, detail_url)
            msg = EmailMultiAlternatives(subject, text_content, settings.NOREPLY_EMAIL, [rfc.requester.email])
            msg.attach_alternative(html_content, 'text/html')
            msg.send()
            # Success notification.
            msg = 'RFC {} status set to "Ready"; requester has been emailed.'.format(rfc.pk)
            messages.success(request, msg)


cab_approve.short_description = 'Mark selected change requests as approved at CAB'


def cab_reject(modeladmin, request, queryset):
    """A custom admin action to reject RFCs at CAB.
    """
    for rfc in queryset:
        if rfc.is_scheduled:
            # Set the RFC status and record a log.
            rfc.status = 0
            rfc.save()
            msg = 'Change request {} has been rejected at CAB; status has been reset to Draft.'.format(rfc.pk)
            log = ChangeLog(change_request=rfc, log=msg)
            log.save()
            # Send an email to the requester.
            subject = 'Change request {} has been rejected at CAB'.format(rfc.pk)
            detail_url = request.build_absolute_uri(rfc.get_absolute_url())
            text_content = """This is an automated message to let you know that change request
                {} ("{}") has been rejected at CAB, and its status reset to draft.\n
                Please review any log messages recorded on the change request as context prior
                to making any required alterations and re-submission:\n
                {}\n
                """.format(rfc.pk, rfc.title, detail_url)
            html_content = """<p>This is an automated message to let you know that change request
                {0} ("{1}") has been rejected at CAB, and its status reset to draft.</p>
                <p>Please review any log messages recorded on the change request as context prior
                to making any required alterations and re-submission:</p>
                <ul><li><a href="{2}">{2}</a></li></ul>
                """.format(rfc.pk, rfc.title, detail_url)
            msg = EmailMultiAlternatives(subject, text_content, settings.NOREPLY_EMAIL, [rfc.requester.email])
            msg.attach_alternative(html_content, 'text/html')
            msg.send()
            # Success notification.
            msg = 'RFC {} status set to "Draft"; requester has been emailed.'.format(rfc.pk)
            messages.success(request, msg)


cab_reject.short_description = 'Mark selected change requests as rejected at CAB (set to draft status)'


@register(ChangeRequest)
class ChangeRequestAdmin(ModelAdmin):
    actions = [cab_approve, cab_reject, email_endorser, email_implementer]
    change_list_template = 'admin/registers/changerequest/change_list.html'
    date_hierarchy = 'planned_start'
    exclude = ('post_complete_email_date',)
    filter_horizontal = ('it_systems',)
    inlines = [ChangeLogInline]
    list_display = (
        'id', 'title', 'change_type', 'requester_name', 'endorser_name', 'implementer_name', 'status',
        'created', 'planned_start', 'planned_end', 'completed')
    list_filter = ('change_type', 'status', CompletionListFilter)
    raw_id_fields = ('requester', 'endorser', 'implementer')
    search_fields = (
        'id', 'title', 'requester__email', 'endorser__email', 'implementer__email', 'implementation',
        'communication', 'reference_url')

    def requester_name(self, obj):
        if obj.requester:
            return obj.requester.get_full_name()
        return ''
    requester_name.short_description = 'requester'

    def endorser_name(self, obj):
        if obj.endorser:
            return obj.endorser.get_full_name()
        return ''
    endorser_name.short_description = 'endorser'

    def implementer_name(self, obj):
        if obj.implementer:
            return obj.implementer.get_full_name()
        return ''
    implementer_name.short_description = 'implementer'

    def get_urls(self):
        urls = super(ChangeRequestAdmin, self).get_urls()
        urls = [path('export/', self.admin_site.admin_view(ChangeRequestExport.as_view()), name='changerequest_export')] + urls
        return urls
