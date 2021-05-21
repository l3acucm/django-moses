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

4. Run ``python manage.py migrate`` to create the accounts models.
