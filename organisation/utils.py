from data_storage import AzureBlobStorage
from datetime import datetime, date
from django.conf import settings
import json
import os
import pytz
import requests
from itassets.utils import ms_graph_client_token

TZ = pytz.timezone(settings.TIME_ZONE)


def ascender_onprem_ad_data_diff(container='azuread', json_path='adusers.json'):
    """A utility function to compare on-premise AD user account data with Ascender HR data.
    """
    from organisation.ascender import ascender_employee_fetch
    print("Downloading Ascender data")
    employee_iter = ascender_employee_fetch()
    ascender_users = {}
    for eid, jobs in employee_iter:
        # Exclude FPC employees and employee having a job that is terminated.
        job = jobs[0]
        if job['clevel1_id'] != 'FPC':
            if not job['job_term_date'] or datetime.strptime(job['job_term_date'], '%Y-%m-%d').date() >= date.today():
                ascender_users[eid] = job

    print("Downloading on-prem AD data")
    ad_users = get_ad_users_json(container=container, azure_json_path=json_path)
    discrepancies = []

    # Iterate through the Ascender data, checking for mismatches with Azure AD data.
    for emp_id, user in ascender_users.items():
        ad_user = None

        # Find the matching Azure AD user.
        for u in ad_users:
            if 'EmployeeID' in u and u['EmployeeID'] == emp_id:
                ad_user = u
                break

        if ad_user:
            print("Checking {} against {}".format(emp_id, ad_user['EmailAddress']))

            # First name.
            if ad_user['GivenName'].upper() != user['first_name']:
                discrepancies.append({
                    'ascender_id': user['employee_id'],
                    'target': 'On-premise AD',
                    'target_pk': ad_user['ObjectGUID'],
                    'field': 'GivenName',
                    'old_value': ad_user['GivenName'],
                    'new_value': user['first_name'].capitalize(),
                    'action': 'Update onprem AD user {} GivenName to {}'.format(ad_user['ObjectGUID'], user['first_name'].capitalize()),
                })

            # Surname.
            if ad_user['Surname'].upper() != user['surname']:
                discrepancies.append({
                    'ascender_id': user['employee_id'],
                    'target': 'On-premise AD',
                    'target_pk': ad_user['ObjectGUID'],
                    'field': 'Surname',
                    'old_value': ad_user['Surname'],
                    'new_value': user['surname'].capitalize(),
                    'action': 'Update onprem AD user {} Surname to {}'.format(ad_user['ObjectGUID'], user['surname'].capitalize()),
                })

            # Phone number.
            if ad_user['telephoneNumber'] != user['work_phone_no']:
                discrepancies.append({
                    'ascender_id': user['employee_id'],
                    'target': 'On-premise AD',
                    'target_pk': ad_user['ObjectGUID'],
                    'field': 'telephoneNumber',
                    'old_value': ad_user['telephoneNumber'],
                    'new_value': user['work_phone_no'],
                    'action': 'Update onprem AD user {} telephoneNumber to {}'.format(ad_user['ObjectGUID'], user['work_phone_no']),
                })

            # Title
            if ad_user['Title'].upper() != user['occup_pos_title']:
                discrepancies.append({
                    'ascender_id': user['employee_id'],
                    'target': 'On-premise AD',
                    'target_pk': ad_user['ObjectGUID'],
                    'field': 'Title',
                    'old_value': ad_user['Title'],
                    'new_value': user['occup_pos_title'].title(),
                    'action': 'Update onprem AD user {} Title to {}'.format(ad_user['ObjectGUID'], user['occup_pos_title'].title()),
                })

            # Cost centre
            # We have to handle these a bit differently to the above.
            if user['paypoint'] and user['paypoint'] != ad_user['Company']:
                cc = False
                if user['paypoint'].startswith('R') and user['paypoint'].replace('R', '') != ad_user['Company'].replace('RIA-', ''):
                    cc = True
                    new_value = user['paypoint'].replace('R', 'RIA-')
                elif user['paypoint'].startswith('Z') and user['paypoint'].replace('Z', '') != ad_user['Company'].replace('ZPA-', ''):
                    cc = True
                    new_value = user['paypoint'].replace('Z', 'ZPA-')
                elif user['paypoint'][0] in '1234567890' and user['paypoint'] != ad_user['Company'].replace('DBCA-', ''):
                    cc = True
                    new_value = 'DBCA-{}'.format(user['paypoint'])
                # TODO: differences for BGPA cost centres.
                if cc:
                    discrepancies.append({
                        'ascender_id': user['employee_id'],
                        'target': 'On-premise AD',
                        'target_pk': ad_user['ObjectGUID'],
                        'field': 'Company',
                        'old_value': ad_user['Company'],
                        'new_value': new_value,
                        'action': 'Update onprem AD user {} Company to {}'.format(ad_user['ObjectGUID'], new_value),
                    })
        else:
            print("{} didn't match any onprem AD user".format(emp_id))

    return discrepancies


def ms_graph_users(licensed=False):
    """Query the Microsoft Graph REST API for on-premise user accounts in our tenancy.
    Passing ``licensed=True`` will return only those users having >0 licenses assigned.
    """
    token = ms_graph_client_token()
    headers = {
        "Authorization": "Bearer {}".format(token["access_token"]),
        "ConsistencyLevel": "eventual",
    }
    url = "https://graph.microsoft.com/v1.0/users?$select=id,mail,displayName,givenName,surname,employeeId,employeeType,jobTitle,businessPhones,mobilePhone,companyName,officeLocation,proxyAddresses,accountEnabled,onPremisesSyncEnabled,assignedLicenses&$filter=endswith(mail,'@dbca.wa.gov.au')&$orderby=userPrincipalName&$count=true"
    users = []
    resp = requests.get(url, headers=headers)
    j = resp.json()

    while '@odata.nextLink' in j:
        users = users + j['value']
        resp = requests.get(j['@odata.nextLink'], headers=headers)
        resp.raise_for_status()
        j = resp.json()

    users = users + j['value']  # Final page
    aad_users = []

    for user in users:
        aad_users.append({
            'objectId': user['id'],
            'mail': user['mail'].lower(),
            'displayName': user['displayName'] if user['displayName'] else '',
            'givenName': user['givenName'] if user['givenName'] else '',
            'surname': user['surname'] if user['surname'] else '',
            'employeeId': user['employeeId'] if user['employeeId'] else '',
            'employeeType': user['employeeType'] if user['employeeType'] else '',
            'jobTitle': user['jobTitle'] if user['jobTitle'] else '',
            'telephoneNumber': user['businessPhones'][0] if user['businessPhones'] else '',
            'mobilePhone': user['mobilePhone'] if user['mobilePhone'] else '',
            'companyName': user['companyName'] if user['companyName'] else '',
            'officeLocation': user['officeLocation'] if user['officeLocation'] else '',
            'proxyAddresses': [i.lower().replace('smtp:', '') for i in user['proxyAddresses'] if i.lower().startswith('smtp')],
            'accountEnabled': user['accountEnabled'],
            'onPremisesSyncEnabled': user['onPremisesSyncEnabled'],
            'assignedLicenses': [i['skuId'] for i in user['assignedLicenses']],
        })

    if licensed:
        return [u for u in aad_users if u['assignedLicenses']]
    else:
        return aad_users


def get_ad_users_json(container, azure_json_path):
    """Pass in the container name and path to a JSON dump of AD users, return parsed JSON.
    """
    connect_string = os.environ.get("AZURE_CONNECTION_STRING", None)
    if not connect_string:
        return None
    store = AzureBlobStorage(connect_string, container)
    return json.loads(store.get_content(azure_json_path))


def onprem_ad_data_import(container='azuread', json_path='adusers.json', verbose=False):
    """Utility function to download onprem AD data from blob storage, then copy it to matching DepartmentUser objects.
    """
    from organisation.models import DepartmentUser
    ad_users = get_ad_users_json(container=container, azure_json_path=json_path)
    ad_users = {i['ObjectGUID']: i for i in ad_users}

    for k, v in ad_users.items():
        if DepartmentUser.objects.filter(ad_guid=k).exists():
            du = DepartmentUser.objects.get(ad_guid=k)
            du.ad_data = v
            du.ad_data_updated = TZ.localize(datetime.now())
            du.save()
        else:
            if verbose:
                print("Could not match onprem AD GUID {} to a department user".format(k))


def azure_ad_data_import(verbose=False):
    """Utility function to download Azure AD data from MS Graph API, then copy it to matching DepartmentUser objects.
    """
    from organisation.models import DepartmentUser
    azure_ad_users = ms_graph_users(licensed=True)
    azure_ad_users = {u['objectId']: u for u in azure_ad_users}

    for k, v in azure_ad_users.items():
        if DepartmentUser.objects.filter(azure_guid=k).exists():
            du = DepartmentUser.objects.get(azure_guid=k)
            du.azure_ad_data = v
            du.azure_ad_data_updated = TZ.localize(datetime.now())
            du.save()
        else:
            if verbose:
                print("Could not match Azure GUID {} to a department user".format(k))


def compare_values(a, b):
    """A utility function to compare two values for equality, with the exception that 'falsy' values
    (e.g. None and '') are equal. This is used to account for differences in how data is returned
    from the different AD environments and APIs.
    """
    if not a and not b:
        return True

    return a == b
