"""
Base settings to build other settings files upon.
"""
import logging
import os
import sys
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve(strict=True).parent.parent.parent
# centauron/
APPS_DIR = BASE_DIR / "apps"
env = environ.Env()

READ_DOT_ENV_FILE = env.bool("DJANGO_READ_DOT_ENV_FILE", default=True)
if READ_DOT_ENV_FILE:
    # OS environment variables take precedence over variables from .env
    env.read_env(str(BASE_DIR / ".env"))

# GENERAL
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#debug
DEBUG = env.bool("DJANGO_DEBUG", False)
# Local time zone. Choices are
# http://en.wikipedia.org/wiki/List_of_tz_zones_by_name
# though not all of them may be available with every OS.
# In Windows, this must be set to your system time zone.
TIME_ZONE = "UTC"
# https://docs.djangoproject.com/en/dev/ref/settings/#language-code
LANGUAGE_CODE = "en-us"
# https://docs.djangoproject.com/en/dev/ref/settings/#site-id
SITE_ID = 1
# https://docs.djangoproject.com/en/dev/ref/settings/#use-i18n
USE_I18N = True
# https://docs.djangoproject.com/en/dev/ref/settings/#use-tz
USE_TZ = True
# https://docs.djangoproject.com/en/dev/ref/settings/#locale-paths
LOCALE_PATHS = [str(BASE_DIR / "locale")]

# DATABASES
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#databases
DATABASES = {"default": env.db("DATABASE_URL")}
DATABASES["default"]["ATOMIC_REQUESTS"] = True
# https://docs.djangoproject.com/en/stable/ref/settings/#std:setting-DEFAULT_AUTO_FIELD
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# URLS
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#root-urlconf
ROOT_URLCONF = "config.urls"
# https://docs.djangoproject.com/en/dev/ref/settings/#wsgi-application
WSGI_APPLICATION = "config.wsgi.application"

# APPS
# ------------------------------------------------------------------------------
DJANGO_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.sites",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",  # Handy template tags
    "django.contrib.admin",
    "django.forms",
]
THIRD_PARTY_APPS = [
    "crispy_forms",
    "crispy_bootstrap5",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.openid_connect",
    "django_celery_beat",
    "rest_framework",
    "rest_framework.authtoken",
    "corsheaders",
    "drf_spectacular",
    "webpack_loader",
    "annoying",
    'rest_framework_datatables',
    'django_filters',
    'active_link',
    'constance'
    # 'django_components'
]

LOCAL_APPS = [
    "apps.user",
    "apps.user.user_profile",
    "apps.user.user_group",
    "apps.auth.apps.AuthConfig",
    "apps.auth.auth_certificate",
    "apps.auth.auth_jwt",
    "apps.challenge",
    "apps.challenge.challenge_dataset",
    "apps.challenge.challenge_submission",
    "apps.challenge.challenge_client",
    'apps.challenge.challenge_targetmetric',
    'apps.challenge.challenge_leaderboard',
    "apps.computing",
    "apps.computing.computing_artifact",
    "apps.computing.computing_executions",
    "apps.computing.computing_log",
    "apps.core",
    "apps.project",
    "apps.project.project_case",
    "apps.project.project_ground_truth",
    "apps.share",
    "apps.share.share_token",
    "apps.storage",
    'apps.storage.storage_importer',
    'apps.storage.storage_exporter',
    'apps.federation',
    'apps.federation.inbox',
    'apps.federation.outbox',
    'apps.federation.file_transfer',
    'apps.permission',
    'apps.study_management',
    'apps.study_management.import_data',
    'apps.study_management.tile_management',
    'apps.storage.fileset',
    'apps.storage.extra_data',
    'apps.terminology',
    'apps.node',
    'apps.event',
    'apps.viewer',
    'apps.viewer.wsi',
    'apps.viewer.image',
    'apps.federation.federation_invitation',
    'apps.blockchain',
]
# https://docs.djangoproject.com/en/dev/ref/settings/#installed-apps
INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# MIGRATIONS
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#migration-modules
MIGRATION_MODULES = {"sites": "apps.contrib.sites.migrations"}

# AUTHENTICATION
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#authentication-backends
AUTHENTICATION_BACKENDS = [
    # 'apps.auth.authentication.SSOAuthenticationBackend',
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]
# https://docs.djangoproject.com/en/dev/ref/settings/#auth-user-model
# AUTH_USER_MODEL = "apps.sers.User"
# https://docs.djangoproject.com/en/dev/ref/settings/#login-redirect-url
# LOGIN_REDIRECT_URL = "project:list"
LOGIN_REDIRECT_URL = env.str('LOGIN_REDIRECT_URL', default='/')
# https://docs.djangoproject.com/en/dev/ref/settings/#login-url
LOGIN_URL = 'account_login'
LOGOUT_REDIRECT_URL = 'account_login'
# PASSWORDS
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#password-hashers
PASSWORD_HASHERS = [
    # https://docs.djangoproject.com/en/dev/topics/auth/passwords/#using-argon2-with-django
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
    "django.contrib.auth.hashers.BCryptSHA256PasswordHasher",
]
# https://docs.djangoproject.com/en/dev/ref/settings/#auth-password-validators
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# MIDDLEWARE
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#middleware
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    'apps.auth.middleware.SSOMiddleware',
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",
]

# STATIC
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#static-root
STATIC_ROOT = str(BASE_DIR / "staticfiles")
# https://docs.djangoproject.com/en/dev/ref/settings/#static-url
STATIC_URL = "/static/"
# https://docs.djangoproject.com/en/dev/ref/contrib/staticfiles/#std:setting-STATICFILES_DIRS
STATICFILES_DIRS = [BASE_DIR / "static", BASE_DIR / 'resources']
# https://docs.djangoproject.com/en/dev/ref/contrib/staticfiles/#staticfiles-finders
STATICFILES_FINDERS = [
    "django.contrib.staticfiles.finders.FileSystemFinder",
    "django.contrib.staticfiles.finders.AppDirectoriesFinder",
]

# MEDIA
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#media-root
MEDIA_ROOT = str(BASE_DIR / "media")
# https://docs.djangoproject.com/en/dev/ref/settings/#media-url
MEDIA_URL = "/media/"

# TEMPLATES
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#templates
TEMPLATES = [
    {
        # https://docs.djangoproject.com/en/dev/ref/settings/#std:setting-TEMPLATES-BACKEND
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        # https://docs.djangoproject.com/en/dev/ref/settings/#dirs
        "DIRS": [str(BASE_DIR / 'templates'), str(APPS_DIR / "templates")],
        # https://docs.djangoproject.com/en/dev/ref/settings/#app-dirs
        "APP_DIRS": True,
        "OPTIONS": {
            # https://docs.djangoproject.com/en/dev/ref/settings/#template-context-processors
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.template.context_processors.i18n",
                "django.template.context_processors.media",
                "django.template.context_processors.static",
                "django.template.context_processors.tz",
                "django.contrib.messages.context_processors.messages",
                # "centauron.users.context_processors.allauth_settings",
            ],
            # 'loaders': [(
            #     'django.template.loaders.cached.Loader', [
            #         'django.template.loaders.filesystem.Loader',
            #         'django.template.loaders.app_directories.Loader',
            #         'django_components.template_loader.Loader',
            #     ]
            # )],
            # 'builtins': [
            #     'django_components.templatetags.component_tags',
            # ]
        },
    }
]

# https://docs.djangoproject.com/en/dev/ref/settings/#form-renderer
FORM_RENDERER = "django.forms.renderers.TemplatesSetting"

# http://django-crispy-forms.readthedocs.io/en/latest/install.html#template-packs
CRISPY_TEMPLATE_PACK = "bootstrap5"
CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"

# FIXTURES
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#fixture-dirs
FIXTURE_DIRS = (str(APPS_DIR / "fixtures"),)

# SECURITY
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#session-cookie-httponly
SESSION_COOKIE_HTTPONLY = True
# https://docs.djangoproject.com/en/dev/ref/settings/#csrf-cookie-httponly
CSRF_COOKIE_HTTPONLY = True
# https://docs.djangoproject.com/en/dev/ref/settings/#x-frame-options
X_FRAME_OPTIONS = "DENY"

# EMAIL
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#email-backend
EMAIL_BACKEND = env(
    "DJANGO_EMAIL_BACKEND",
    default="django.core.mail.backends.smtp.EmailBackend",
)
# https://docs.djangoproject.com/en/dev/ref/settings/#email-timeout
EMAIL_TIMEOUT = 5

# ADMIN
# ------------------------------------------------------------------------------
# Django Admin URL.
ADMIN_URL = "admin/"
# https://docs.djangoproject.com/en/dev/ref/settings/#admins
ADMINS = [("""Andreas Keil""", "andreas.keil@stcmed.com")]
# https://docs.djangoproject.com/en/dev/ref/settings/#managers
MANAGERS = ADMINS

# LOGGING
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#logging
# See https://docs.djangoproject.com/en/dev/topics/logging for
# more details on how to customize your logging configuration.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "%(levelname)s %(asctime)s %(module)s %(process)d %(thread)d %(message)s",
        },
    },
    "handlers": {
        "console": {
            "level": "DEBUG",
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": os.getenv("DJANGO_LOG_LEVEL", "INFO"),
            "propagate": False,
        },
    },
    "root": {"level": "INFO", "handlers": ["console"]},
}

# Celery
# ------------------------------------------------------------------------------
if USE_TZ:
    # https://docs.celeryq.dev/en/stable/userguide/configuration.html#std:setting-timezone
    CELERY_TIMEZONE = TIME_ZONE
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#std:setting-broker_url
CELERY_BROKER_URL = env("CELERY_BROKER_URL")
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#std:setting-result_backend
CELERY_RESULT_BACKEND = env.str('CELERY_RESULT_BACKEND', 'rpc://')
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#result-extended
CELERY_RESULT_EXTENDED = True
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#result-backend-always-retry
# https://github.com/celery/celery/pull/6122
CELERY_RESULT_BACKEND_ALWAYS_RETRY = True
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#result-backend-max-retries
CELERY_RESULT_BACKEND_MAX_RETRIES = 10
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#std:setting-accept_content
CELERY_ACCEPT_CONTENT = ["json"]
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#std:setting-task_serializer
CELERY_TASK_SERIALIZER = "json"
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#std:setting-result_serializer
CELERY_RESULT_SERIALIZER = "json"
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#task-time-limit
# TODO: set to whatever value is adequate in your circumstances
CELERY_TASK_TIME_LIMIT = 5 * 60
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#task-soft-time-limit
# TODO: set to whatever value is adequate in your circumstances
CELERY_TASK_SOFT_TIME_LIMIT = 5 * 60
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#beat-scheduler
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#worker-send-task-events
CELERY_WORKER_SEND_TASK_EVENTS = True
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#std-setting-task_send_sent_event
CELERY_TASK_SEND_SENT_EVENT = True

# django-rest-framework
# -------------------------------------------------------------------------------
# django-rest-framework - https://www.django-rest-framework.org/api-guide/settings/
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework.authentication.TokenAuthentication",
        'apps.auth.auth_jwt.authentication.JWTAuthentication',
        "rest_framework.authentication.SessionAuthentication",
        'apps.auth.auth_certificate.authentication.CertificateAuthentication'
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    # "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
        'rest_framework_datatables.renderers.DatatablesRenderer',
    ],
    'DEFAULT_FILTER_BACKENDS': [
        'rest_framework_datatables.filters.DatatablesFilterBackend',
        'django_filters.rest_framework.DjangoFilterBackend',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework_datatables.pagination.DatatablesPageNumberPagination',
    'PAGE_SIZE': 50,
}

# django-cors-headers - https://github.com/adamchainz/django-cors-headers#setup
CORS_URLS_REGEX = r"^/api/.*$"

# By Default swagger ui is available only to admin user(s). You can change permission classes to change that
# See more configuration options at https://drf-spectacular.readthedocs.io/en/latest/settings.html#settings
SPECTACULAR_SETTINGS = {
    "TITLE": "centauron API",
    "DESCRIPTION": "Documentation of API endpoints of centauron",
    "VERSION": "1.0.0",
    "SERVE_PERMISSIONS": ["rest_framework.permissions.IsAdminUser"],
}
# django-webpack-loader
# ------------------------------------------------------------------------------
WEBPACK_LOADER = {
    "DEFAULT": {
        "CACHE": not DEBUG,
        "STATS_FILE": BASE_DIR / "webpack-stats.json",
        "POLL_INTERVAL": 0.1,
        "IGNORE": [r".+\.hot-update.js", r".+\.map"],
    }
}
# Your stuff...
# ------------------------------------------------------------------------------
FILE_UPLOAD_HANDLERS = [
    "django.core.files.uploadhandler.TemporaryFileUploadHandler"
]

KEYCLOAK_URL = env.str('KEYCLOAK_URL')
if not KEYCLOAK_URL.endswith('/'):
    KEYCLOAK_URL += '/'

KEYCLOAK_CLIENT_ID = env.str('KEYCLOAK_CLIENT_ID')
KEYCLOAK_REALM = env.str('KEYCLOAK_REALM', None)
if KEYCLOAK_REALM is None:
    KEYCLOAK_REALM = 'master'
KEYCLOAK_CLIENT_SECRET = env.str('KEYCLOAK_CLIENT_SECRET')
KEYCLOAK_PUBLIC_KEY = env.str('KEYCLOAK_PUBLIC_KEY')

SOCIALACCOUNT_ADAPTER = 'apps.user.adapter.CentauronSocialAccountAdapter'
SOCIALACCOUNT_PROVIDERS = {
    "openid_connect": {
        "APPS": [
            {
                "provider_id": "keycloak",
                "name": "Keycloak",
                "client_id": KEYCLOAK_CLIENT_ID,
                "secret": KEYCLOAK_CLIENT_SECRET,
                "settings": {
                    "server_url": f"{KEYCLOAK_URL}realms/{KEYCLOAK_REALM}/.well-known/openid-configuration",
                },
            }
        ]
    }
}
SOCIALACCOUNT_STORE_TOKENS = True

ACTIVE_LINK_STRICT = True

# the base identifier a fqdn e.g. centauron.tiga.com
IDENTIFIER = env.str('IDENTIFIER')
if '#' in IDENTIFIER:
    print('base identifier should be fqdn and not contain a #.')
    sys.exit()

FHIR_SERVER = env.str('FHIR_SERVER', '')
if not FHIR_SERVER.endswith('/'):
    FHIR_SERVER += '/'

TMP_DIR = Path(env.str('TMP_DIR', '/tmp/')).absolute()
TMP_DIR.mkdir(parents=True, exist_ok=True)

STORAGE_IMPORT_DIR: Path = Path(env.str('STORAGE_IMPORTER_IMPORT_DIR', '/import/')).absolute()
STORAGE_IMPORT_DIR.mkdir(parents=True, exist_ok=True)

STORAGE_DATA_DIR: Path = Path(env.str('STORAGE_DATA_DIR', '/data/')).absolute()
STORAGE_DATA_DIR.mkdir(parents=True, exist_ok=True)

STORAGE_EXPORT_DIR: Path = Path(env.str('STORAGE_EXPORT_DIR', '/export/')).absolute()
STORAGE_EXPORT_DIR.mkdir(parents=True, exist_ok=True)

CLEAN_UP_OLD_FILES_DAYS_THRESHOLD = env.int('STORAGE_CLEAN_UP_OLD_FILES_DAYS_THRESHOLD', 5)
IMPORTER_FLUSH_EVERY = env.int('STORAGE_IMPORTER_FLUSH_EVERY', 500_000)

CA_DIR = Path(env.str('CA_DIR', 'ca_certs/'))

CERTS_DIR = Path(env.str('CERTS_DIR', '/certs/'))
CERTS_DIR.mkdir(parents=True, exist_ok=True)
CERTS_DIR_NODES = Path(env.str('CERTS_DIR_NODES', CERTS_DIR / 'nodes'))
CERTS_DIR_NODES.mkdir(parents=True, exist_ok=True)

ADDRESS = env.str('ADDRESS')
if ADDRESS.endswith('/'):
    # remove trailing slash: function that use the address will use the django fn reverse() and that returns a / as prefix
    ADDRESS = ADDRESS[:-1]

EXTERNAL_ADDRESS = env.str('ADDRESS')  # used for k8s sidecar to communicate with centauron
if not EXTERNAL_ADDRESS.endswith('/'):
    EXTERNAL_ADDRESS += '/'

COMMON_NAME = env.str('COMMON_NAME')  # as specified in dsf certificate
VERIFY_TLS = env.bool('VERIFY_TLS', True)
MY_DEV_CREDENTIALS = {
    'X-FORWARDED-TLS-CLIENT-CERT-INFO': f'Subject%3D%22CN%3DCOMMON_NAME%22'.replace('COMMON_NAME',
                                                                                    COMMON_NAME)}  # example how traefik forwards the cn: Subject%3D%22CN%3Dak-demo%22

DOWNLOADER_TMP_DIR = Path(env.str('DOWNLOADER_TMP_DIR', '/downloads'))
DOWNLOADER_SECRET = env.str('DOWNLOADER_SECRET')
DOWNLOADER_ADDRESS = env.str('DOWNLOADER_ADDRESS')
# the directory inside the aria2 container that contains the certificates
DOWNLOADER_CERT_DIR = Path(env.str('DOWNLOADER_CERT_DIR', '/certs/'))
# the directory inside the aria2 container that contains the private key
DOWNLOADER_KEY_DIR = Path(env.str('DOWNLOADER_KEY_DIR', str(DOWNLOADER_CERT_DIR)))

DOWNLOADER_CERTIFICATE = env.str('DOWNLOADER_CERTIFICATE', None)
DOWNLOADER_CERTIFICATE_PRIVATE_KEY = env.str('DOWNLOADER_CERTIFICATE_PRIVATE_KEY', None)

DOWNLOADER_DEBUG = env.bool('DOWNLOADER_DEBUG', False)

# this is the address for a user to download a file with a downloadtoken. typically something like: download.node.com
DOWNLOAD_ADDRESS = env.str('DOWNLOAD_ADDRESS', None)

# CHALLENGE_HUB_USER_IDENTIFIER = env.str('CHALLENGE_HUB_USER_IDENTIFIER', 'centauron.com#users::hub')
CHALLENGE_HUB_USER_IDENTIFIER = env.str('CHALLENGE_HUB_USER_IDENTIFIER', 'goe.centauron.net#user::ak')
IS_CHALLENGE_HUB = env.bool('IS_HUB', False)
HUB_ENABLE_REGISTRATION = env.bool('HUB_ENABLE_REGISTRATION', False)
HUB_IDENTIFIER = CHALLENGE_HUB_USER_IDENTIFIER  # IDENTIFIER + '#user::hub'

# k8s
COMPUTING_K8S_DATA_DIRECTORY = Path(env.str('C_K8S_DATA_DIRECTORY', '/data/'))
# COMPUTING_K8S_DATA_DIRECTORY.mkdir(parents=True, exist_ok=True)
COMPUTING_K8S_TMP_DIRECTORY = Path(env.str('C_K8S_TMP_DIRECTORY', COMPUTING_K8S_DATA_DIRECTORY / 'tmp'))
# COMPUTING_K8S_TMP_DIRECTORY.mkdir(parents=True, exist_ok=True)
HOST_K8S_DATA_DIRECTORY = Path(env.str('HOST_K8S_DATA_DIRECTORY', '/mnt/centauron/data/'))
# HOST_K8S_DATA_DIRECTORY.mkdir(parents=True, exist_ok=True)
HOST_K8S_TMP_DIRECTORY = Path(env.str('HOST_K8S_TMP_DIRECTORY', '/tmp'))
# HOST_K8S_TMP_DIRECTORY.mkdir(parents=True, exist_ok=True)

COMPUTING_K8S_SIDECAR_IMAGE_TAG = env.str('COMPUTING_K8S_SIDECAR_IMAGE_TAG',
                                          'docker.cytoslider.com/centauron/k8s-helper:latest')
COMPUTING_K8S_SIDECAR_CONTAINER_CMD = env.str('COMPUTING_K8S_SIDECAR_CONTAINER_CMD', 'python main.py').split(' ')
COMPUTING_K8S_CONFIG_FILE = env.str('COMPUTING_K8S_CONFIG_FILE', '/home/django/.kube/config')

COMPUTING_ARTIFACT_DIRECTORY = Path(env.str('C_COMPUTING_ARTIFACT_DIRECTORY', '/artifacts/'))
HOST_COMPUTING_ARTIFACT_DIRECTORY = Path(
    env.str('HOST_COMPUTING_ARTIFACT_DIRECTORY', '/mnt/centauron/computing/artifacts/'))

# this is the docker repository used by the computing cluster
PRIVATE_DOCKER_REPOSITORY = env.str('DOCKER_REPOSITORY', 'docker.cytoslider.com')
PRIVATE_DOCKER_REGISTRY_K8S_SECRET_NAME = env.str('PRIVATE_DOCKER_REGISTRY_K8S_SECRET_NAME', 'docker-credentials')
RETAG_DOCKER_IMAGES = env.bool('RETAG_DOCKER_IMAGES', False)

DOCKER_CONFIG_FILE = env.str('DOCKER_CONFIG_FILE', '/dockerconfig.json')

# misc stuff
DOCKER_IMAGE_TILING = env.str('DOCKER_IMAGE_TILING', 'docker.cytoslider.com/centauron/tiler:latest')

ENABLE_JWT_AUTH = env.bool('ENABLE_JWT_AUTH', True)
JWT_ALGORITHMS = [e.strip() for e in env.str('JWT_ALGORITHMS', 'RS256').split(',') if len(e.strip()) > 0]
JWT_AUDIENCE = env.str('JWT_AUDIENCE', 'account')

if ENABLE_JWT_AUTH:
    # validate jwt
    from cryptography.hazmat.primitives import serialization
    from base64 import b64decode

    KEY_DER = b64decode(KEYCLOAK_PUBLIC_KEY.encode())
    PUBLIC_KEY = serialization.load_der_public_key(KEY_DER)

ANNOTATION_BACKEND_URL = env.str('ANNOTATION_BACKEND_URL', None)
ANNOTATION_BACKEND_USERNAME = env.str('ANNOTATION_BACKEND_USERNAME', 'annotation_backend')
ANNOTATION_BACKEND_APPLICATION_IDENTIFIER = env.str('ANNOTATION_BACKEND_APPLICATION_IDENTIFIER')

# the url of iipsrv that serves the slides
IIPSRV_URL = env.str('IIPSRV_URL', None)

NODE_NAME = env.str('NODE_NAME', IDENTIFIER)
# DSF_PRIVATE_KEY = env.str('DSF_PRIVATE_KEY')
DSF_CERTIFICATE = env.str('DSF_CERTIFICATE', '/run/secrets/app_client_certificate.pem')
DSF_CERTIFICATE_PRIVATE_KEY = env.str('DSF_CERTIFICATE_PRIVATE_KEY',
                                      '/run/secrets/app_client_certificate_private_key.pem')

DECENTRALIZED_BACKEND = env.str('DECENTRALIZED_BACKEND', 'apps.federation.outbox.backends.CentauronAdapter')
BROADCAST_BACKEND = env.str('BROADCAST_BACKEND', 'apps.federation.outbox.backends.FireflyAdapter')

API_ADDRESS = env.str('API_ADDRESS')

available_viewer = ['wsi', 'image']
VIEWER_APP_MAPPING = {'wsi': 'viewer:wsi:viewer', 'png,jpg,jpeg':'viewer:image:viewer'}

VIEWER_MAPPINGS = env.str('CONTENT_TYPE_VIEWER_MAPPING', '')
VIEWER_MAPPINGS = VIEWER_MAPPINGS.split(',')
r = {}
for vm in VIEWER_MAPPINGS:
    content_types, viewer = vm.split(':')
    if viewer not in available_viewer:
        logging.error(f'Viewer {viewer} does not exist. Existing viewers: {available_viewer}')
        sys.exit(2)

    content_type_arr = content_types.split(',')
    for content_type in content_type_arr:
        r[content_type] = viewer
VIEWER_MAPPINGS = r

CCA_URL = env.str('CCA_URL', 'https://ca.centauron.io/')
if not CCA_URL.endswith('/'):
    CCA_URL += '/'

CONSTANCE_BACKEND = 'constance.backends.database.DatabaseBackend'
CONSTANCE_CONFIG = {
    'CCA_TOKEN': ('', 'The token issued by the CCA for authentication.'),
    'CERTIFICATE_THUMBPRINT': ('', 'The thumbprint of the node client certificate.')
}

CCA_LOCAL_USERNAME = 'cca'

# the FQDN of the CDN subdomain of this node. used for transferring files.
CDN_ADDRESS = env.str('CDN_ADDRESS')

KEYCLOAK_ADMIN_CONFIG = Path(env.str('KEYCLOAK_ADMIN_CONFIG', '/run/secrets/keycloak'))
if not KEYCLOAK_ADMIN_CONFIG.exists():
    logging.error('KEYCLOAK_ADMIN_CONFIG not found @ %s', KEYCLOAK_ADMIN_CONFIG)
    sys.exit(1)

# file that contains the keycloak admin password
KEYCLOAK_ADMIN_USERNAME = env.str('KEYCLOAK_ADMIN_USERNAME', 'admin')
KEYCLOAK_ADMIN_PASSWORD = Path(env.str('KEYCLOAK_ADMIN_PASSWORD', '/run/secrets/keycloak_admin_password'))
if not KEYCLOAK_ADMIN_PASSWORD.exists():
    logging.error('KEYCLOAK_ADMIN_PASSWORD not found @ %s', KEYCLOAK_ADMIN_PASSWORD)
    sys.exit(1)


ENABLE_COMPUTING = env.bool('ENABLE_COMPUTING', True)

FIREFLY_WS_URL = env.str('FIREFLY_WS_URL', '')
FIREFLY_API_URL = env.str('FIREFLY_API_URL', '')
FIREFLY_NAMESPACE = env.str('FIREFLY_NAMESPACE', 'default')

FIREFLY_MESSAGE_TOPIC_LOG = env.str('FIREFLY_MESSAGE_TOPIC_LOG', 'log')
FIREFLY_MESSAGE_TOPIC_CONTROL_MESSAGES = env.str('FIREFLY_MESSAGE_TOPIC_CONTROL_MESSAGES', 'centauron')
FIREFLY_MESSAGE_TOPIC_DATA_TRANSFER = env.str('FIREFLY_MESSAGE_TOPIC_DATA_TRANSFER', 'data-transfer')

FIREFLY_SUBSCRIPTION_NAME = env.str('FIREFLY_SUBSCRIPTION_NAME', 'centauron')

FIREFLY_KIND_CONFIG_FILE = env.str('FIREFLY_KIND_CONFIG_FILE', '/home/django/.kube/config')
FIREFLY_SIGNER_POD_NAME = env.str('FIREFLY_SIGNER_POD_NAME', 'firefly-signer-0')
FIREFLY_K8S_NAMESPACE = env.str('FIREFLY_K8S_NAMESPACE', 'default')
FIREFLY_K8S_CONTEXT = env.str('FIREFLY_K8S_CONTEXT', 'kind-firefly')
# the did of the organization this centauron node belongs to in FF
ORGANIZATION_DID = env.str('ORGANIZATION_DID')

# disable for sending submission results back to the client
DATA_UPLOAD_MAX_NUMBER_FIELDS = None
DATA_UPLOAD_MAX_MEMORY_SIZE = env.int('DATA_UPLOAD_MAX_MEMORY_SIZE', 1024*1024*50)

FORCE_SCRIPT_NAME = env.str('FORCE_SCRIPT_NAME', None)

BLOCKCHAIN_POLLING_FREQUENCY = env.int('BLOCKCHAIN_POLLING_FREQUENCY', 2)
BLOCKCHAIN_RPC_URL = env.str('BLOCKCHAIN_RPC_URL', 'http://besu-control-plane:30545/')
IPFS_URL = env.str('IPFS_URL', 'http://127.0.0.1:5001')

if IPFS_URL[-1] != '/':
    IPFS_URL += '/'

# ipfs timeout in seconds
IPFS_TIMEOUT = env.int('IPFS_TIMEOUT', 30)

PRIVATE_KEY_FOLDER = Path(env.str('PRIVATE_KEY_FOLDER', '/keystore'))

