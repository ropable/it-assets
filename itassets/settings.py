import os
import sys
import tomllib
from pathlib import Path
from zoneinfo import ZoneInfo

import dj_database_url
from dbca_utils.utils import env
from django.core.exceptions import DisallowedHost
from django.db.utils import OperationalError
from redis.exceptions import ConnectionError

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = str(Path(__file__).resolve().parents[1])
PROJECT_DIR = str(Path(__file__).resolve().parents[0])
# Add PROJECT_DIR to the system path.
sys.path.insert(0, PROJECT_DIR)

# Settings defined in environment variables.
DEBUG = env("DEBUG", False)
SECRET_KEY = env("SECRET_KEY", "PlaceholderSecretKey")
CSRF_COOKIE_SECURE = env("CSRF_COOKIE_SECURE", False)
CSRF_TRUSTED_ORIGINS = env("CSRF_TRUSTED_ORIGINS", "http://127.0.0.1").split(",")
SESSION_COOKIE_SECURE = env("SESSION_COOKIE_SECURE", False)
if not DEBUG:
    ALLOWED_HOSTS = env("ALLOWED_HOSTS", "").split(",")
else:
    ALLOWED_HOSTS = ["*"]
INTERNAL_IPS = ["127.0.0.1", "::1"]
ROOT_URLCONF = "itassets.urls"
WSGI_APPLICATION = "itassets.wsgi.application"
DEFAULT_AUTO_FIELD = "django.db.models.AutoField"
GEOSERVER_URL = env("GEOSERVER_URL", "")
LOGIN_URL = "/admin/login/"
LOGIN_REDIRECT_URL = "/"
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        # Use whitenoise to add compression and caching support for static files.
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

# Assume Azure blob storage is used for media uploads, unless explicitly set as local storage.
LOCAL_MEDIA_STORAGE = env("LOCAL_MEDIA_STORAGE", False)
if LOCAL_MEDIA_STORAGE:
    if not os.path.exists(os.path.join(BASE_DIR, "media")):
        os.mkdir(os.path.join(BASE_DIR, "media"))
    MEDIA_ROOT = os.path.join(BASE_DIR, "media")
else:
    STORAGES["default"] = {
        "BACKEND": "storages.backends.azure_storage.AzureStorage",
    }
    AZURE_ACCOUNT_NAME = env("AZURE_ACCOUNT_NAME", "name")
    AZURE_ACCOUNT_KEY = env("AZURE_ACCOUNT_KEY", "key")
    AZURE_CONTAINER = env("AZURE_CONTAINER", "container")
    AZURE_URL_EXPIRATION_SECS = env("AZURE_URL_EXPIRATION_SECS", 3600)  # Default one hour.

INSTALLED_APPS = (
    "whitenoise.runserver_nostatic",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.messages",
    "django.contrib.sessions",
    "django.contrib.sites",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "django_extensions",
    "webtemplate_dbca",
    "organisation",
    "registers",
)

MIDDLEWARE = [
    "itassets.middleware.HealthCheckMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.cache.UpdateCacheMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.cache.FetchFromCacheMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "dbca_utils.middleware.SSOLoginMiddleware",
]

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": (os.path.join(BASE_DIR, "itassets", "templates"),),
        "APP_DIRS": True,
        "OPTIONS": {
            "debug": DEBUG,
            "context_processors": [
                "django.contrib.auth.context_processors.auth",
                "django.template.context_processors.debug",
                "django.template.context_processors.i18n",
                "django.template.context_processors.media",
                "django.template.context_processors.static",
                "django.template.context_processors.tz",
                "django.template.context_processors.request",
                "django.template.context_processors.csrf",
                "django.contrib.messages.context_processors.messages",
                "itassets.context_processors.from_settings",
            ],
        },
    }
]
SERIALIZATION_MODULES = {
    "geojson": "django.contrib.gis.serializers.geojson",
}

# Caching config
REDIS_CACHE_HOST = env("REDIS_CACHE_HOST", "")
if REDIS_CACHE_HOST:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": REDIS_CACHE_HOST,
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.dummy.DummyCache",
        }
    }
API_RESPONSE_CACHE_SECONDS = env("API_RESPONSE_CACHE_SECONDS", 60)
CACHE_MIDDLEWARE_SECONDS = env("CACHE_MIDDLEWARE_SECONDS", 60)

ADMIN_EMAILS = env("ADMIN_EMAILS", "asi@dbca.wa.gov.au").split(",")
SERVICE_DESK_EMAIL = env("SERVICE_DESK_EMAIL", "oim.servicedesk@dbca.wa.gov.au")
SITE_ID = 1
ENVIRONMENT_NAME = env("ENVIRONMENT_NAME", "")
ENVIRONMENT_COLOUR = env("ENVIRONMENT_COLOUR", "")

pyproject = open(os.path.join(BASE_DIR, "pyproject.toml"), "rb")
project = tomllib.load(pyproject)
pyproject.close()
VERSION_NO = project["project"]["version"]

# Threshold value below which to warn Service Desk about available Microsoft licenses.
LICENCE_NOTIFY_THRESHOLD = env("LICENCE_NOTIFY_THRESHOLD", 5)

# Flag to control whether Azure AD accounts should be deactivated during sync
# processes if their associated job in Ascender has a termination date in the past.
ASCENDER_DEACTIVATE_EXPIRED = env("ASCENDER_DEACTIVATE_EXPIRED", False)
# Flag to control whether new Azure AD accounts should be created during sync.
ASCENDER_CREATE_AZURE_AD = env("ASCENDER_CREATE_AZURE_AD", False)
# Flag to set how many days ahead of their start date a new AD account should be created.
# False == no limit. Value should be a positive integer value.
ASCENDER_CREATE_AZURE_AD_LIMIT_DAYS = env("ASCENDER_CREATE_AZURE_AD_LIMIT_DAYS", -1)
# Number of days after which an Entra ID account may be considered "dormant":
DORMANT_ACCOUNT_DAYS = env("DORMANT_ACCOUNT_DAYS", 90)

# Settings related to the Ascender SFTP target
ASCENDER_SFTP_HOST = env("ASCENDER_SFTP_HOST", None)
ASCENDER_SFTP_PORT = env("ASCENDER_SFTP_PORT", 22)
ASCENDER_SFTP_USERNAME = env("ASCENDER_SFTP_USERNAME", None)
ASCENDER_SFTP_PASSWORD = env("ASCENDER_SFTP_PASSWORD", None)

# Ascender database view information
FOREIGN_DB_HOST = env("FOREIGN_DB_HOST", None)
FOREIGN_DB_PORT = env("FOREIGN_DB_PORT", default=5432)
FOREIGN_DB_NAME = env("FOREIGN_DB_NAME", None)
FOREIGN_DB_USERNAME = env("FOREIGN_DB_USERNAME", None)
FOREIGN_DB_PASSWORD = env("FOREIGN_DB_PASSWORD", None)
FOREIGN_SERVER = env("FOREIGN_SERVER", None)
FOREIGN_SCHEMA = env("FOREIGN_SCHEMA", default="public")
FOREIGN_TABLE = env("FOREIGN_TABLE", None)
FOREIGN_TABLE_CC_MANAGER = env("FOREIGN_TABLE_CC_MANAGER", None)

# Database configuration
DATABASES = {
    # Defined in DATABASE_URL env variable.
    "default": dj_database_url.config(),
}

DATABASES["default"]["TIME_ZONE"] = "Australia/Perth"
# Use PostgreSQL connection pool if using that DB engine (use ConnectionPool defaults).
if "ENGINE" in DATABASES["default"] and any(eng in DATABASES["default"]["ENGINE"] for eng in ["postgresql", "postgis"]):
    if "OPTIONS" in DATABASES["default"]:
        DATABASES["default"]["OPTIONS"]["pool"] = True
    else:
        DATABASES["default"]["OPTIONS"] = {"pool": True}

# Static files configuration
STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")
STATIC_URL = "/static/"
STATICFILES_DIRS = (os.path.join(BASE_DIR, "itassets", "static"),)
WHITENOISE_ROOT = STATIC_ROOT

# Media uploads
MEDIA_URL = "/media/"


# Internationalisation.
USE_I18N = False
USE_TZ = True
TIME_ZONE = "Australia/Perth"
TZ = ZoneInfo(TIME_ZONE)
LANGUAGE_CODE = "en-us"
DATE_INPUT_FORMATS = (
    "%d/%m/%Y",
    "%d/%m/%y",
    "%d-%m-%Y",
    "%d-%m-%y",
    "%d %b %Y",
    "%d %b, %Y",
    "%d %B %Y",
    "%d %B, %Y",
)
DATETIME_INPUT_FORMATS = (
    "%d/%m/%Y %H:%M",
    "%d/%m/%y %H:%M",
    "%d-%m-%Y %H:%M",
    "%d-%m-%y %H:%M",
)


# Email settings.
EMAIL_HOST = env("EMAIL_HOST", "email.host")
EMAIL_PORT = env("EMAIL_PORT", 25)
NOREPLY_EMAIL = env("NOREPLY_EMAIL", "noreply@dbca.wa.gov.au")


# Logging settings - log to stdout/stderr
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "console": {
            "format": "{asctime} {levelname} {name} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "level": "INFO",
            "class": "logging.StreamHandler",
            "stream": sys.stdout,
            "formatter": "console",
        },
    },
    "loggers": {
        "": {
            "handlers": ["console"],
            "level": "DEBUG" if DEBUG else "INFO",
        },
        "itassets": {"handlers": ["console"], "level": "INFO"},
        # Microsoft Authentication Libraries logging.
        "msal": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
        # Azure libraries logging.
        "azure": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
    },
}


def sentry_excluded_exceptions(event, hint):
    """Exclude defined class(es) of Exception from being reported to Sentry.
    These exception classes are generally related to operational or configuration issues,
    and they are not errors that we want to capture.
    https://docs.sentry.io/platforms/python/configuration/filtering/#filtering-error-events
    """
    if "exc_info" in hint and hint["exc_info"]:
        # Exclude database-related errors (connection error, timeout, DNS failure, etc.)
        if hint["exc_info"][0] is OperationalError:
            return None
        # Exclude exceptions related to host requests not in ALLOWED_HOSTS.
        elif hint["exc_info"][0] is DisallowedHost:
            return None
        # Exclude Redis service connection errors.
        elif hint["exc_info"][0] is ConnectionError:
            return None

    return event


# Sentry settings
SENTRY_DSN = env("SENTRY_DSN", None)
SENTRY_SAMPLE_RATE = env("SENTRY_SAMPLE_RATE", 1.0)  # Error sampling rate
SENTRY_TRANSACTION_SAMPLE_RATE = env("SENTRY_TRANSACTION_SAMPLE_RATE", 0.0)  # Transaction sampling
SENTRY_PROFILES_SAMPLE_RATE = env("SENTRY_PROFILES_SAMPLE_RATE", 0.0)  # Proportion of sampled transactions to profile.
SENTRY_ENVIRONMENT = env("SENTRY_ENVIRONMENT", None)
if SENTRY_DSN and SENTRY_ENVIRONMENT:
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        sample_rate=SENTRY_SAMPLE_RATE,
        traces_sample_rate=SENTRY_TRANSACTION_SAMPLE_RATE,
        profiles_sample_rate=SENTRY_PROFILES_SAMPLE_RATE,
        environment=SENTRY_ENVIRONMENT,
        release=VERSION_NO,
        before_send=sentry_excluded_exceptions,
        integrations=[DjangoIntegration(cache_spans=True)],
    )

# Sentry crons
SENTRY_CRON_CHECK_ASCENDER = env("SENTRY_CRON_CHECK_ASCENDER", None)
SENTRY_CRON_CHECK_AZURE = env("SENTRY_CRON_CHECK_AZURE", None)
SENTRY_CRON_CHECK_ONPREM = env("SENTRY_CRON_CHECK_ONPREM", None)
