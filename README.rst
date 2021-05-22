=====
Polls
=====

Polls is a Django app to conduct Web-based polls. For each question,
visitors can choose between a fixed number of answers.

Detailed documentation is in the "docs" directory.

Quick start
-----------

1. Add "polls" to your INSTALLED_APPS setting like this::

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
