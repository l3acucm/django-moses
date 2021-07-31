SECRET_KEY = "fake-key"

DEBUG = True

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": "sinbad",
    }
}
AUTH_USER_MODEL = 'moses.CustomUser'
DEFAULT_AUTO_FIELD = "django.db.models.AutoField"
ROOT_URLCONF = "test_project.urls"
AUTHENTICATION_BACKENDS = ("django.contrib.auth.backends.ModelBackend", "guardian.backends.ObjectPermissionBackend")
INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.sites",
    "django.contrib.staticfiles",
    "moses"
]

MOSES = {
    "DEFAULT_LANGUAGE": 'en',
    "SEND_SMS_HANDLER": "tests.mocks.send_sms_handler",
    "PHONE_NUMBER_VALIDATOR": "tests.mocks.validate_phone_number",
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
