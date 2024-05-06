Moses
=====

Moses is the Django app that provides OTP authentication and phone number email verification by 6-digit verification codes.

Quick start
-----------

1. Add "moses" to your INSTALLED_APPS setting like this::
```
    INSTALLED_APPS = [
        ...
        'moses',
        'django.contrib.admin',
        ...
    ]
```
2. Set moses's CustomUser model as AUTH_USER_MODEL::
```
    AUTH_USER_MODEL = 'moses.CustomUser'
```
3. Allow OTP header in django-cors-headers config::
```
    CORS_ALLOW_HEADERS = (
        *default_headers,
        "otp",
   )
```
4. Add MFAModelBackend as Authentication backend to process OTP on authentication::
```
    AUTHENTICATION_BACKENDS = [
        'moses.authentication.MFAModelBackend',
        ...
    ]
```
5. Add JWTAuthentication to REST_FRAMEWORK's DEFAULT_AUTHENTICATION_CLASSES::
```
    REST_FRAMEWORK = {
        ...
        'DEFAULT_AUTHENTICATION_CLASSES': [
            'moses.authentication.JWTAuthentication',
        ]
    }
```
6. Specify Moses's serializers for Djoser::
```
    MOSES = {
        "DEFAULT_LANGUAGE": 'en',
        "SEND_SMS_HANDLER": "project.common.sms.send",
        "SENDER_EMAIL": "noreply@example.com",
        "PHONE_NUMBER_VALIDATOR": "project.common.sms.validate_phone_number",
        "DOMAIN": DOMAIN,
        "URL_PREFIX": "http://localhost:8000", # without trailing slash
        "IP_HEADER": "HTTP_CF_CONNECTING_IP" if DEBUG else None,
        "LANGUAGE_CHOICES": (
            ('en', _("English")),
        ),
    }
```
7. Add to your root urls.py::
```
    from moses.admin import OTPAdminAuthenticationForm

    admin.site.site_header = _('Admin Panel')
    admin.site.index_title = 'Welcome'
    admin.site.login_form = OTPAdminAuthenticationForm
```
8. Run ``python manage.py migrate`` to create the accounts models.
