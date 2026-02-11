from datetime import datetime, timedelta, timezone

import jwt
from django.conf import settings as django_settings
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token

from moses.common import error_codes
from moses.common.exceptions import CustomAPIException, KwargsError
from moses.conf import settings as moses_settings


def verify_google_id_token(token: str) -> dict:
    """
    Verify a Google ID token and return the decoded claims.
    Returns dict with keys: sub, email, email_verified, given_name, family_name, picture.
    """
    client_id = moses_settings.GOOGLE_OAUTH2_CLIENT_ID
    if not client_id:
        raise CustomAPIException({
            '': [KwargsError(code=error_codes.GOOGLE_SIGN_IN_NOT_CONFIGURED)]
        })

    try:
        id_info = google_id_token.verify_oauth2_token(
            token,
            google_requests.Request(),
            client_id
        )
        return id_info
    except ValueError:
        raise CustomAPIException({
            'id_token': [KwargsError(code=error_codes.INVALID_GOOGLE_ID_TOKEN)]
        })


def create_google_auth_temp_token(google_claims: dict) -> str:
    """
    Create a short-lived signed JWT containing Google user info.
    Used when a new user needs to complete registration (provide phone number).
    """
    expiry_minutes = moses_settings.GOOGLE_AUTH_TEMP_TOKEN_EXPIRY_MINUTES
    payload = {
        'google_sub': google_claims['sub'],
        'email': google_claims.get('email', ''),
        'first_name': google_claims.get('given_name', ''),
        'last_name': google_claims.get('family_name', ''),
        'token_type': 'google_auth_temp',
        'exp': datetime.now(timezone.utc) + timedelta(minutes=expiry_minutes),
        'iat': datetime.now(timezone.utc),
    }
    return jwt.encode(payload, django_settings.SECRET_KEY, algorithm='HS256')


def decode_google_auth_temp_token(token: str) -> dict:
    """
    Decode and validate the temporary Google auth token.
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
            'google_auth_token': [
                KwargsError(code=error_codes.GOOGLE_AUTH_TEMP_TOKEN_EXPIRED)
            ]
        })
    except jwt.InvalidTokenError:
        raise CustomAPIException({
            'google_auth_token': [
                KwargsError(code=error_codes.INVALID_GOOGLE_AUTH_TEMP_TOKEN)
            ]
        })

    if payload.get('token_type') != 'google_auth_temp':
        raise CustomAPIException({
            'google_auth_token': [
                KwargsError(code=error_codes.INVALID_GOOGLE_AUTH_TEMP_TOKEN)
            ]
        })

    return payload
