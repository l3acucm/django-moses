import pyotp
from django.core.cache import cache
from django.contrib.sites.models import Site
from django.db import transaction
from rest_framework import status

from moses.common import error_codes
from moses.common.exceptions import CustomAPIException, KwargsError
from moses.conf import settings as moses_settings
from moses.enums import Credential
from moses.models import CustomUser
from moses.services.credentials_confirmation import send_credential_confirmation_code
from moses.signals import phone_number_confirmed


def client_ip(request):
    meta = request.META
    header = moses_settings.IP_HEADER
    return (meta.get(header) if header else None) or meta.get('REMOTE_ADDR')


def count_hit(key: str, window: int) -> int:
    """Fixed-window counter: add() sets the timeout only when the key is new."""
    cache.add(key, 0, timeout=window)
    return cache.incr(key)


def check_request_ip_limit(request) -> None:
    limit = moses_settings.PHONE_OTP_REQUEST_IP_LIMIT
    if limit is None:
        return
    max_requests, window = limit
    if count_hit(f'moses:otp_ip:{client_ip(request)}', window) > max_requests:
        raise CustomAPIException(
            {'': [KwargsError(code=error_codes.TOO_FREQUENT_SMS_REQUESTS)]},
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        )


def send_login_code(user: CustomUser) -> None:
    """Sends a code, refusing once PHONE_OTP_CODES_PER_PHONE_LIMIT codes went out in the window.

    Only sent codes are counted; a request refused by the resend pause raises
    before the hit.
    """
    limit = moses_settings.PHONE_OTP_CODES_PER_PHONE_LIMIT
    key = f'moses:otp_phone:{user.site.domain}:{user.phone_number}'
    if limit is not None and cache.get(key, 0) >= limit[0]:
        raise CustomAPIException(
            {'': [KwargsError(code=error_codes.PHONE_OTP_CODES_LIMIT_REACHED)]},
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        )
    send_credential_confirmation_code(user, Credential.PHONE_NUMBER, generate_new=True)
    if limit is not None:
        count_hit(key, limit[1])


def request_login_code(phone_number: str, domain: str) -> CustomUser:
    validator = moses_settings.PHONE_NUMBER_VALIDATOR
    if validator and not validator(phone_number):
        raise CustomAPIException(
            {'phone_number': [KwargsError(
                kwargs={'phone_number': phone_number}, code=error_codes.INVALID_PHONE_NUMBER)]}
        )
    site = Site.objects.filter(domain=domain).first()
    if site is None:
        raise CustomAPIException(
            {'domain': [KwargsError(
                kwargs={'domain': domain}, code=error_codes.SITE_WITH_DOMAIN_DOES_NOT_EXIST)]}
        )
    with transaction.atomic():
        user = CustomUser.objects.filter(site=site, phone_number=phone_number).first()
        if user is None:
            user = CustomUser(phone_number=phone_number, site=site)
            user.set_unusable_password()
            user.save()
        send_login_code(user)
    return user


def wrong_code_error() -> CustomAPIException:
    return CustomAPIException(
        {'code': [KwargsError(code=error_codes.INCORRECT_CONFIRMATION_PIN)]})


def totp_ok(user: CustomUser, otp) -> bool:
    """Strict second factor for OTP login: no DEBUG bypass, a superuser must have a key."""
    if not user.mfa_secret_key:
        return not user.is_superuser
    return isinstance(otp, str) and pyotp.TOTP(user.mfa_secret_key).verify(otp)


def verify_login_code(user: CustomUser, code: str, otp=None) -> bool:
    """Checks a login code; only the main phone pin is used, never the candidate.

    Runs on a row-locked fresh copy so parallel guesses can't lose attempt
    increments or reuse a code, and writes only the fields it changes.
    A superuser or a user with an MFA key also needs a valid TOTP `otp`; a
    missing or wrong one costs an attempt but leaves the SMS code usable.
    """
    with transaction.atomic():
        user = CustomUser.objects.select_for_update().get(pk=user.pk)
        if user.phone_number_confirmation_attempts >= moses_settings.PHONE_NUMBER_CONFIRMATION_ATTEMPTS_LIMIT:
            raise CustomAPIException({'': [KwargsError(code=error_codes.ATTEMPTS_LIMIT_REACHED)]})
        try:
            received = int(code or 0)
        except (TypeError, ValueError):
            received = 0
        pin = user.phone_number_confirmation_pin
        code_ok = received == pin and pin != 0
        if code_ok and totp_ok(user, otp):
            was_confirmed = user.is_phone_number_confirmed
            user.phone_number_confirmation_pin = 0
            user.phone_number_confirmation_attempts = 0
            user.is_phone_number_confirmed = True
            user.save(update_fields=[
                'phone_number_confirmation_pin', 'phone_number_confirmation_attempts',
                'is_phone_number_confirmed'])
            if not was_confirmed:
                phone_number_confirmed.send(
                    sender=user.__class__, user=user, phone_number=user.phone_number,
                    is_initial_confirmation=True)
            return True
        user.phone_number_confirmation_attempts += 1
        user.save(update_fields=['phone_number_confirmation_attempts'])
        if not code_ok:
            return False
    # Raised outside the atomic block so the attempt increment is committed.
    raise CustomAPIException({'otp': [KwargsError(code=error_codes.INVALID_OTP)]})
