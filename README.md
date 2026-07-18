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
        'social_django',
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
        'social_core.backends.google.GoogleOAuth2',
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
    from moses import urls as moses_urls

    admin.site.site_header = _('Admin Panel')
    admin.site.index_title = 'Welcome'
    admin.site.login_form = OTPAdminAuthenticationForm
    urlpatterns = [
        ...
        path('moses/', include(moses_urls, namespace='moses')),
    ]
```
8. Run ``python manage.py migrate`` to create the accounts models.

9. Add middleware:
```
MIDDLEWARE = [
    ...
    'social_django.middleware.SocialAuthExceptionMiddleware',
]
```
10. Add context processors:
```
TEMPLATES[0]['OPTIONS']['context_processors'] += [
    'social_django.context_processors.backends',
    'social_django.context_processors.login_redirect',
]
```

Google Sign-In
--------------

Moses supports authentication via Google OAuth2. To enable it:

1. Create a Google OAuth2 Client ID in the [Google Cloud Console](https://console.cloud.google.com/apis/credentials).

2. Add the client ID to your `MOSES` settings:
```python
    MOSES = {
        ...
        "GOOGLE_OAUTH2_CLIENT_ID": "your-google-client-id.apps.googleusercontent.com",
    }
```

3. The following endpoints will be available:

- **POST** `/moses/token/google/` — Step 1: Send the Google `id_token` and `domain`. If the user exists, returns JWT tokens. If the user is new, returns a temporary `google_auth_token` for completing registration.

  Request body:
  ```json
  {"id_token": "<google-id-token>", "domain": "example.com"}
  ```

- **POST** `/moses/token/google/complete/` — Step 2 (new users only): Send the `google_auth_token`, `phone_number`, and `domain` to create the account and receive JWT tokens.

  Request body:
  ```json
  {"google_auth_token": "<temp-token>", "phone_number": "+1234567890", "domain": "example.com"}
  ```

Telegram Sign-In
----------------

Moses supports authentication via the [Telegram Login Widget](https://core.telegram.org/widgets/login) — the method officially recommended by Telegram.

### Setup

1. Create a Telegram bot via [@BotFather](https://t.me/BotFather).

2. In BotFather, go to **Bot Settings → Domain → Add your website domain** to allow login from your site.

3. Add the bot token to your `MOSES` settings:
```python
    MOSES = {
        ...
        "TELEGRAM_BOT_TOKEN": "123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ",
    }
```

4. Optional settings:
```python
    MOSES = {
        ...
        "TELEGRAM_AUTH_TEMP_TOKEN_EXPIRY_MINUTES": 5,   # temp token lifetime for new user registration (default: 5)
        "TELEGRAM_AUTH_DATA_MAX_AGE_SECONDS": 300,        # max age of Telegram auth data to prevent replay attacks (default: 300 = 5min)
    }
```

5. Add the [Telegram Login Widget](https://core.telegram.org/widgets/login) to your frontend. The widget will return auth data containing: `id`, `first_name`, `last_name`, `username`, `photo_url`, `auth_date`, and `hash`.

### API Endpoints

- **POST** `/moses/token/telegram/` — Step 1: Send the Telegram auth data and `domain`. If the user exists (by `telegram_id`), returns JWT tokens. If the user is new, returns a temporary `telegram_auth_token` for completing registration.

  Request body:
  ```json
  {
    "auth_data": {
      "id": 123456789,
      "first_name": "John",
      "last_name": "Doe",
      "username": "johndoe",
      "photo_url": "https://t.me/i/userpic/...",
      "auth_date": 1234567890,
      "hash": "abc123..."
    },
    "domain": "example.com"
  }
  ```

  Response (existing user):
  ```json
  {"status": "authenticated", "refresh": "<jwt>", "access": "<jwt>"}
  ```

  Response (new user):
  ```json
  {
    "status": "phone_required",
    "telegram_auth_token": "<temp-token>",
    "first_name": "John",
    "last_name": "Doe",
    "username": "johndoe"
  }
  ```

- **POST** `/moses/token/telegram/complete/` — Step 2 (new users only): Send the `telegram_auth_token`, `phone_number`, optional `email`, and `domain` to create the account and receive JWT tokens.

  Request body:
  ```json
  {
    "telegram_auth_token": "<temp-token>",
    "phone_number": "+1234567890",
    "email": "john@example.com",
    "domain": "example.com"
  }
  ```

  Response:
  ```json
  {"status": "authenticated", "refresh": "<jwt>", "access": "<jwt>"}
  ```

### How Verification Works

Moses verifies Telegram auth data using the algorithm specified by Telegram:
1. A SHA-256 hash of the bot token is used as the HMAC secret key.
2. All auth data fields (except `hash`) are sorted alphabetically and joined as `key=value\n`.
3. An HMAC-SHA-256 signature is computed and compared against the received `hash`.
4. The `auth_date` is checked to prevent replay attacks.

Message templates (SMS / email)
--------------------------------

All outgoing SMS and email texts are configurable through the `MESSAGE_TEMPLATES`
setting — the same way the SMS transport is provided via `SEND_SMS_HANDLER`. You
override **any subset** of the keys; the rest fall back to the built-in defaults.

```python
from django.utils.translation import gettext_lazy as _

MOSES = {
    ...
    "MESSAGE_TEMPLATES": {
        # business requirement: SMS must contain only the code
        "PHONE_NUMBER_CONFIRMATION_PIN_BODY": "{pin}",
        "PASSWORD_RESET_SMS_BODY": "{pin}",
        # a localizable email body (needs your own .po/.mo — see i18n below)
        "EMAIL_CONFIRMATION_PIN_BODY": _("Hi {user.first_name}! Your code is {pin}"),
    },
}
```

### Available keys

| Key | Channel | Placeholders |
|-----|---------|--------------|
| `EMAIL_CONFIRMATION_PIN_TITLE` | email subject | `{pin}` |
| `EMAIL_CONFIRMATION_PIN_BODY` | email body | `{pin}` |
| `PHONE_NUMBER_CONFIRMATION_PIN_BODY` | **SMS** | `{pin}` |
| `PASSWORD_RESET_PIN_TITLE` | email subject | `{pin}` |
| `PASSWORD_RESET_EMAIL_BODY` | email body | `{pin}` |
| `PASSWORD_RESET_SMS_BODY` | **SMS** | `{pin}` |
| `PASSWORD_CHANGED_TITLE` / `PASSWORD_CHANGED_BODY` | email | `{domain}` |
| `EMAIL_CHANGED_TITLE` / `EMAIL_CHANGED_BODY` | email | `{domain}` |
| `PHONE_NUMBER_CHANGED_TITLE` / `PHONE_NUMBER_CHANGED_BODY` | email | `{domain}` |

Password reset uses **separate** SMS and email bodies, so you can strip the SMS to
a bare code while keeping the full email text.

### Placeholders

Templates are rendered with `str.format`. Always available: `{pin}`, `{user}` (and
its attributes, e.g. `{user.first_name}`, `{user.email}`), and `{domain}`. Escape
literal braces as `{{` / `}}`; referencing an undefined placeholder raises
`KeyError` (surfacing the misconfiguration).

### Internationalization

Each template is resolved to the user's `preferred_language` before formatting.

- A **plain string** (e.g. `"{pin}"`) is not translated — the same in every
  language. This is exactly what you want for an SMS that is only a code.
- To translate a template, wrap it in `gettext_lazy` and ship your own `.po/.mo`
  catalogs (set `LOCALE_PATHS`, run `makemessages` + `compilemessages`). Moses does
  not ship translation catalogs itself, so the built-in defaults render as their
  English source text until you provide your own.

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
