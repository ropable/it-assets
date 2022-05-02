from data_storage import AzureBlobStorage
from datetime import datetime, timedelta
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.postgres.fields import ArrayField, CIEmailField
from django.contrib.gis.db import models
import json
import logging
import os
import requests
from tempfile import NamedTemporaryFile

from itassets.utils import ms_graph_client_token
from .utils import compare_values, parse_windows_ts, title_except
LOGGER = logging.getLogger('organisation')


class DepartmentUser(models.Model):
    """Represents a user account managed in Active Directory.
    """
    ACTIVE_FILTER = {'active': True, 'contractor': False}
    # The following choices are intended to match options in Ascender.
    ACCOUNT_TYPE_CHOICES = (
        (2, 'L1 User Account - Permanent'),
        (3, 'L1 User Account - Agency contract'),
        (0, 'L1 User Account - Department fixed-term contract'),
        (8, 'L1 User Account - Seasonal'),
        (6, 'L1 User Account - Vendor'),
        (7, 'L1 User Account - Volunteer'),
        (1, 'L1 User Account - Other/Alumni'),
        (11, 'L1 User Account - RoomMailbox'),
        (12, 'L1 User Account - EquipmentMailbox'),
        (10, 'L2 Service Account - System'),
        (5, 'L1 Group (shared) Mailbox - Shared account'),
        (9, 'L1 Role Account - Role-based account'),
        (4, 'Terminated'),
        (14, 'Unknown - AD disabled'),
        (15, 'Cleanup - Permanent'),
        (16, 'Unknown - AD active'),
    )
    # The following is a list of account types to normally exclude from user queries.
    # E.g. shared accounts, meeting rooms, terminated accounts, etc.
    ACCOUNT_TYPE_EXCLUDE = [1, 4, 5, 7, 9, 10, 11, 12, 14, 16]
    # The following is a list of user account types for individual staff/vendors,
    # i.e. no shared or role-based account types.
    # NOTE: it may not necessarily be the inverse of the previous list.
    ACCOUNT_TYPE_USER = [2, 3, 0, 8, 6, 7, 1]
    # The following is a list of user account types where it may be reasonable for there to be
    # an active Azure AD account without the user also having a current Ascender job.
    ACCOUNT_TYPE_NONSTAFF = [8, 6, 7, 1]
    # This dict maps the Microsoft SKU ID for user account licences to a human-readable name.
    # https://docs.microsoft.com/en-us/azure/active-directory/users-groups-roles/licensing-service-plan-reference
    MS_LICENCE_SKUS = {
        '18181a46-0d4e-45cd-891e-60aabd171b4e': 'OFFICE 365 E1',
        '6fd2c87f-b296-42f0-b197-1e91e994b900': 'OFFICE 365 E3',
        'c7df2760-2c81-4ef7-b578-5b5392b571df': 'OFFICE 365 E5',
        '05e9a617-0261-4cee-bb44-138d3ef5d965': 'MICROSOFT 365 E3',
        '66b55226-6b4f-492c-910c-a3b7a3c9d993': 'MICROSOFT 365 F3',
        '06ebc4ee-1bb5-47dd-8120-11324bc54e06': 'MICROSOFT 365 E5',
        'c5928f49-12ba-48f7-ada3-0d743a3601d5': 'VISIO ONLINE PLAN 2',
        '1f2f344a-700d-42c9-9427-5cea1d5d7ba6': 'MICROSOFT STREAM',
        'b05e124f-c7cc-45a0-a6aa-8cf78c946968': 'ENTERPRISE MOBILITY + SECURITY E5',
        '87bbbc60-4754-4998-8c88-227dca264858': 'POWERAPPS AND LOGIC FLOWS',
        '6470687e-a428-4b7a-bef2-8a291ad947c9': 'WINDOWS STORE FOR BUSINESS',
        'f30db892-07e9-47e9-837c-80727f46fd3d': 'MICROSOFT POWER AUTOMATE FREE',
        '440eaaa8-b3e0-484b-a8be-62870b9ba70a': 'MICROSOFT 365 PHONE SYSTEM - VIRTUAL USER',
        'bc946dac-7877-4271-b2f7-99d2db13cd2c': 'DYNAMICS 365 CUSTOMER VOICE TRIAL',
        'dcb1a3ae-b33f-4487-846a-a640262fadf4': 'MICROSOFT POWER APPS PLAN 2 TRIAL',
        '338148b6-1b11-4102-afb9-f92b6cdc0f8d': 'DYNAMICS 365 P1 TRIAL FOR INFORMATION WORKERS',
        '6070a4c8-34c6-4937-8dfb-39bbc6397a60': 'MICROSOFT TEAMS ROOMS STANDARD',
        'a403ebcc-fae0-4ca2-8c8c-7a907fd6c235': 'POWER BI (FREE)',
        '111046dd-295b-4d6d-9724-d52ac90bd1f2': 'MICROSOFT DEFENDER ADVANCED THREAT PROTECTION',
        '710779e8-3d4a-4c88-adb9-386c958d1fdf': 'MICROSOFT TEAMS EXPLORATORY',
        'efccb6f7-5641-4e0e-bd10-b4976e1bf68e': 'ENTERPRISE MOBILITY + SECURITY E3',
        '90d8b3f8-712e-4f7b-aa1e-62e7ae6cbe96': 'BUSINESS APPS (FREE)',
        'fcecd1f9-a91e-488d-a918-a96cdb6ce2b0': 'MICROSOFT DYNAMICS AX7 USER TRIAL',
        '093e8d14-a334-43d9-93e3-30589a8b47d0': 'RIGHTS MANAGEMENT SERVICE BASIC CONTENT PROTECTION',
        '53818b1b-4a27-454b-8896-0dba576410e6': 'PROJECT ONLINE PROFESSIONAL',
        'c1ec4a95-1f05-45b3-a911-aa3fa01094f5': 'INTUNE',
        '3e26ee1f-8a5f-4d52-aee2-b81ce45c8f40': 'AUDIO CONFERENCING',
        '57ff2da0-773e-42df-b2af-ffb7a2317929': 'MICROSOFT TEAMS',
        '0feaeb32-d00e-4d66-bd5a-43b5b83db82c': 'SKYPE FOR BUSINESS ONLINE (PLAN 2)',
        '4828c8ec-dc2e-4779-b502-87ac9ce28ab7': 'SKYPE FOR BUSINESS CLOUD PBX',
        '19ec0d23-8335-4cbd-94ac-6050e30712fa': 'EXCHANGE ONLINE (PLAN 2)',
        '2347355b-4e81-41a4-9c22-55057a399791': 'MICROSOFT 365 SECURITY AND COMPLIANCE FOR FLW',
        'de376a03-6e5b-42ec-855f-093fb50b8ca5': 'POWER BI PREMIUM PER USER ADD-ON',
    }
    # A map of codes in the EMP_STATUS field to descriptive text.
    EMP_STATUS_MAP = {
        "ADV": "ADVERTISED VACANCY",
        "BD": "Board",
        "CAS": "CASUAL EMPLOYEES",
        "CCFA": "COMMITTEE-BOARD MEMBERS FIXED TERM CONTRACT  AUTO",
        "CD": "CADET",
        "CEP": "COMMONWEALTH EMPLOYMENT PROGRAM",
        "CFA": "FIXED TERM CONTRACT FULL-TIME AUTO",
        "CFAS": "CONTRACT F-TIME AUTO SENIOR EXECUTIVE SERVICE",
        "CFT": "FIXED TERM CONTRACT FULL-TIME TSHEET",
        "CJA": "FIXED TERM CONTRACT JOB SHARE AUTO",
        "CJT": "FIXED TERM CONTRACT JOBSHARE TSHEET",
        "CO": "COMMITTEE (DO NOT USE- USE CCFA)",
        "CON": "EXTERNAL CONTRACTOR",
        "CPA": "FIXED TERM CONTRACT PART-TIME AUTO",
        "CPAS": "CONTRACT P-TIME AUTO SENIOR EXECUTIVE SERVICE",
        "CPT": "FIXED TERM CONTRACT PART-TIME TSHEET",
        "ECAS": "EXTERNAL FUND CASUAL",
        "ECFA": "FIXED TERM CONTRACT EXT. FUND F/TIME AUTO",
        "ECFT": "FIXED TERM CONTRACT EXT. FUND F/TIME TSHEET",
        "ECJA": "FIXED TERM CONTRACT EXT. FUND JOBSHARE AUTO",
        "ECJT": "FIXED TERM CONTRACT EXT. FUND JOBSHARE TSHEET",
        "ECPA": "FIXED TERM CONTRACT EXT. FUND P/TIME AUTO",
        "ECPT": "FIXED TERM CONTRACT EXT. FUND P/TIME TSHEET",
        "EPFA": "EXTERNAL FUND PERMANENT FULL-TIME AUTO",
        "EPFT": "EXTERNAL FUND FULL-TIME TSHEET",
        "EPJA": "EXTERNAL FUND PERMANENT JOBSHARE AUTO",
        "EPJT": "EXTERNAL FUND PERMANENT JOBSHARE TSHEEET",
        "EPPA": "EXTERNAL FUND PERMANENT PART-TIME AUTO",
        "EPPT": "EXTERNAL FUND PERMANENT PART-TIME TSHEET",
        "EXT": "EXTERNAL PERSON (NON EMPLOYEE)",
        "GRCA": "GRADUATE RECRUIT FIXED TERM CONTRACT AUTO",
        "JOB": "JOBSKILLS",
        "NON": "NON EMPLOYEE",
        "NOPAY": "NO PAY ALLOWED",
        "NPAYC": "CASUAL NO PAY ALLOWED",
        "NPAYF": "FULLTIME NO PAY ALLOWED",
        "NPAYP": "PARTTIME NO PAY ALLOWED",
        "NPAYT": "CONTRACT NO PAY ALLOWED (SEAS,CONT)",
        "PFA": "PERMANENT FULL-TIME AUTO",
        "PFAE": "PERMANENT FULL-TIME AUTO EXECUTIVE COUNCIL APPOINT",
        "PFAS": "PERMANENT FULL-TIME AUTO SENIOR EXECUTIVE SERVICE",
        "PFT": "PERMANENT FULL-TIME TSHEET",
        "PJA": "PERMANENT JOB SHARE AUTO",
        "PJT": "PERMANENT JOBSHARE TSHEET",
        "PPA": "PERMANENT PART-TIME AUTO",
        "PPAS": "PERMANENT PART-TIME AUTO SENIOR EXECUTIVE SERVICE",
        "PPRTA": "PERMANENT P-TIME AUTO (RELINQUISH ROR to FT)",
        "PPT": "PERMANENT PART-TIME TSHEET",
        "SCFA": "SECONDMENT FULL-TIME AUTO",
        "SEAP": "SEASONAL EMPLOYMENT (PERMANENT)",
        "SEAS": "SEASONAL EMPLOYMENT",
        "SES": "Senior Executive Service",
        "SFTC": "SPONSORED FIXED TERM CONTRACT AUTO",
        "SFTT": "SECONDMENT FULL-TIME TSHEET",
        "SN": "SUPERNUMERY",
        "SPFA": "PERMANENT FT SPECIAL CONDITIO AUTO",
        "SPFT": "PERMANENT FT SPECIAL CONDITIONS  TS",
        "SPTA": "SECONDMENT PART-TIME AUTO",
        "SPTT": "SECONDMENT PART-TIME TSHEET",
        "TEMP": "TEMPORARY EMPLOYMENT",
        "TERM": "TERMINATED",
        "TRAIN": "TRAINEE",
        "V": "VOLUNTEER",
        "WWR": "WEEKEND WEATHER READER",
        "Z": "Non-Resident",
    }

    date_created = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True)

    # Fields directly related to the employee, which map to a field in Active Directory.
    active = models.BooleanField(
        default=True, editable=False, help_text='Account is enabled within Active Directory.')
    email = CIEmailField(unique=True, editable=False, help_text='Account email address')
    name = models.CharField(max_length=128, verbose_name='display name')
    given_name = models.CharField(max_length=128, null=True, blank=True, help_text='First name')
    surname = models.CharField(max_length=128, null=True, blank=True, help_text='Last name')
    preferred_name = models.CharField(max_length=256, null=True, blank=True)
    title = models.CharField(
        max_length=128, null=True, blank=True,
        help_text='Occupation position title (should match Ascender position title)')
    telephone = models.CharField(
        max_length=128, null=True, blank=True, help_text='Work telephone number')
    mobile_phone = models.CharField(
        max_length=128, null=True, blank=True, help_text='Work mobile number')
    manager = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True,
        limit_choices_to={'active': True},
        related_name='manages', help_text='Staff member who manages this employee')
    cost_centre = models.ForeignKey(
        'organisation.CostCentre', on_delete=models.PROTECT, null=True, blank=True,
        limit_choices_to={'active': True},
        help_text='Cost centre to which the employee currently belongs')
    location = models.ForeignKey(
        'Location', on_delete=models.PROTECT, null=True, blank=True,
        limit_choices_to={'active': True},
        help_text='Current physical workplace.')
    proxy_addresses = ArrayField(base_field=models.CharField(
        max_length=254, blank=True), blank=True, null=True, help_text='Email aliases')
    assigned_licences = ArrayField(base_field=models.CharField(
        max_length=254, blank=True), blank=True, null=True, help_text='Assigned Microsoft 365 licences')

    # Metadata fields with no direct equivalent in AD.
    # They are used for internal reporting and the Address Book.
    org_unit = models.ForeignKey(
        'organisation.OrgUnit', on_delete=models.PROTECT, null=True, blank=True,
        limit_choices_to={'active': True},
        verbose_name='organisational unit',
        help_text="The organisational unit to which the employee belongs.")
    extension = models.CharField(
        max_length=128, null=True, blank=True, verbose_name='VoIP extension')
    home_phone = models.CharField(max_length=128, null=True, blank=True)
    other_phone = models.CharField(max_length=128, null=True, blank=True)
    name_update_reference = models.CharField(
        max_length=512, null=True, blank=True, verbose_name='update reference',
        help_text='Reference for name/CC change request')
    vip = models.BooleanField(
        default=False,
        help_text="An individual who carries out a critical role for the department")
    executive = models.BooleanField(
        default=False, help_text="An individual who is an executive")
    contractor = models.BooleanField(
        default=False,
        help_text="An individual who is an external contractor (does not include agency contract staff)")
    notes = models.TextField(
        null=True, blank=True,
        help_text='Records relevant to any AD account extension, expiry or deletion (e.g. ticket #).')
    account_type = models.PositiveSmallIntegerField(
        choices=ACCOUNT_TYPE_CHOICES, null=True, blank=True,
        help_text='Employee network account status')
    security_clearance = models.BooleanField(
        default=False, verbose_name='security clearance granted',
        help_text='''Security clearance approved by CC Manager (confidentiality
        agreement, referee check, police clearance, etc.''')
    shared_account = models.BooleanField(
        default=False, editable=False, help_text='Automatically set from account type.')

    # Ascender data
    employee_id = models.CharField(
        max_length=128, null=True, unique=True, blank=True, verbose_name='Employee ID',
        help_text='Ascender employee number')
    ascender_data = models.JSONField(default=dict, null=True, blank=True, editable=False, help_text="Cache of staff Ascender data")
    ascender_data_updated = models.DateTimeField(
        null=True, editable=False, help_text="Timestamp of when Ascender data was last updated for this user")
    # On-premise AD data
    ad_guid = models.CharField(
        max_length=48, unique=True, null=True, blank=True, verbose_name="AD GUID",
        help_text="On-premise Active Directory unique object ID")
    ad_data = models.JSONField(default=dict, null=True, blank=True, editable=False, help_text="Cache of on-premise AD data")
    ad_data_updated = models.DateTimeField(null=True, editable=False)
    # Azure AD data
    azure_guid = models.CharField(
        max_length=48, unique=True, null=True, blank=True, verbose_name="Azure GUID",
        editable=False, help_text="Azure Active Directory unique object ID")
    azure_ad_data = models.JSONField(default=dict, null=True, blank=True, editable=False, help_text="Cache of Azure AD data")
    azure_ad_data_updated = models.DateTimeField(null=True, editable=False)
    dir_sync_enabled = models.BooleanField(null=True, default=None, help_text="Azure AD account is synced to on-prem AD")

    def __str__(self):
        return self.email

    def save(self, *args, **kwargs):
        """Override the save method with additional business logic.
        """
        if self.employee_id:
            if (self.employee_id.lower() == "n/a") or (self.employee_id.strip() == ''):
                self.employee_id = None
        if self.account_type in [5, 9, 10]:  # Shared/role-based/system account types.
            self.shared_account = True
        # If an account type is not set, set one here.
        if self.account_type is None:
            if self.active:
                self.account_type = 16  # Unknown - AD active
            elif not self.active:
                self.account_type = 14  # Unknown - AD disabled
        super(DepartmentUser, self).save(*args, **kwargs)

    @property
    def group_unit(self):
        """Return the group-level org unit, as seen in the primary address book view.
        In most cases, this should return the user's division.
        """
        if self.org_unit and self.org_unit.division_unit:
            return self.org_unit.division_unit
        return self.org_unit

    def get_division(self):
        """Returns the name of the division this user belongs to, based upon their cost centre.
        """
        if self.cost_centre:
            return self.cost_centre.get_division_name_display()
        return None

    def get_licence(self):
        """Return Microsoft 365 licence description consistent with other OIM communications.
        """
        if self.assigned_licences:
            if 'MICROSOFT 365 E5' in self.assigned_licences:
                return 'On-premise'
            elif 'MICROSOFT 365 F3' in self.assigned_licences:
                return 'Cloud'
        return None

    def get_full_name(self):
        """Return given_name and surname, with a space in between.
        """
        full_name = '{} {}'.format(self.given_name if self.given_name else '', self.surname if self.surname else '')
        return full_name.strip()

    def get_employment_status(self):
        """From Ascender data, return a description of a user's employment status.
        """
        if self.ascender_data and 'emp_status' in self.ascender_data and self.ascender_data['emp_status']:
            if self.ascender_data['emp_status'] in self.EMP_STATUS_MAP:
                return self.EMP_STATUS_MAP[self.ascender_data['emp_status']]
        return ''

    def get_ascender_full_name(self):
        """From Ascender data, return the users's full name.
        """
        if self.ascender_data:
            name = []
            if 'first_name' in self.ascender_data and self.ascender_data['first_name']:
                name.append(self.ascender_data['first_name'])
            if 'second_name' in self.ascender_data and self.ascender_data['second_name']:
                name.append(self.ascender_data['second_name'])
            if 'surname' in self.ascender_data and self.ascender_data['surname']:
                name.append(self.ascender_data['surname'])
            return ' '.join(name)
        return ''

    def get_ascender_preferred_name(self):
        if self.ascender_data and 'preferred_name' in self.ascender_data:
            return self.ascender_data['preferred_name']
        return ''

    def get_position_title(self):
        """From Ascender data, return the user's position title.
        """
        if self.ascender_data and 'occup_pos_title' in self.ascender_data and self.ascender_data['occup_pos_title']:
            return self.ascender_data['occup_pos_title']
        return ''

    def get_paypoint(self):
        """From Ascender data, return the user's paypoint value.
        """
        if self.ascender_data and 'paypoint' in self.ascender_data and self.ascender_data['paypoint']:
            return self.ascender_data['paypoint']
        return ''

    def get_ascender_org_path(self):
        """From Ascender data, return the users's organisation tree path as a list of section names.
        """
        path = []
        if (
            self.ascender_data
            and 'clevel1_desc' in self.ascender_data
            and 'clevel2_desc' in self.ascender_data
            and 'clevel3_desc' in self.ascender_data
            and 'clevel4_desc' in self.ascender_data
            and 'clevel5_desc' in self.ascender_data
        ):
            data = [
                self.ascender_data['clevel1_desc'],
                self.ascender_data['clevel2_desc'],
                self.ascender_data['clevel3_desc'],
                self.ascender_data['clevel4_desc'],
                self.ascender_data['clevel5_desc'],
            ]
            for d in data:
                branch = d.replace('ROTTNEST ISLAND AUTHORITY - ', '').replace('  ', ' ')
                if branch not in path and branch != 'DEPT BIODIVERSITY, CONSERVATION AND ATTRACTIONS':
                    path.append(branch)
        return path

    def get_geo_location_desc(self):
        """From Ascender data, return the user's geographical location description.
        """
        if self.ascender_data and 'geo_location_desc' in self.ascender_data:
            return self.ascender_data['geo_location_desc']
        return ''

    def get_job_start_date(self):
        """From Ascender data, return the user's job start date.
        """
        if self.ascender_data and 'job_start_date' in self.ascender_data and self.ascender_data['job_start_date']:
            return datetime.strptime(self.ascender_data['job_start_date'], '%Y-%m-%d').date()
        return ''

    def get_job_end_date(self):
        """From Ascender data, return the user's occupation/job termination/end date.
        """
        if self.ascender_data and 'job_end_date' in self.ascender_data and self.ascender_data['job_end_date']:
            return datetime.strptime(self.ascender_data['job_end_date'], '%Y-%m-%d').date()
        return ''

    def get_manager_name(self):
        """From Ascender data, return the user's occupation/job termination/end date.
        """
        if self.ascender_data and 'manager_name' in self.ascender_data and self.ascender_data['manager_name']:
            return self.ascender_data['manager_name']
        return ''

    def get_extended_leave(self):
        """From Ascender data, return the date from which a user's extended leave ends (if applicable).
        """
        if (
            self.ascender_data
            and 'extended_lv' in self.ascender_data
            and 'ext_lv_end_date' in self.ascender_data
            and self.ascender_data['extended_lv'] == 'Y'
            and self.ascender_data['ext_lv_end_date']
        ):
            return datetime.strptime(self.ascender_data['ext_lv_end_date'], '%Y-%m-%d').date()
        return ''

    def sync_ad_data(self, container='azuread', log_only=False, token=None):
        """For this DepartmentUser, iterate through fields which need to be synced between IT Assets
        and external AD databases (Azure AD, onprem AD).
        Each field has a 'source of truth'. In each case, check the source of truth and make changes
        to the required databases.
        If `log_only` is True, do not schedule changes to AD databases (output logs only).
        """
        connect_string = os.environ.get('AZURE_CONNECTION_STRING')
        store = AzureBlobStorage(connect_string, container)
        if not token:
            token = ms_graph_client_token()
        url = f"https://graph.microsoft.com/v1.0/users/{self.azure_guid}"
        acct = 'onprem' if self.dir_sync_enabled else 'cloud'
        today = datetime.today().replace(hour=0, minute=0, second=0, microsecond=0)  # We need a datetime object.

        # active (source of truth: Ascender).
        # This also includes Cloud-licenced users, which don't have an "expiry date".
        # SCENARIO 1: Ascender record indicates that a user's job has finished (is in the past) but their account is active - deactivate their account.
        if (
            self.active
            and self.employee_id
            and self.ascender_data
            and 'job_end_date' in self.ascender_data
            and self.ascender_data['job_end_date']
            and settings.ASCENDER_DEACTIVATE_EXPIRED
        ):
            job_end_date = datetime.strptime(self.ascender_data['job_end_date'], '%Y-%m-%d')

            # Where a user has a job which in which the job end date is in the past, deactivate the user's AD account.
            if job_end_date < today:
                LOGGER.info(f'ASCENDER SYNC: {self} job is past end date of {job_end_date.date()}; deactivating their {acct} AD account')

                # Create a DepartmentUserLog object to record this update.
                if not log_only:
                    DepartmentUserLog.objects.create(
                        department_user=self,
                        log={
                            'ascender_field': 'job_end_date',
                            'old_value': self.ascender_data['job_end_date'],
                            'new_value': None,
                            'description': f'Deactivate {acct} AD account',
                        },
                    )

                # Onprem AD users.
                if self.dir_sync_enabled and self.ad_guid and self.ad_data:
                    prop = 'Enabled'
                    change = {
                        'identity': self.ad_guid,
                        'property': prop,
                        'value': False,
                    }
                    f = NamedTemporaryFile()
                    f.write(json.dumps(change, indent=2).encode('utf-8'))
                    f.flush()
                    if not log_only:
                        store.upload_file('onprem_changes/{}_{}.json'.format(self.ad_guid, prop), f.name)
                    LOGGER.info(f'AD SYNC: {self} onprem AD change diff uploaded to blob storage ({prop})')

                # Azure (cloud only) AD users.
                elif not self.dir_sync_enabled and self.azure_guid and self.azure_ad_data:
                    if token:
                        headers = {
                            "Authorization": "Bearer {}".format(token["access_token"]),
                            "Content-Type": "application/json",
                        }
                        data = {"accountEnabled": False}
                        if not log_only:
                            requests.patch(url, headers=headers, json=data)
                        LOGGER.info(f'AZURE SYNC: {self} Azure AD account accountEnabled set to False')

        # Future scenarios:
        # SCENARIO 2: Ascender record indicates that a user is on extended leave.
        # SCENARIO 3: Ascender record indicates that a user is seconded to another organisation.

        # expiry date (source of truth: Ascender).
        # Note that this is for onprem AD only; Azure AD has no concept of "expiry date".
        # SCENARIO 1: the user has a job end date value set in Ascender.
        if (
            self.employee_id
            and self.dir_sync_enabled
            and self.ascender_data
            and 'job_end_date' in self.ascender_data
            and self.ascender_data['job_end_date']
            and self.ad_data
            and 'AccountExpirationDate' in self.ad_data
        ):
            job_end_date = datetime.strptime(self.ascender_data['job_end_date'], '%Y-%m-%d').date()
            # Business rule: Ascender job_end_date is the final working day of a job. Onprem expiration date should be that date, plus one day.
            job_end_date = job_end_date + timedelta(days=1)

            if self.ad_data['AccountExpirationDate']:
                account_expiration_date = parse_windows_ts(self.ad_data['AccountExpirationDate']).date()
            else:
                account_expiration_date = None

            if job_end_date != account_expiration_date:
                # Set the onprem AD account expiration date value.
                prop = 'AccountExpirationDate'
                change = {
                    'identity': self.ad_guid,
                    'property': prop,
                    'value': job_end_date.strftime("%m/%d/%Y"),
                }
                f = NamedTemporaryFile()
                f.write(json.dumps(change, indent=2).encode('utf-8'))
                f.flush()
                if not log_only:
                    store.upload_file('onprem_changes/{}_{}.json'.format(self.ad_guid, prop), f.name)
                LOGGER.info(f'AD SYNC: {self} onprem AD change diff uploaded to blob storage ({prop})')

        # SCENARIO 2: the user has no job end date set in Ascender (i.e. is permanent to the department).
        elif (
            self.employee_id
            and self.dir_sync_enabled
            and self.ascender_data
            and 'job_end_date' in self.ascender_data
            and not self.ascender_data['job_end_date']
            and self.ad_data
            and 'AccountExpirationDate' in self.ad_data
        ):
            if self.ad_data['AccountExpirationDate']:
                account_expiration_date = parse_windows_ts(self.ad_data['AccountExpirationDate']).date()
            else:
                account_expiration_date = None

            if account_expiration_date:  # User has an account expiration set in onprem AD; remove this.
                # Unset the onprem AD account expiration date value.
                prop = 'AccountExpirationDate'
                change = {
                    'identity': self.ad_guid,
                    'property': prop,
                    'value': None,
                }
                f = NamedTemporaryFile()
                f.write(json.dumps(change, indent=2).encode('utf-8'))
                f.flush()
                if not log_only:
                    store.upload_file('onprem_changes/{}_{}.json'.format(self.ad_guid, prop), f.name)
                LOGGER.info(f'AD SYNC: {self} onprem AD change diff uploaded to blob storage ({prop})')

        # display_name (source of truth: Ascender)
        # Onprem AD users
        if self.dir_sync_enabled and self.ad_guid and self.ad_data and 'DisplayName' in self.ad_data and self.ad_data['DisplayName'] != self.name:
            prop = 'DisplayName'
            change = {
                'identity': self.ad_guid,
                'property': prop,
                'value': self.name,
            }
            f = NamedTemporaryFile()
            f.write(json.dumps(change, indent=2).encode('utf-8'))
            f.flush()
            if not log_only:
                store.upload_file('onprem_changes/{}_{}.json'.format(self.ad_guid, prop), f.name)
            LOGGER.info(f'AD SYNC: {self} onprem AD change diff uploaded to blob storage ({prop})')
        # Azure (cloud only) AD users.
        elif not self.dir_sync_enabled and self.azure_guid and self.azure_ad_data and 'displayName' in self.azure_ad_data and self.azure_ad_data['displayName'] != self.name:
            if token:
                headers = {
                    "Authorization": "Bearer {}".format(token["access_token"]),
                    "Content-Type": "application/json",
                }
                data = {"displayName": self.name}
                if not log_only:
                    requests.patch(url, headers=headers, json=data)
                LOGGER.info(f'AZURE AD SYNC: {self} Azure AD account displayName set to {self.name}')

        # given_name (source of truth: Ascender)
        # Onprem AD users
        if self.dir_sync_enabled and self.ad_guid and self.ad_data and 'GivenName' in self.ad_data and self.ad_data['GivenName'] != self.given_name:
            prop = 'GivenName'
            change = {
                'identity': self.ad_guid,
                'property': prop,
                'value': self.given_name,
            }
            f = NamedTemporaryFile()
            f.write(json.dumps(change, indent=2).encode('utf-8'))
            f.flush()
            if not log_only:
                store.upload_file('onprem_changes/{}_{}.json'.format(self.ad_guid, prop), f.name)
            LOGGER.info(f'AD SYNC: {self} onprem AD change diff uploaded to blob storage ({prop})')
        # Azure (cloud only) AD users.
        elif not self.dir_sync_enabled and self.azure_guid and self.azure_ad_data and 'givenName' in self.azure_ad_data and self.azure_ad_data['givenName'] != self.given_name:
            if token:
                headers = {
                    "Authorization": "Bearer {}".format(token["access_token"]),
                    "Content-Type": "application/json",
                }
                data = {"givenName": self.given_name}
                if not log_only:
                    requests.patch(url, headers=headers, json=data)
                LOGGER.info(f'AZURE AD SYNC: {self} Azure AD account givenName set to {self.given_name}')

        # surname (source of truth: Ascender)
        # Onprem AD users
        if self.dir_sync_enabled and self.ad_guid and self.ad_data and 'Surname' in self.ad_data and self.ad_data['Surname'] != self.surname:
            prop = 'Surname'
            change = {
                'identity': self.ad_guid,
                'property': prop,
                'value': self.surname,
            }
            f = NamedTemporaryFile()
            f.write(json.dumps(change, indent=2).encode('utf-8'))
            f.flush()
            if not log_only:
                store.upload_file('onprem_changes/{}_{}.json'.format(self.ad_guid, prop), f.name)
            LOGGER.info(f'AD SYNC: {self} onprem AD change diff uploaded to blob storage ({prop})')
        # Azure (cloud only) AD users.
        elif not self.dir_sync_enabled and self.azure_guid and self.azure_ad_data and 'surname' in self.azure_ad_data and self.azure_ad_data['surname'] != self.surname:
            if token:
                headers = {
                    "Authorization": "Bearer {}".format(token["access_token"]),
                    "Content-Type": "application/json",
                }
                data = {"surname": self.surname}
                if not log_only:
                    requests.patch(url, headers=headers, json=data)
                LOGGER.info(f'AZURE AD SYNC: {self} Azure AD account surname set to {self.surname}')

        # cost_centre (source of truth: Ascender, recorded in AD to the Company field).
        if (
            self.employee_id
            and self.dir_sync_enabled
            and self.cost_centre
            and self.ad_guid
            and self.ad_data
            and 'Company' in self.ad_data
            and self.ad_data['Company'] != self.cost_centre.code
        ):
            prop = 'Company'
            change = {
                'identity': self.ad_guid,
                'property': prop,
                'value': self.cost_centre.code,
            }
            f = NamedTemporaryFile()
            f.write(json.dumps(change, indent=2).encode('utf-8'))
            f.flush()
            if not log_only:
                store.upload_file('onprem_changes/{}_{}.json'.format(self.ad_guid, prop), f.name)
            LOGGER.info(f'AD SYNC: {self} onprem AD change diff uploaded to blob storage ({prop})')
        # Azure (cloud only) AD users. Update the user account directly using the MS Graph API.
        elif (
            self.employee_id
            and not self.dir_sync_enabled
            and self.cost_centre
            and self.azure_guid
            and self.azure_ad_data
            and 'companyName' in self.azure_ad_data
            and self.azure_ad_data['companyName'] != self.cost_centre.code
        ):
            if token:
                headers = {
                    "Authorization": "Bearer {}".format(token["access_token"]),
                    "Content-Type": "application/json",
                }
                data = {"companyName": self.cost_centre.code}
                if not log_only:
                    requests.patch(url, headers=headers, json=data)
                LOGGER.info(f'AZURE SYNC: {self} Azure AD account companyName set to {self.cost_centre.code}')

        # division (source of truth: Ascender, recorded in AD to the Department field).
        # Onprem AD users
        if (
            self.dir_sync_enabled
            and self.ad_guid
            and self.ad_data
            and self.get_division()
            and 'Department' in self.ad_data
            and self.ad_data['Department'] != self.get_division()
        ):
            prop = 'Department'
            change = {
                'identity': self.ad_guid,
                'property': prop,
                'value': self.get_division(),
            }
            f = NamedTemporaryFile()
            f.write(json.dumps(change, indent=2).encode('utf-8'))
            f.flush()
            if not log_only:
                store.upload_file('onprem_changes/{}_{}.json'.format(self.ad_guid, prop), f.name)
            LOGGER.info(f'AD SYNC: {self} onprem AD change diff uploaded to blob storage ({prop})')
        # Azure (cloud only) AD users.
        elif (
            not self.dir_sync_enabled
            and self.azure_guid
            and self.azure_ad_data
            and 'department' in self.azure_ad_data
            and self.get_division()
            and self.azure_ad_data['department'] != self.get_division()
        ):
            if token:
                headers = {
                    "Authorization": "Bearer {}".format(token["access_token"]),
                    "Content-Type": "application/json",
                }
                data = {"department": self.get_division()}
                if not log_only:
                    requests.patch(url, headers=headers, json=data)
                LOGGER.info(f'AZURE SYNC: {self} Azure AD account department set to {self.get_division()}')

        # title (source of truth: Ascender)
        # Onprem AD users
        if self.dir_sync_enabled and self.ad_guid and self.ad_data and 'Title' in self.ad_data and self.ad_data['Title'] != self.title:
            prop = 'Title'
            change = {
                'identity': self.ad_guid,
                'property': prop,
                'value': self.title,
            }
            f = NamedTemporaryFile()
            f.write(json.dumps(change, indent=2).encode('utf-8'))
            f.flush()
            if not log_only:
                store.upload_file('onprem_changes/{}_{}.json'.format(self.ad_guid, prop), f.name)
            LOGGER.info(f'AD SYNC: {self} onprem AD change diff uploaded to blob storage ({prop})')
        # Azure (cloud only) AD users.
        elif not self.dir_sync_enabled and self.azure_guid and self.azure_ad_data and 'jobTitle' in self.azure_ad_data and self.azure_ad_data['jobTitle'] != self.title:
            if token:
                headers = {
                    "Authorization": "Bearer {}".format(token["access_token"]),
                    "Content-Type": "application/json",
                }
                data = {"jobTitle": self.title}
                if not log_only:
                    requests.patch(url, headers=headers, json=data)
                LOGGER.info(f'AZURE AD SYNC: {self} Azure AD account jobTitle set to {self.title}')

        # telephone (source of truth: IT Assets)
        # Onprem AD users
        if self.dir_sync_enabled and self.ad_guid and self.ad_data and 'telephoneNumber' in self.ad_data:
            if (
                self.ad_data['telephoneNumber']
                and not compare_values(self.ad_data['telephoneNumber'].strip(), self.telephone)
            ) or (
                self.telephone
                and not self.ad_data['telephoneNumber']
            ):
                prop = 'telephoneNumber'
                change = {
                    'identity': self.ad_guid,
                    'property': prop,
                    'value': self.telephone,
                }
                f = NamedTemporaryFile()
                f.write(json.dumps(change, indent=2).encode('utf-8'))
                f.flush()
                if not log_only:
                    store.upload_file('onprem_changes/{}_{}.json'.format(self.ad_guid, prop), f.name)
                LOGGER.info(f'AD SYNC: {self} onprem AD change diff uploaded to blob storage ({prop})')
        # Azure (cloud only) AD users
        elif not self.dir_sync_enabled and self.azure_guid and self.azure_ad_data and 'telephoneNumber' in self.azure_ad_data:
            if (
                self.azure_ad_data['telephoneNumber']
                and not compare_values(self.azure_ad_data['telephoneNumber'].strip(), self.telephone)
            ) or (
                self.telephone
                and not self.azure_ad_data['telephoneNumber']
            ):
                if token:
                    headers = {
                        "Authorization": "Bearer {}".format(token["access_token"]),
                        "Content-Type": "application/json",
                    }
                    data = {"businessPhones": [self.telephone if self.telephone else " "]}
                    if not log_only:
                        requests.patch(url, headers=headers, json=data)
                    LOGGER.info(f'AZURE AD SYNC: {self} Azure AD account telephoneNumber set to {self.telephone}')

        # mobile (source of truth: IT Assets)
        # Onprem AD users
        if self.dir_sync_enabled and self.ad_guid and self.ad_data and 'Mobile' in self.ad_data:
            if (
                self.ad_data['Mobile']
                and not compare_values(self.ad_data['Mobile'].strip(), self.mobile_phone)
            ) or (
                self.mobile_phone
                and not self.ad_data['Mobile']
            ):
                prop = 'Mobile'
                change = {
                    'identity': self.ad_guid,
                    'property': prop,
                    'value': self.mobile_phone,
                }
                f = NamedTemporaryFile()
                f.write(json.dumps(change, indent=2).encode('utf-8'))
                f.flush()
                if not log_only:
                    store.upload_file('onprem_changes/{}_{}.json'.format(self.ad_guid, prop), f.name)
                LOGGER.info(f'AD SYNC: {self} onprem AD change diff uploaded to blob storage ({prop})')
        # Azure (cloud only) AD users
        elif not self.dir_sync_enabled and self.azure_guid and self.azure_ad_data and 'mobilePhone' in self.azure_ad_data:
            if (
                self.azure_ad_data['mobilePhone']
                and not compare_values(self.azure_ad_data['mobilePhone'].strip(), self.mobile_phone)
            ) or (
                self.mobile_phone
                and not self.azure_ad_data['mobilePhone']
            ):
                if token:
                    headers = {
                        "Authorization": "Bearer {}".format(token["access_token"]),
                        "Content-Type": "application/json",
                    }
                    data = {"mobilePhone": self.mobile_phone}
                    if not log_only:
                        requests.patch(url, headers=headers, json=data)
                    LOGGER.info(f'AZURE AD SYNC: {self} Azure AD account mobilePhone set to {self.mobile_phone}')

        # employee_id (source of truth: Ascender)
        # Onprem AD users
        if (
            self.dir_sync_enabled
            and self.ad_guid
            and self.ad_data
            and 'EmployeeID' in self.ad_data
            and self.ad_data['EmployeeID'] != self.employee_id
        ):
            prop = 'EmployeeID'
            change = {
                'identity': self.ad_guid,
                'property': prop,
                'value': self.employee_id,
            }
            f = NamedTemporaryFile()
            f.write(json.dumps(change, indent=2).encode('utf-8'))
            f.flush()
            if not log_only:
                store.upload_file('onprem_changes/{}_{}.json'.format(self.ad_guid, prop), f.name)
            LOGGER.info(f'AD SYNC: {self} onprem AD change diff uploaded to blob storage ({prop})')
        # Azure (cloud only) AD users
        elif (
            not self.dir_sync_enabled
            and self.azure_guid
            and self.azure_ad_data
            and 'employeeId' in self.azure_ad_data
            and self.azure_ad_data['employeeId'] != self.employee_id
        ):
            if token:
                headers = {
                    "Authorization": "Bearer {}".format(token["access_token"]),
                    "Content-Type": "application/json",
                }
                data = {"employeeId": self.employee_id}
                if not log_only:
                    requests.patch(url, headers=headers, json=data)
                LOGGER.info(f'AZURE AD SYNC: {self} Azure AD account employeeId set to {self.employee_id}')

        # manager (source of truth: Ascender)
        # Onprem AD users
        if self.dir_sync_enabled and self.ad_guid and self.ad_data and 'Manager' in self.ad_data:
            if self.ad_data['Manager'] and DepartmentUser.objects.filter(active=True, ad_data__DistinguishedName=self.ad_data['Manager']).exists():
                manager_ad = DepartmentUser.objects.get(ad_data__DistinguishedName=self.ad_data['Manager'])
            else:
                manager_ad = None

            if self.manager != manager_ad:
                prop = 'Manager'
                change = {
                    'identity': self.ad_guid,
                    'property': prop,
                    'value': self.manager.ad_guid if self.manager else None,
                }
                f = NamedTemporaryFile()
                f.write(json.dumps(change, indent=2).encode('utf-8'))
                f.flush()
                if not log_only:
                    store.upload_file('onprem_changes/{}_{}.json'.format(self.ad_guid, prop), f.name)
                LOGGER.info(f'AD SYNC: {self} onprem AD change diff uploaded to blob storage ({prop})')
        # Azure (cloud only) AD users
        elif not self.dir_sync_enabled and self.azure_guid and self.azure_ad_data and 'manager' in self.azure_ad_data:
            if self.azure_ad_data['manager'] and DepartmentUser.objects.filter(azure_guid=self.azure_ad_data['manager']['id']).exists():
                manager_ad = DepartmentUser.objects.get(azure_guid=self.azure_ad_data['manager']['id'])
            else:
                manager_ad = None

            if self.manager and self.manager.azure_guid and self.manager != manager_ad:
                if token:
                    headers = {
                        "Authorization": "Bearer {}".format(token["access_token"]),
                        "Content-Type": "application/json",
                    }
                    manager_url = f"https://graph.microsoft.com/v1.0/users/{self.azure_guid}/manager/$ref"
                    data = {"@odata.id": f"https://graph.microsoft.com/v1.0/users/{self.manager.azure_guid}"}
                    if not log_only:
                        requests.put(manager_url, headers=headers, json=data)
                    LOGGER.info(f'AZURE AD SYNC: {self} Azure AD account manager set to {self.manager}')

        # location (source of truth: Ascender)
        # Onprem AD users
        if (
            self.dir_sync_enabled
            and self.ad_guid
            and self.ad_data
            and 'physicalDeliveryOfficeName' in self.ad_data
            and 'geo_location_desc' in self.ascender_data
            and self.ascender_data['geo_location_desc']
        ):
            if Location.objects.filter(ascender_desc=self.ascender_data['geo_location_desc']).exists():
                ascender_location = Location.objects.get(ascender_desc=self.ascender_data['geo_location_desc'])
            else:
                ascender_location = None
            if self.ad_data['physicalDeliveryOfficeName'] and Location.objects.filter(name=self.ad_data['physicalDeliveryOfficeName']).exists():
                ad_location = Location.objects.get(name=self.ad_data['physicalDeliveryOfficeName'])
            else:
                ad_location = None
            # Only update if we matched a physical location from Ascender.
            if ascender_location and ascender_location != ad_location:
                # Update both physicalDeliveryOfficeName and StreetAddress in onprem AD.
                prop = 'physicalDeliveryOfficeName'
                change = {
                    'identity': self.ad_guid,
                    'property': prop,
                    'value': ascender_location.name,
                }
                f = NamedTemporaryFile()
                f.write(json.dumps(change, indent=2).encode('utf-8'))
                f.flush()
                if not log_only:
                    store.upload_file('onprem_changes/{}_{}.json'.format(self.ad_guid, prop), f.name)
                LOGGER.info(f'AD SYNC: {self} onprem AD change diff uploaded to blob storage ({prop})')
                prop = 'streetAddress'
                change = {
                    'identity': self.ad_guid,
                    'property': prop,
                    'value': ascender_location.address,
                }
                f = NamedTemporaryFile()
                f.write(json.dumps(change, indent=2).encode('utf-8'))
                f.flush()
                if not log_only:
                    store.upload_file('onprem_changes/{}_{}.json'.format(self.ad_guid, prop), f.name)
                LOGGER.info(f'AD SYNC: {self} onprem AD change diff uploaded to blob storage ({prop})')
        # Azure (cloud only) AD users
        elif (
            not self.dir_sync_enabled
            and self.azure_guid
            and self.azure_ad_data
            and 'officeLocation' in self.azure_ad_data
            and 'geo_location_desc' in self.ascender_data
            and self.ascender_data['geo_location_desc']
        ):
            if Location.objects.filter(ascender_desc=self.ascender_data['geo_location_desc']).exists():
                ascender_location = Location.objects.get(ascender_desc=self.ascender_data['geo_location_desc'])
            else:
                ascender_location = None
            if self.azure_ad_data['officeLocation'] and Location.objects.filter(name=self.azure_ad_data['officeLocation']).exists():
                ad_location = Location.objects.get(name=self.azure_ad_data['officeLocation'])
            else:
                ad_location = None
            # Only update if we matched a physical location from Ascender.
            if ascender_location and ascender_location != ad_location:
                # Update both officeLocation and streetAddress in Azure AD.
                if token:
                    headers = {
                        "Authorization": "Bearer {}".format(token["access_token"]),
                        "Content-Type": "application/json",
                    }
                    data = {
                        "officeLocation": ascender_location.name,
                        "streetAddress": ascender_location.address,
                    }
                    if not log_only:
                        requests.patch(url, headers=headers, json=data)
                    LOGGER.info(f'AZURE AD SYNC: {self} Azure AD account officeLocation set to {ascender_location.name}')
                    LOGGER.info(f'AZURE AD SYNC: {self} Azure AD account streetAddress set to {ascender_location.address}')

    def update_from_ascender_data(self):
        """For this DepartmentUser object, update the field values from cached Ascender data
        (the source of truth for these values).
        """
        if not self.employee_id or not self.ascender_data:
            return

        # First name - note that we use "preferred name" in place of legal first name here, and this should flow through to AD.
        if 'preferred_name' in self.ascender_data and self.ascender_data['preferred_name']:
            if not self.given_name:
                given_name = ''
            else:
                given_name = self.given_name
            if self.ascender_data['preferred_name'].upper() != given_name.upper():
                first_name = self.ascender_data['preferred_name'].title()
                LOGGER.info(f"ASCENDER SYNC: {self} first name {self.given_name} differs from Ascender preferred name name {first_name}, updating it")
                DepartmentUserLog.objects.create(
                    department_user=self,
                    log={
                        'ascender_field': 'first_name',
                        'old_value': self.given_name,
                        'new_value': first_name,
                        'description': 'Update given_name value from Ascender',
                    },
                )
                self.given_name = first_name
                self.name = f'{first_name} {self.surname}'  # Also update display name

        # Surname
        if 'surname' in self.ascender_data and self.ascender_data['surname']:
            if not self.surname:
                surname = ''
            else:
                surname = self.surname
            if self.ascender_data['surname'].upper() != surname.upper():
                new_surname = self.ascender_data['surname'].title()
                LOGGER.info(f"ASCENDER SYNC: {self} surname {self.surname} differs from Ascender surname {new_surname}, updating it")
                DepartmentUserLog.objects.create(
                    department_user=self,
                    log={
                        'ascender_field': 'surname',
                        'old_value': self.surname,
                        'new_value': new_surname,
                        'description': 'Update surname value from Ascender',
                    },
                )
                self.surname = new_surname
                self.name = f'{self.given_name} {new_surname}'  # Also update display name

        # Preferred name
        if 'preferred_name' in self.ascender_data and self.ascender_data['preferred_name']:
            if not self.preferred_name:
                preferred_name = ''
            else:
                preferred_name = self.preferred_name
            if self.ascender_data['preferred_name'].upper() != preferred_name.upper():
                new_preferred_name = self.ascender_data['preferred_name'].title()
                LOGGER.info(f"ASCENDER SYNC: {self} preferred name {self.preferred_name} differs from Ascender preferred name {new_preferred_name}, updating it")
                DepartmentUserLog.objects.create(
                    department_user=self,
                    log={
                        'ascender_field': 'preferred_name',
                        'old_value': self.preferred_name,
                        'new_value': new_preferred_name,
                        'description': 'Update preferred_name value from Ascender',
                    },
                )
                self.preferred_name = new_preferred_name
                self.name = f'{new_preferred_name} {self.surname}'  # Also update display name

        # Cost centre (Ascender records cost centre as 'paypoint').
        if 'paypoint' in self.ascender_data and CostCentre.objects.filter(ascender_code=self.ascender_data['paypoint']).exists():
            paypoint = self.ascender_data['paypoint']
            cc = CostCentre.objects.get(ascender_code=paypoint)

            # The user's current CC differs from that in Ascender (it might be None).
            if self.cost_centre != cc:
                if self.cost_centre:
                    LOGGER.info(f"ASCENDER SYNC: {self} cost centre {self.cost_centre.ascender_code} differs from Ascender paypoint {paypoint}, updating it")
                    DepartmentUserLog.objects.create(
                        department_user=self,
                        log={
                            'ascender_field': 'paypoint',
                            'old_value': self.cost_centre.ascender_code,
                            'new_value': paypoint,
                            'description': 'Update CC value from Ascender',
                        },
                    )
                else:
                    LOGGER.info(f"ASCENDER SYNC: {self} cost centre set from Ascender paypoint {paypoint}")
                    DepartmentUserLog.objects.create(
                        department_user=self,
                        log={
                            'ascender_field': 'paypoint',
                            'old_value': None,
                            'new_value': paypoint,
                            'description': 'Set CC value from Ascender',
                        },
                    )
                self.cost_centre = cc  # Change the department user's cost centre.
        elif 'paypoint' in self.ascender_data and not CostCentre.objects.filter(ascender_code=self.ascender_data['paypoint']).exists():
            LOGGER.warning('ASCENDER SYNC: Cost centre {} is not present in the IT Assets database, creating it'.format(self.ascender_data['paypoint']))
            new_cc = CostCentre.objects.create(code=paypoint, ascender_code=paypoint)
            self.cost_centre = new_cc
            LOGGER.info(f"ASCENDER SYNC: {self} cost centre set from Ascender paypoint {paypoint}")
            DepartmentUserLog.objects.create(
                department_user=self,
                log={
                    'ascender_field': 'paypoint',
                    'old_value': None,
                    'new_value': paypoint,
                    'description': 'Set CC value from Ascender',
                },
            )

        # Manager
        if 'manager_emp_no' in self.ascender_data and self.ascender_data['manager_emp_no'] and DepartmentUser.objects.filter(employee_id=self.ascender_data['manager_emp_no']).exists():
            manager = DepartmentUser.objects.get(employee_id=self.ascender_data['manager_emp_no'])
            # The user's current manager differs from that in Ascender (it might be set to None).
            if self.manager != manager:
                if self.manager:
                    LOGGER.info(f"ASCENDER SYNC: {self} manager {self.manager} differs from Ascender, updating it to {manager}")
                    DepartmentUserLog.objects.create(
                        department_user=self,
                        log={
                            'ascender_field': 'manager',
                            'old_value': self.manager.email,
                            'new_value': manager.email,
                            'description': 'Update manager value from Ascender',
                        },
                    )
                else:
                    LOGGER.info(f"ASCENDER SYNC: {self} manager set from Ascender to {manager}")
                    DepartmentUserLog.objects.create(
                        department_user=self,
                        log={
                            'ascender_field': 'manager',
                            'old_value': None,
                            'new_value': manager.email,
                            'description': 'Set manager value from Ascender',
                        },
                    )
                self.manager = manager  # Change the department user's manager.

        # Location
        if (
            'geo_location_desc' in self.ascender_data
            and self.ascender_data['geo_location_desc']
            and Location.objects.filter(ascender_desc=self.ascender_data['geo_location_desc']).exists()
        ):
            location = Location.objects.get(ascender_desc=self.ascender_data['geo_location_desc'])
            # The user's current location differs from that in Ascender.
            if self.location != location:
                if self.location:
                    LOGGER.info(f"ASCENDER SYNC: {self} location {self.location} differs from Ascender location {location}, updating it")
                    DepartmentUserLog.objects.create(
                        department_user=self,
                        log={
                            'ascender_field': 'geo_location_desc',
                            'old_value': self.location.name,
                            'new_value': location.name,
                            'description': 'Update location value from Ascender',
                        },
                    )
                else:
                    LOGGER.info(f"ASCENDER SYNC: {self} location set from Ascender location {location}")
                    DepartmentUserLog.objects.create(
                        department_user=self,
                        log={
                            'ascender_field': 'location',
                            'old_value': None,
                            'new_value': location.name,
                            'description': 'Set location value from Ascender',
                        },
                    )
                self.location = location

        # Title
        if 'occup_pos_title' in self.ascender_data and self.ascender_data['occup_pos_title']:
            ascender_title = title_except(self.ascender_data['occup_pos_title'])
            current_title = self.title if self.title else ''
            if ascender_title.upper() != current_title.upper():
                LOGGER.info(f"ASCENDER SYNC: {self} title {self.title} differs from Ascender title {ascender_title}, updating it")
                DepartmentUserLog.objects.create(
                    department_user=self,
                    log={
                        'ascender_field': 'occup_pos_title',
                        'old_value': self.title,
                        'new_value': ascender_title,
                        'description': 'Update title value from Ascender',
                    },
                )
                self.title = ascender_title

        self.save()

    def update_from_azure_ad_data(self):
        """For this DepartmentUser object, update the field values from cached Azure AD data
        (the source of truth for these values).
        """
        if not self.azure_guid or not self.azure_ad_data:
            return

        if 'accountEnabled' in self.azure_ad_data and self.azure_ad_data['accountEnabled'] != self.active:
            self.active = self.azure_ad_data['accountEnabled']
            LOGGER.info(f'AZURE AD SYNC: {self} active changed to {self.active}')
        if 'mail'in self.azure_ad_data and self.azure_ad_data['mail'] != self.email:
            LOGGER.info('AZURE AD SYNC: {} email changed to {}'.format(self, self.azure_ad_data['mail']))
            self.email = self.azure_ad_data['mail']
        if 'onPremisesSyncEnabled' in self.azure_ad_data:
            if not self.azure_ad_data['onPremisesSyncEnabled']:  # False/None
                self.dir_sync_enabled = False
            else:
                self.dir_sync_enabled = True
        if 'proxyAddresses' in self.azure_ad_data and self.azure_ad_data['proxyAddresses'] != self.proxy_addresses:
            self.proxy_addresses = self.azure_ad_data['proxyAddresses']

        # Just replace the assigned_licences value every time (no comparison).
        # We replace the SKU GUID values with (known) human-readable licence types, as appropriate.
        self.assigned_licences = []
        if 'assignedLicenses' in self.azure_ad_data:
            for sku in self.azure_ad_data['assignedLicenses']:
                if sku in self.MS_LICENCE_SKUS:
                    self.assigned_licences.append(self.MS_LICENCE_SKUS[sku])
                else:
                    self.assigned_licences.append(sku)

        self.save()


class DepartmentUserLog(models.Model):
    """Represents an event carried out on a DepartmentUser object that may need to be reported
    for audit purposes, e.g. change of security access due to change of position.
    """
    created = models.DateTimeField(auto_now_add=True)
    department_user = models.ForeignKey(DepartmentUser, on_delete=models.CASCADE)
    log = models.JSONField(default=dict, editable=False)

    def __str__(self):
        return '{} {} {}'.format(
            self.created.isoformat(),
            self.department_user,
            self.log,
        )


class ADAction(models.Model):
    """Represents a single "action" or change that needs to be carried out to the Active Directory
    object which matches a DepartmentUser object.
    DEPRECATED, to be removed.
    """
    ACTION_TYPE_CHOICES = (
        ('Change email', 'Change email'),  # Separate from 'change field' because this is a significant operation.
        ('Change account field', 'Change account field'),
        ('Disable account', 'Disable account'),
        ('Enable account', 'Enable account'),
    )
    created = models.DateTimeField(auto_now_add=True)
    department_user = models.ForeignKey(DepartmentUser, on_delete=models.CASCADE)
    action_type = models.CharField(max_length=128, choices=ACTION_TYPE_CHOICES)
    ad_field = models.CharField(max_length=128, blank=True, null=True, help_text='Name of the field in Active Directory')
    ad_field_value = models.TextField(blank=True, null=True, help_text='Value of the field in Active Directory')
    field = models.CharField(max_length=128, blank=True, null=True, help_text='Name of the field in IT Assets')
    field_value = models.TextField(blank=True, null=True, help_text='Value of the field in IT Assets')
    completed = models.DateTimeField(null=True, blank=True, editable=False)
    completed_by = models.ForeignKey(get_user_model(), on_delete=models.SET_NULL, null=True, blank=True, editable=False)

    class Meta:
        verbose_name = 'AD action'
        verbose_name_plural = 'AD actions'

    def __str__(self):
        return '{}: {} ({} -> {})'.format(
            self.department_user.azure_guid, self.action_type, self.ad_field, self.field_value
        )

    @property
    def azure_guid(self):
        return self.department_user.azure_guid

    @property
    def ad_guid(self):
        return self.department_user.ad_guid

    @property
    def action(self):
        return '{} {} to {}'.format(self.action_type, self.ad_field, self.field_value)

    def powershell_instructions(self):
        """Returns a PowerShell command to update the relevant Active Directory.
        """
        if self.department_user.dir_sync_enabled:  # Powershell instructions for onprem AD.
            if not self.department_user.ad_guid:
                return ''
            if self.ad_field == 'Manager':
                instructions = '$manager = Get-ADUser -Identity {}\nSet-ADUser -Identity {} -Manager $manager'.format(
                    self.department_user.manager.ad_guid, self.department_user.ad_guid)
            else:
                if self.field_value:
                    instructions = 'Set-ADUser -Identity {} -{} "{}"'.format(self.department_user.ad_guid, self.ad_field, self.field_value)
                else:
                    instructions = 'Set-ADUser -Identity {} -{} $null'.format(self.department_user.ad_guid, self.ad_field)
        else:  # Powershell instructions for Azure AD.
            if self.ad_field == 'Manager':
                instructions = 'Set-AzureADUserManager -ObjectId "{}" -RefObjectId "{}"'.format(self.department_user.azure_guid, self.department_user.manager.azure_guid)
            elif self.ad_field == 'EmployeeId':
                instructions = 'Set-AzureADUserExtension -ObjectId "{}" -ExtensionName "EmployeeId" -ExtensionValue "{}"'.format(self.department_user.azure_guid, self.field_value)
            else:
                if self.field_value:
                    instructions = 'Set-AzureADUser -ObjectId "{}" -{} "{}"'.format(self.department_user.azure_guid, self.ad_field, self.field_value)
                else:
                    instructions = 'Set-AzureADUser -ObjectId "{}" -{} $null'.format(self.department_user.azure_guid, self.ad_field)
            instructions = 'Connect-AzureAD\n' + instructions

        return instructions


class Location(models.Model):
    """A model to represent a physical location.
    """
    name = models.CharField(max_length=256, unique=True)
    address = models.TextField(unique=True, blank=True)
    pobox = models.TextField(blank=True, verbose_name='PO Box')
    phone = models.CharField(max_length=128, null=True, blank=True)
    fax = models.CharField(max_length=128, null=True, blank=True)
    point = models.PointField(null=True, blank=True)
    ascender_code = models.CharField(max_length=16, null=True, blank=True, unique=True)
    ascender_desc = models.CharField(max_length=128, null=True, blank=True)  # Equivalent to geo_location_desc field in Ascender.
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ('name',)

    def __str__(self):
        return self.name


class OrgUnit(models.Model):
    """Represents an element within the Department organisational hierarchy.
    """
    TYPE_CHOICES = (
        (0, 'Department (Tier one)'),
        (1, 'Division (Tier two)'),
        (11, 'Division'),
        (9, 'Group'),
        (2, 'Branch'),
        (7, 'Section'),
        (3, 'Region'),
        (6, 'District'),
        (8, 'Unit'),
        (5, 'Office'),
        (10, 'Work centre'),
    )
    active = models.BooleanField(default=True)
    unit_type = models.PositiveSmallIntegerField(choices=TYPE_CHOICES)
    name = models.CharField(max_length=256)
    acronym = models.CharField(max_length=16, null=True, blank=True)
    manager = models.ForeignKey(
        DepartmentUser, on_delete=models.SET_NULL, null=True, blank=True)
    location = models.ForeignKey(
        Location, on_delete=models.PROTECT, null=True, blank=True)
    division_unit = models.ForeignKey(
        'self', on_delete=models.PROTECT, null=True, blank=True,
        related_name='division_orgunits',
        help_text='Division-level unit to which this unit belongs',
    )
    ascender_clevel = models.CharField(max_length=128, null=True, blank=True, unique=True)

    class Meta:
        ordering = ('name',)

    def cc(self):
        return ', '.join([str(x) for x in self.costcentre_set.all()])

    def __str__(self):
        return self.name


DIVISION_CHOICES = (
    ("BCS", "DBCA Biodiversity and Conservation Science"),
    ("BGPA", "Botanic Gardens and Parks Authority"),
    ("CBS", "DBCA Corporate and Business Services"),
    ("CPC", "Conservation and Parks Commission"),
    ("ODG", "Office of the Director General"),
    ("PWS", "Parks and Wildlife Service"),
    ("RIA", "Rottnest Island Authority"),
    ("ZPA", "Zoological Parks Authority"),
)


class CostCentre(models.Model):
    """Models the details of a Department cost centre / chart of accounts.
    """
    active = models.BooleanField(default=True)
    code = models.CharField(max_length=16, unique=True)
    chart_acct_name = models.CharField(
        max_length=256, blank=True, null=True, verbose_name='chart of accounts name')
    division_name = models.CharField(max_length=128, choices=DIVISION_CHOICES, null=True, blank=True)
    org_position = models.ForeignKey(
        OrgUnit, on_delete=models.PROTECT, blank=True, null=True)
    manager = models.ForeignKey(
        DepartmentUser, on_delete=models.SET_NULL, related_name='manage_ccs',
        null=True, blank=True)
    business_manager = models.ForeignKey(
        DepartmentUser, on_delete=models.SET_NULL, related_name='bmanage_ccs',
        help_text='Business Manager', null=True, blank=True)
    admin = models.ForeignKey(
        DepartmentUser, on_delete=models.SET_NULL, related_name='admin_ccs',
        help_text='Adminstration Officer', null=True, blank=True)
    tech_contact = models.ForeignKey(
        DepartmentUser, on_delete=models.SET_NULL, related_name='tech_ccs',
        help_text='Technical Contact', null=True, blank=True)
    ascender_code = models.CharField(max_length=16, null=True, blank=True, unique=True)

    class Meta:
        ordering = ('code',)

    def __str__(self):
        return self.code
