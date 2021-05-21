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

    DJOSER = {
        'DOMAIN': DOMAIN,
        'SITE_NAME': 'Fooder',
        'PASSWORD_RESET_CONFIRM_URL': 'auth/resetPassword?uid={uid}&token={token}',
        'ACTIVATION_URL': '?action=activation&uid={uid}&token={token}',
        'SEND_ACTIVATION_EMAIL': False,
        'SERIALIZERS': {
            'user_create': 'moses.serializers.CustomUserCreateSerializer',
            'current_user': 'moses.serializers.PrivateCustomUserSerializer',
            'token_obtain': 'moses.serializers.TokenObtainSerializer'
        }
    }

5. Run ``python manage.py migrate`` to create the accounts models.
