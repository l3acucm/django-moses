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

2. Set Moses's CustomUser model as AUTH_USER_MODEL::

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
    "DEFAULT_LANGUAGE": 1,
    "SEND_SMS_HANDLER": "polls.sms.send", # def send(phone_number, body) -> success: bool
    "PHONE_NUMBER_VALIDATOR": "polls.validate_phone_number", #  # def validate_phone_number(phone_number) -> is_valid: bool
    "DOMAIN": DOMAIN,
    "LANGUAGE_CHOICES": (
            ('en', _("English")),
            ('ru', _("Russian")),
            ('kg', _("Kyrgyz")),
        ),
    }

6. Run ``python manage.py migrate`` to create the accounts models.
