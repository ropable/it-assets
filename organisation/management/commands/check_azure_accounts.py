import json
import logging
from datetime import datetime, timezone

from django.conf import settings
from django.core import mail
from django.core.management.base import BaseCommand
from sentry_sdk.crons import monitor

from organisation.models import CostCentre, DepartmentUser, Location
from organisation.utils import ms_graph_users


class Command(BaseCommand):
    help = "Checks licensed user accounts from Azure AD and updates linked DepartmentUser objects"

    def handle(self, *args, **options):
        logger = logging.getLogger("organisation")
        logger.info("Querying Microsoft Graph API for Azure AD user accounts")
        # Optionally run this management command in the context of a Sentry cron monitor.
        if settings.SENTRY_CRON_CHECK_AZURE:
            with monitor(monitor_slug=settings.SENTRY_CRON_CHECK_AZURE):
                logger.info(f"Applying Sentry Cron Monitor: {settings.SENTRY_CRON_CHECK_AZURE}")
                self.check_azure_accounts(logger)
        else:
            self.check_azure_accounts(logger)

        logger.info("Completed")

    def check_azure_accounts(self, logger):
        """Separate the body of this management command to allow running it in context with
        the Sentry monitor process.
        """
        azure_users = ms_graph_users()

        if not azure_users:
            logger.error("Microsoft Graph API returned no data")
            return

        logger.info("Comparing Department Users to Azure AD user accounts")
        for az in azure_users:
            if az["mail"] and az["displayName"]:  # Azure object has an email address and a display name; proceed.
                try:
                    if not DepartmentUser.objects.filter(azure_guid=az["objectId"]).exists():
                        # No existing DepartmentUser is linked to this Azure AD user.
                        # NOTE: a department user with matching email may already exist with a different azure_guid.
                        # If so, return a warning and skip that user.
                        # We'll need to correct this issue manually.
                        if DepartmentUser.objects.filter(email=az["mail"], azure_guid__isnull=False).exists():
                            existing_user = DepartmentUser.objects.filter(email=az["mail"]).first()
                            logger.warning(
                                f"Skipped {az['mail']}: email exists and already associated with Azure ObjectId {existing_user.azure_guid} (this ObjectId is {az['objectId']})"
                            )
                            continue  # Skip to the next Azure user.

                        # A department user with matching email may already exist in IT Assets with no azure_guid.
                        # If so, associate the Azure AD objectId with that user.
                        if DepartmentUser.objects.filter(email=az["mail"], azure_guid__isnull=True).exists():
                            existing_user = DepartmentUser.objects.filter(email=az["mail"]).first()
                            existing_user.azure_guid = az["objectId"]
                            existing_user.azure_ad_data = az
                            existing_user.azure_ad_data_updated = datetime.now(timezone.utc)
                            existing_user.update_from_entra_id_data()  # This method calls save()
                            logger.info(f"Linked existing user {az['mail']} with Azure objectId {az['objectId']}")
                            continue  # Skip to the next Azure user.

                        # Only create a new DepartmentUser instance if the Azure AD account has an E5 or F3 licence assigned.
                        user_licences = ["MICROSOFT 365 E5", "MICROSOFT 365 F3"]
                        if az["assignedLicenses"] and any(x in user_licences for x in az["assignedLicenses"]):
                            if az["companyName"] and CostCentre.objects.filter(code=az["companyName"]).exists():
                                cost_centre = CostCentre.objects.get(code=az["companyName"])
                            else:
                                cost_centre = None

                            if az["officeLocation"] and Location.objects.filter(name=az["officeLocation"]).exists():
                                location = Location.objects.get(name=az["officeLocation"])
                            else:
                                location = None

                            new_user = DepartmentUser.objects.create(
                                azure_guid=az["objectId"],
                                azure_ad_data=az,
                                azure_ad_data_updated=datetime.now(timezone.utc),
                                active=az["accountEnabled"],
                                email=az["mail"],
                                name=az["displayName"],
                                given_name=az["givenName"],
                                surname=az["surname"],
                                title=az["jobTitle"],
                                telephone=az["telephoneNumber"],
                                mobile_phone=az["mobilePhone"],
                                employee_id=az["employeeId"],
                                cost_centre=cost_centre,
                                location=location,
                                dir_sync_enabled=az["onPremisesSyncEnabled"],
                            )
                            logger.info(f"Created new department user {new_user}")
                    elif DepartmentUser.objects.filter(azure_guid=az["objectId"]).exists():
                        # An existing DepartmentUser is linked to this Azure AD user.
                        # Update the existing DepartmentUser object fields with values from Azure.
                        existing_user = DepartmentUser.objects.get(azure_guid=az["objectId"])
                        existing_user.azure_ad_data = az
                        existing_user.azure_ad_data_updated = datetime.now(timezone.utc)
                        existing_user.update_from_entra_id_data()  # This method calls save()
                except Exception as e:
                    # In the event of an exception, fail gracefully and alert the admins.
                    subject = f"AZURE AD SYNC: exception during sync of Azure AD account (object {az['objectId']})"
                    logger.error(subject)
                    message = f"Azure data:\n{json.dumps(az, indent=2)}\nException:\n{str(e)}\n"
                    html_message = f"<p>Azure data:</p><p>{json.dumps(az, indent=2)}</p><p>Exception:</p><p>{str(e)}\n</p>"
                    mail.send_mail(
                        subject=subject,
                        message=message,
                        from_email=settings.NOREPLY_EMAIL,
                        recipient_list=settings.ADMIN_EMAILS,
                        html_message=html_message,
                    )

        logger.info("Checking for invalid Azure GUIDs")
        azure_guids = [az["objectId"] for az in azure_users]
        dept_users = DepartmentUser.objects.filter(azure_guid__isnull=False)
        for user in dept_users:
            if user.azure_guid not in azure_guids:
                logger.info(f"Azure GUID {user.azure_guid} invalid, clearing it from {user}")
                user.azure_guid = None
                user.save()
