import hashlib
import hmac
import time
from datetime import datetime, timedelta, timezone

import jwt
from django.conf import settings as django_settings

from moses.common import error_codes
from moses.common.exceptions import CustomAPIException, KwargsError
from moses.conf import settings as moses_settings


def verify_telegram_auth_data(auth_data: dict) -> dict:
    """
    Verify Telegram Login Widget authentication data using HMAC-SHA-256.

    Telegram's verification algorithm:
    1. Create a SHA-256 hash of the bot token (this is the secret key).
    2. Build a data-check-string by sorting all fields (except 'hash')
       alphabetically and joining them as 'key=value' with newlines.
    3. Compute HMAC-SHA-256 of the data-check-string using the secret key.
    4. Compare the computed hash with the received 'hash' field.

    Also validates that auth_date is not too old (replay attack prevention).

    Returns the verified auth_data dict.
    """
    bot_token = moses_settings.TELEGRAM_BOT_TOKEN
    if not bot_token:
        raise CustomAPIException({
            '': [KwargsError(code=error_codes.TELEGRAM_SIGN_IN_NOT_CONFIGURED)]
        })

    # Validate required fields
    for required_field in ('id', 'auth_date', 'hash'):
        if required_field not in auth_data or auth_data[required_field] in (None, ''):
            raise CustomAPIException({
                'auth_data': [KwargsError(code=error_codes.INVALID_TELEGRAM_AUTH_DATA)]
            })

    received_hash = str(auth_data['hash'])

    # Build data-check-string: sort fields alphabetically, join with \n
    # All values are explicitly cast to str to match Telegram's signed representation
    data_fields = {k: str(v) for k, v in auth_data.items() if k != 'hash'}
    data_check_string = '\n'.join(
        f'{key}={data_fields[key]}' for key in sorted(data_fields.keys())
    )

    # Secret key = SHA-256 of bot token
    secret_key = hashlib.sha256(bot_token.encode('utf-8')).digest()

    # Compute HMAC-SHA-256
    computed_hash = hmac.new(
        secret_key,
        data_check_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(computed_hash, received_hash):
        raise CustomAPIException({
            'auth_data': [KwargsError(code=error_codes.INVALID_TELEGRAM_AUTH_DATA)]
        })

    # Check auth_date freshness (replay attack prevention)
    max_age = moses_settings.TELEGRAM_AUTH_DATA_MAX_AGE_SECONDS
    auth_date = int(auth_data.get('auth_date', 0))
    if (time.time() - auth_date) > max_age:
        raise CustomAPIException({
            'auth_data': [KwargsError(code=error_codes.TELEGRAM_AUTH_DATA_EXPIRED)]
        })

    return auth_data


def create_telegram_auth_temp_token(telegram_data: dict) -> str:
    """
    Create a short-lived signed JWT containing Telegram user info.
    Used when a new user needs to complete registration (provide phone number).
    """
    expiry_minutes = moses_settings.TELEGRAM_AUTH_TEMP_TOKEN_EXPIRY_MINUTES
    payload = {
        'telegram_id': str(telegram_data['id']),
        'first_name': telegram_data.get('first_name', ''),
        'last_name': telegram_data.get('last_name', ''),
        'username': telegram_data.get('username', ''),
        'token_type': 'telegram_auth_temp',
        'exp': datetime.now(timezone.utc) + timedelta(minutes=expiry_minutes),
        'iat': datetime.now(timezone.utc),
    }
    return jwt.encode(payload, django_settings.SECRET_KEY, algorithm='HS256')


def decode_telegram_auth_temp_token(token: str) -> dict:
    """
    Decode and validate the temporary Telegram auth token.
    Returns the payload dict.
    """
    try:
        payload = jwt.decode(
            token,
            django_settings.SECRET_KEY,
            algorithms=['HS256']
        )
    except jwt.ExpiredSignatureError:
        raise CustomAPIException({
            'telegram_auth_token': [
                KwargsError(code=error_codes.TELEGRAM_AUTH_TEMP_TOKEN_EXPIRED)
            ]
        })
    except jwt.InvalidTokenError:
        raise CustomAPIException({
            'telegram_auth_token': [
                KwargsError(code=error_codes.INVALID_TELEGRAM_AUTH_TEMP_TOKEN)
            ]
        })

    if payload.get('token_type') != 'telegram_auth_temp':
        raise CustomAPIException({
            'telegram_auth_token': [
                KwargsError(code=error_codes.INVALID_TELEGRAM_AUTH_TEMP_TOKEN)
            ]
        })

    return payload
