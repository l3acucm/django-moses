=====
Moses
=====

Moses is the Django app that provides OTP authentication and phone number email verification by 6-digit verification codes.

Quick start
-----------

1. Add "moses" to your INSTALLED_APPS setting like this::

    INSTALLED_APPS = [
        ...
        'moses',
    ]

2. Set moses's CustomUser model as AUTH_USER_MODEL::

    AUTH_USER_MODEL = 'moses.CustomUser'
    
3. Add MFAModelBackend as Authentication backend to process OTP on authentication::

    AUTHENTICATION_BACKENDS = [
        'moses.authentication.MFAModelBackend',
        ...
    ]

4. Add JWTAuthentication to REST_FRAMEWORK's DEFAULT_AUTHENTICATION_CLASSES::

    REST_FRAMEWORK = {
        ...
        'DEFAULT_AUTHENTICATION_CLASSES': [
            'moses.authentication.JWTAuthentication',
        ]
    }

5. Specify Moses's serializers for Djoser::


MOSES = {
    "DEFAULT_LANGUAGE": 'en',
    "SEND_SMS_HANDLER": "project.common.sms.send",
    "PHONE_NUMBER_VALIDATOR": "project.common.sms.validate_phone_number",
    "DOMAIN": DOMAIN,
    "LANGUAGE_CHOICES": (
        ('en', _("English")),
    ),
}

6. Run ``python manage.py migrate`` to create the accounts models.
