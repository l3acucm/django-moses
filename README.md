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

## Phone OTP login

Opt-in passwordless login by SMS code, enabled via `LOGIN_METHODS` (default `['WITH_PASSWORD']`; `PHONE_OTP_LOGIN` was removed and raises `ImproperlyConfigured` if still present). Values: `WITH_PASSWORD` (token/obtain, user create, set/reset password) and `WITHOUT_PASSWORD` (otp_request, otp_verify); a disabled method's endpoints answer 404. Use `['WITH_PASSWORD', 'WITHOUT_PASSWORD']` for both; empty, unknown or non-list values raise `ImproperlyConfigured`.

> **Warning:** set `PHONE_OTP_CODES_PER_PHONE_LIMIT` (and `PHONE_OTP_REQUEST_IP_LIMIT`) before enabling `WITHOUT_PASSWORD`. Both default to `None`; without a per-number cap every new code resets the attempts counter, which allows roughly 8.6k guesses per day per number.

Run `migrate` after upgrading to 0.18.0 or later (migration `0007_email_unique_unless_blank`: `(site, email)` is unique only when the email is non-blank).

```python
MOSES = {
    ...
    'LOGIN_METHODS': ['WITHOUT_PASSWORD'],
    'PHONE_OTP_REQUEST_IP_LIMIT': (20, 3600),  # optional: (count, seconds) per client IP, default None
    'PHONE_OTP_CODES_PER_PHONE_LIMIT': (3, 86400),  # optional: unused codes per (site, phone), default None
    'PHONE_OTP_CODE_TTL_SECONDS': 900,  # optional: login code lifetime, default None (valid until used)
}
```

**POST `/moses/users/otp_request/`** `{"phone_number": "+996...", "domain": "example.com"}` -> `{}`.
Creates the user (unusable password) if the number is new and sends a code; an inactive user gets the same `{}` but no
code. A blank, too long (over 20 chars) or validator-rejected number gives 400 `invalid_phone_number`; an unknown domain
gives 400 `site_with_domain_does_not_exist`. `too_frequent_sms_requests` is 400 for the per-phone resend pause
(`PHONE_NUMBER_CONFIRMATION_SMS_SECONDS_PERIOD`) and 429 over `PHONE_OTP_REQUEST_IP_LIMIT`. Over
`PHONE_OTP_CODES_PER_PHONE_LIMIT` the answer is 429 `phone_otp_codes_limit_reached`; only codes actually sent count,
and a successful `otp_verify` takes its code off the count. Password-reset codes sent to the phone share that count
(`reset_password` answers the same 429; a successful `reset_password_confirm` takes its code off). The per-IP limit also
covers user create, Google/Telegram sign-up completion, `reset_password`, `request_phone_number_confirmation_pin` and a
profile update that sets a new phone number (one shared counter).

**POST `/moses/users/otp_verify/`** `{"phone_number": "+996...", "code": "123456", "domain": "example.com"}` -> `{"access": "...", "refresh": "...", "created": true}`.
`created` is true exactly when this verify did the user's initial phone confirmation (the same moment
`phone_number_confirmed` fires with `is_initial_confirmation=True`), so a client can show a one-time onboarding prompt
for brand-new accounts; false for every later login. A failed TOTP doesn't confirm, so the next success still says true.
A wrong or unknown code gives 400 `{"code": [incorrect_confirmation_pin]}`; too many attempts give `attempts_limit_reached`.
A superuser or a user with an MFA key must also send `"otp"` (their TOTP); a missing or wrong one gives 400
`{"otp": [invalid_otp]}`, costs an attempt and keeps the SMS code valid. A superuser without an MFA key can't log in
this way. There is no DEBUG master code. Exception: while the number is not confirmed yet, a non-staff user needs no
TOTP, and that first successful verify drops the password, `google_sub`, `telegram_id` and MFA key (whoever attached
them never proved the number). With `PHONE_OTP_CODE_TTL_SECONDS` a code older than that (counted from
`phone_number_confirmation_pin_created_at`; `otp_login.login_code_expired(user)`) answers like a wrong code without
costing an attempt, and `request_phone_number_confirmation_pin` sends a new code instead of re-sending an expired
one. Tokens are minted from the saved user, so with simplejwt's `CHECK_REVOKE_TOKEN` the first-proof verify ends the
squatter's sessions and the new tokens stay valid. Failed verifies are counted per client IP with the `PHONE_OTP_REQUEST_IP_LIMIT` numbers; over it
the IP gets 429 `too_frequent_sms_requests` before the user is looked up. `phone_number_confirmed` receivers run inside the verify transaction, under a
row lock on the user: keep them quick, and an exception in one fails the login.

Without `WITH_PASSWORD`, these return 404: user create (`POST /moses/users/`), `set_password`, `reset_password`,
`reset_password_confirm` and the password token endpoint (`token_obtain_pair`). Self-deletion works under every
configuration (see Deletion).

Both limits count in Django's cache, so it must be shared and atomic (Redis or Memcached); LocMem is per process.

The per-IP limit uses `IP_HEADER`: it must be a header your reverse proxy overwrites (not one the client can set),
otherwise the limit can be bypassed by spoofing it. If `IP_HEADER` is set but missing on a request, `REMOTE_ADDR` is used.

## Deletion

Through the API and `CustomUserAdmin` moses never deletes a user row (`user.delete()`, ORM/shell code and deleting a `Site` still hard-delete). `DELETE /moses/users/me/`, `DELETE /moses/users/{id}/`, the Django admin «Delete»
button and the admin «Delete selected» action all call `moses.services.anonymize.anonymize_user(user)`, so games,
payments and anything else pointing at the user stay intact.

`anonymize_user` sets `first_name` and `last_name` to `DELETED`, replaces `phone_number` with a random
`deleted-xxxxxxxxxxxx` placeholder (unique per site, not a valid phone; collisions are retried), clears `email`,
`email_candidate`, `phone_number_candidate`, `google_sub`, `telegram_id` and `mfa_secret_key`, sets an unusable password,
`is_active = False`, `is_staff = False`, `is_phone_number_confirmed = False`, `is_email_confirmed = False`, clears groups and user permissions, zeroes the confirmation pins and the password reset code, then
sends `user_anonymized` — all in one transaction. The old phone number is free again: `otp_request` with it creates a
new user. Anonymizing an already anonymized user works (a new placeholder, the signal fires again).

Self-deletion needs `current_password` only if the user has a usable password (code-login users have none); a wrong
one gives 400. Superusers can't be anonymized: the API answers 403 `{"": [superuser_cannot_be_deleted]}`, the admin
refuses the delete page (403) and refuses the whole bulk action if any selected user is a superuser. The admin
confirmation page lists only the users themselves (nothing cascades).

**user_anonymized** (`sender`: the User model class, `user`: the anonymized user) runs inside the anonymization
transaction; an exception in a receiver rolls it back, so put external side effects (S3 deletes, pushes) in
`transaction.on_commit`. Hook it to wipe your own personal data:

```python
from django.dispatch import receiver
from moses.models import CustomUser
from moses.signals import user_anonymized

@receiver(user_anonymized, sender=CustomUser)
def wipe_profile(sender, user, **kwargs):
    user.profile.avatar = None
    user.profile.save()
```

## Changelog

### 0.19.1

Security fixes. Run `migrate` (migration `0008`: `password_reset_code_attempts` with a database default of 0, and
`phone_number_confirmation_pin_created_at`; both are safe while old processes still run).

- Password-reset code: `PHONE_NUMBER_CONFIRMATION_ATTEMPTS_LIMIT` wrong guesses burn it (then `attempts_limit_reached`
  until a new code is sent), the right code works once. A new reset code restores the attempts, so the real limit on
  guessing is how many codes can be sent: phone reset codes now count in `PHONE_OTP_CODES_PER_PHONE_LIMIT` together with
  login codes (only unused ones; a successful reset takes its code off), and the email branch now has the same
  `PASSWORD_RESET_TIMEOUT_SECONDS` pause as the phone branch (they share `password_reset_code_sms_unlocks_at`). Set
  `PHONE_OTP_CODES_PER_PHONE_LIMIT` if you keep `WITH_PASSWORD`: without it, reset codes are limited only by the pause.
- `otp_verify` on a not yet confirmed number (non-staff): no TOTP asked; the password, `google_sub`, `telegram_id` and
  MFA key set before the number was proven are cleared. Superusers, staff and confirmed users are unchanged. To also end
  the squatter's existing JWTs, set simplejwt `SIMPLE_JWT['CHECK_REVOKE_TOKEN'] = True` (then any password change ends
  that user's other sessions).
- `PHONE_OTP_REQUEST_IP_LIMIT` now also applies to user create, `reset_password`, `request_phone_number_confirmation_pin`
  Google/Telegram sign-up completion and a profile update with a new phone number, and (as a separate count of
  failures) to `otp_verify`.
- `PHONE_OTP_CODES_PER_PHONE_LIMIT` counts only unused codes: a successful login takes its code off the count.
- New `PHONE_OTP_CODE_TTL_SECONDS` (default `None`): login codes older than that are refused. Projects that set
  `phone_number_confirmation_pin` themselves must also set `phone_number_confirmation_pin_created_at`, or the code
  counts as expired. Re-sending the confirmation pin replaces an expired code.
- A candidate pin of 0 never matches (the main pin already had this guard).
- Confirming a number change onto a number held by a never-confirmed, non-staff user anonymizes that holder
  (`user_anonymized` fires) instead of a 500. `PATCH me` by an unconfirmed user onto a taken number gives 400
  `phone_number_already_registered_on_domain` instead of a 500.

### 0.19.0

**Admin login by code.** With `WITHOUT_PASSWORD` the admin login page gets a «Отправить код» button and a code field.
Staff only: it never registers anyone, and answers the same whoever the number belongs to. Superusers still need their
TOTP. Sending a code shares the per-IP limit (`PHONE_OTP_REQUEST_IP_LIMIT`) with `otp_request`.

- `LOGIN_METHODS` (`['WITH_PASSWORD']` by default, `'WITHOUT_PASSWORD'` for SMS-code login) replaces `PHONE_OTP_LOGIN`,
  which is removed, not aliased: replace `'PHONE_OTP_LOGIN': True` with `'LOGIN_METHODS': ['WITHOUT_PASSWORD']` (or both
  values). A leftover `PHONE_OTP_LOGIN` key raises `ImproperlyConfigured`.
- Django admin login by SMS code (`OTPAdminAuthenticationForm`) when `WITHOUT_PASSWORD` is on.
- **BREAKING:** deletion anonymizes instead of deleting (see Deletion), in the API and in `CustomUserAdmin`. Rows that
  used to be CASCADE-deleted with the user are now kept: projects must wipe their personal data in a `user_anonymized`
  receiver (runs inside the transaction; external side effects belong in `transaction.on_commit`). Only the API and
  `CustomUserAdmin` anonymize; `user.delete()`, ORM/shell code and deleting a `Site` still hard-delete. Self-deletion is
  available again with `WITHOUT_PASSWORD` (0.18.1 answered 404) and needs no password for passwordless users.
- Upgrading from 0.18: no new migrations. If you subclassed `CustomUserAdmin` to anonymize, drop that override; move
  project-specific cleanup into a `user_anonymized` receiver. Code that relied on `pre_delete`/`post_delete` of the user
  for account deletion must move to `user_anonymized`.
