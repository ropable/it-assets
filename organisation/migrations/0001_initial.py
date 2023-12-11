# Generated by Django 3.2.20 on 2023-08-29 01:45

import django.contrib.gis.db.models.fields
import django.contrib.postgres.fields
import django.contrib.postgres.fields.citext
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='AscenderActionLog',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('level', models.CharField(choices=[('INFO', 'INFO'), ('WARNING', 'WARNING'), ('ERROR', 'ERROR')], editable=False, max_length=64)),
                ('log', models.CharField(editable=False, max_length=512)),
                ('ascender_data', models.JSONField(blank=True, default=dict, editable=False, null=True)),
            ],
            options={
                'ordering': ('-created',),
            },
        ),
        migrations.CreateModel(
            name='CostCentre',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('active', models.BooleanField(default=True)),
                ('code', models.CharField(max_length=16, unique=True)),
                ('chart_acct_name', models.CharField(blank=True, max_length=256, null=True, verbose_name='chart of accounts name')),
                ('division_name', models.CharField(blank=True, choices=[('BCS', 'DBCA Biodiversity and Conservation Science'), ('BGPA', 'Botanic Gardens and Parks Authority'), ('CBS', 'DBCA Corporate and Business Services'), ('CPC', 'Conservation and Parks Commission'), ('ODG', 'Office of the Director General'), ('PWS', 'Parks and Wildlife Service'), ('RIA', 'Rottnest Island Authority'), ('ZPA', 'Zoological Parks Authority')], max_length=128, null=True)),
                ('ascender_code', models.CharField(blank=True, max_length=16, null=True, unique=True)),
            ],
            options={
                'ordering': ('code',),
            },
        ),
        migrations.CreateModel(
            name='DepartmentUser',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date_created', models.DateTimeField(auto_now_add=True)),
                ('date_updated', models.DateTimeField(auto_now=True)),
                ('active', models.BooleanField(default=True, editable=False, help_text='Account is enabled within Active Directory.')),
                ('email', django.contrib.postgres.fields.citext.CIEmailField(editable=False, help_text='Account email address', max_length=254, unique=True)),
                ('name', models.CharField(help_text='Display name within AD / Outlook', max_length=128, verbose_name='display name')),
                ('given_name', models.CharField(blank=True, help_text='First name', max_length=128, null=True)),
                ('surname', models.CharField(blank=True, help_text='Last name', max_length=128, null=True)),
                ('preferred_name', models.CharField(blank=True, max_length=256, null=True)),
                ('maiden_name', models.CharField(blank=True, help_text='Optional maiden name value, for the purposes of setting display name', max_length=128, null=True)),
                ('title', models.CharField(blank=True, help_text='Occupation position title (should match Ascender position title)', max_length=128, null=True)),
                ('telephone', models.CharField(blank=True, help_text='Work telephone number', max_length=128, null=True)),
                ('mobile_phone', models.CharField(blank=True, help_text='Work mobile number', max_length=128, null=True)),
                ('proxy_addresses', django.contrib.postgres.fields.ArrayField(base_field=models.CharField(blank=True, max_length=254), blank=True, help_text='Email aliases', null=True, size=None)),
                ('assigned_licences', django.contrib.postgres.fields.ArrayField(base_field=models.CharField(blank=True, max_length=254), blank=True, help_text='Assigned Microsoft 365 licences', null=True, size=None)),
                ('extension', models.CharField(blank=True, max_length=128, null=True, verbose_name='VoIP extension')),
                ('home_phone', models.CharField(blank=True, max_length=128, null=True)),
                ('other_phone', models.CharField(blank=True, max_length=128, null=True)),
                ('name_update_reference', models.CharField(blank=True, help_text='Reference for name/CC change request', max_length=512, null=True, verbose_name='update reference')),
                ('vip', models.BooleanField(default=False, help_text='An individual who carries out a critical role for the department')),
                ('executive', models.BooleanField(default=False, help_text='An individual who is an executive')),
                ('contractor', models.BooleanField(default=False, help_text='An individual who is an external contractor (does not include agency contract staff)')),
                ('notes', models.TextField(blank=True, help_text='Records relevant to any AD account extension, expiry or deletion (e.g. ticket #).', null=True)),
                ('account_type', models.PositiveSmallIntegerField(blank=True, choices=[(2, 'L1 User Account - Permanent'), (3, 'L1 User Account - Agency contract'), (0, 'L1 User Account - Department fixed-term contract'), (8, 'L1 User Account - Seasonal'), (6, 'L1 User Account - Vendor'), (7, 'L1 User Account - Volunteer'), (1, 'L1 User Account - Other/Alumni'), (11, 'L1 User Account - RoomMailbox'), (12, 'L1 User Account - EquipmentMailbox'), (10, 'L2 Service Account - System'), (5, 'L1 Group (shared) Mailbox - Shared account'), (9, 'L1 Role Account - Role-based account'), (4, 'Terminated'), (14, 'Unknown - AD disabled'), (15, 'Cleanup - Permanent'), (16, 'Unknown - AD active')], help_text='Employee network account status', null=True)),
                ('security_clearance', models.BooleanField(default=False, help_text='Security clearance approved by CC Manager (confidentiality\n        agreement, referee check, police clearance, etc.', verbose_name='security clearance granted')),
                ('shared_account', models.BooleanField(default=False, editable=False, help_text='Automatically set from account type.')),
                ('employee_id', models.CharField(blank=True, help_text='Ascender employee number', max_length=128, null=True, unique=True, verbose_name='Employee ID')),
                ('ascender_data', models.JSONField(blank=True, default=dict, editable=False, help_text='Cache of staff Ascender data', null=True)),
                ('ascender_data_updated', models.DateTimeField(editable=False, help_text='Timestamp of when Ascender data was last updated for this user', null=True)),
                ('ad_guid', models.CharField(blank=True, help_text='On-premise Active Directory unique object ID', max_length=48, null=True, unique=True, verbose_name='AD GUID')),
                ('ad_data', models.JSONField(blank=True, default=dict, editable=False, help_text='Cache of on-premise AD data', null=True)),
                ('ad_data_updated', models.DateTimeField(editable=False, null=True)),
                ('azure_guid', models.CharField(blank=True, editable=False, help_text='Azure Active Directory unique object ID', max_length=48, null=True, unique=True, verbose_name='Azure GUID')),
                ('azure_ad_data', models.JSONField(blank=True, default=dict, editable=False, help_text='Cache of Azure AD data', null=True)),
                ('azure_ad_data_updated', models.DateTimeField(editable=False, null=True)),
                ('dir_sync_enabled', models.BooleanField(default=None, help_text='Azure AD account is synced to on-prem AD', null=True)),
                ('cost_centre', models.ForeignKey(blank=True, help_text='Cost centre to which the employee currently belongs', limit_choices_to={'active': True}, null=True, on_delete=django.db.models.deletion.PROTECT, to='organisation.costcentre')),
            ],
        ),
        migrations.CreateModel(
            name='Location',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=256, unique=True)),
                ('address', models.TextField(blank=True)),
                ('pobox', models.TextField(blank=True, verbose_name='PO Box')),
                ('phone', models.CharField(blank=True, max_length=128, null=True)),
                ('fax', models.CharField(blank=True, max_length=128, null=True)),
                ('point', django.contrib.gis.db.models.fields.PointField(blank=True, null=True, srid=4326)),
                ('ascender_code', models.CharField(blank=True, max_length=16, null=True, unique=True)),
                ('ascender_desc', models.CharField(blank=True, max_length=128, null=True)),
                ('active', models.BooleanField(default=True)),
            ],
            options={
                'ordering': ('name',),
            },
        ),
        migrations.CreateModel(
            name='OrgUnit',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('active', models.BooleanField(default=True)),
                ('unit_type', models.PositiveSmallIntegerField(choices=[(0, 'Department (Tier one)'), (1, 'Division (Tier two)'), (11, 'Division'), (9, 'Group'), (2, 'Branch'), (7, 'Section'), (3, 'Region'), (6, 'District'), (8, 'Unit'), (5, 'Office'), (10, 'Work centre')])),
                ('name', models.CharField(max_length=256)),
                ('acronym', models.CharField(blank=True, max_length=16, null=True)),
                ('ascender_clevel', models.CharField(blank=True, max_length=128, null=True, unique=True)),
                ('division_unit', models.ForeignKey(blank=True, help_text='Division-level unit to which this unit belongs', null=True, on_delete=django.db.models.deletion.PROTECT, related_name='division_orgunits', to='organisation.orgunit')),
                ('location', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to='organisation.location')),
                ('manager', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='organisation.departmentuser')),
            ],
            options={
                'ordering': ('name',),
            },
        ),
        migrations.CreateModel(
            name='DepartmentUserLog',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('log', models.JSONField(default=dict, editable=False)),
                ('department_user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='organisation.departmentuser')),
            ],
        ),
        migrations.AddField(
            model_name='departmentuser',
            name='location',
            field=models.ForeignKey(blank=True, help_text='Current physical workplace.', limit_choices_to={'active': True}, null=True, on_delete=django.db.models.deletion.PROTECT, to='organisation.location'),
        ),
        migrations.AddField(
            model_name='departmentuser',
            name='manager',
            field=models.ForeignKey(blank=True, help_text='Staff member who manages this employee', limit_choices_to={'active': True}, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='manages', to='organisation.departmentuser'),
        ),
        migrations.AddField(
            model_name='costcentre',
            name='manager',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='manage_ccs', to='organisation.departmentuser'),
        ),
    ]