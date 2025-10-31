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

Signals
-------

Moses emits Django signals during credential confirmation workflows. You can listen to these signals in your application to perform custom actions.

### Available Signals

**phone_number_confirmed**

Emitted when a user successfully confirms their phone number.

Parameters:
- `sender`: The User model class
- `user`: The user instance whose phone was confirmed
- `phone_number`: The confirmed phone number (str)
- `is_initial_confirmation`: True if this is the first confirmation, False if updating phone number

Example usage:
```python
from django.dispatch import receiver
from moses.signals import phone_number_confirmed
from moses.models import CustomUser

@receiver(phone_number_confirmed, sender=CustomUser)
def handle_phone_confirmed(sender, user, phone_number, is_initial_confirmation, **kwargs):
    if is_initial_confirmation:
        print(f"User {user.id} confirmed their phone: {phone_number}")
    else:
        print(f"User {user.id} changed their phone to: {phone_number}")
```

**email_confirmed**

Emitted when a user successfully confirms their email address.

Parameters:
- `sender`: The User model class
- `user`: The user instance whose email was confirmed
- `email`: The confirmed email address (str)
- `is_initial_confirmation`: True if this is the first confirmation, False if updating email

Example usage:
```python
from django.dispatch import receiver
from moses.signals import email_confirmed
from moses.models import CustomUser

@receiver(email_confirmed, sender=CustomUser)
def handle_email_confirmed(sender, user, email, is_initial_confirmation, **kwargs):
    if is_initial_confirmation:
        print(f"User {user.id} confirmed their email: {email}")
    else:
        print(f"User {user.id} changed their email to: {email}")
```
