import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
SECRET_KEY = "fake-key"

DEBUG = True

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'moses_test',
        'USER': 'postgres',
        'PASSWORD': 'abcxyz123',
        'HOST': 'localhost',
        'PORT': 5432
    }
}

EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
MACOS = bool(int(os.environ.get('MACOS', 0)))
AUTH_USER_MODEL = 'moses.CustomUser'
DEFAULT_AUTO_FIELD = "django.db.models.AutoField"
ROOT_URLCONF = "test_project.urls"
AUTHENTICATION_BACKENDS = ("moses.authentication.MFAModelBackend",)
DOMAIN = 'lvh.me'
INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.sites",
    'django.contrib.staticfiles',

    "rest_framework",
    "moses"
]

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [''],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]
MOSES = {
    "DEFAULT_LANGUAGE": 'en',
    'MAX_PHONE_NUMBER_CONFIRMATION_ATTEMPTS': 10,
    'MINUTES_BETWEEN_CONFIRMATION_PIN_SMS': 0,
    "SEND_SMS_HANDLER": "test_project.app_for_tests.mocks.send_sms_handler",
    "PHONE_NUMBER_VALIDATOR": "test_project.app_for_tests.mocks.validate_phone_number",
    "DOMAIN": "abc.xyz",
    "URL_PREFIX": "https://abc.xyz",
    "IP_HEADER": "HTTP_CF_CONNECTING_IP" if DEBUG else None,
    "LANGUAGE_CHOICES": (
        ('en', "English"),
    ),
}

DJOSER = {
    'DOMAIN': "abc.xyz",
    'SITE_NAME': 'SunPay',
    'PASSWORD_RESET_CONFIRM_URL': 'auth/resetPassword?uid={uid}&token={token}',
    'ACTIVATION_URL': '?action=activation&uid={uid}&token={token}',
    'SEND_ACTIVATION_EMAIL': False,
    'SERIALIZERS': {
        'user_create': 'moses.serializers.CustomUserCreateSerializer',
        'current_user': 'moses.serializers.PrivateCustomUserSerializer',
        'token_obtain': 'moses.serializers.TokenObtainSerializer'
    }
}
FIXTURE_DIRS = [
    'test_project/app_for_tests/fixtures'
]
if MACOS:
    GDAL_LIBRARY_PATH = '/opt/homebrew/opt/gdal/lib/libgdal.dylib'
    GEOS_LIBRARY_PATH = '/opt/homebrew/opt/geos/lib/libgeos_c.dylib'
