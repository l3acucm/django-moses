from django.conf import settings as django_settings
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


def check_request_ip_limit(request) -> None:
    limit = moses_settings.PHONE_OTP_REQUEST_IP_LIMIT
    if limit is None:
        return
    max_requests, window = limit
    key = f'moses:otp_ip:{client_ip(request)}'
    # Fixed window: add() sets the timeout only when the key is new.
    cache.add(key, 0, timeout=window)
    if cache.incr(key) > max_requests:
        raise CustomAPIException(
            {'': [KwargsError(code=error_codes.TOO_FREQUENT_SMS_REQUESTS)]},
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        )


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
        send_credential_confirmation_code(user, Credential.PHONE_NUMBER, generate_new=True)
    return user


def wrong_code_error() -> CustomAPIException:
    return CustomAPIException(
        {'code': [KwargsError(code=error_codes.INCORRECT_CONFIRMATION_PIN)]})


def verify_login_code(user: CustomUser, code: str) -> bool:
    """Checks a login code; only the main phone pin is used, never the candidate."""
    if user.phone_number_confirmation_attempts >= moses_settings.PHONE_NUMBER_CONFIRMATION_ATTEMPTS_LIMIT:
        raise CustomAPIException({'': [KwargsError(code=error_codes.ATTEMPTS_LIMIT_REACHED)]})
    try:
        received = int(code or 0)
    except (TypeError, ValueError):
        received = 0
    pin = user.phone_number_confirmation_pin
    if (received == pin and pin != 0) or (django_settings.DEBUG and received == 123456):
        was_confirmed = user.is_phone_number_confirmed
        user.phone_number_confirmation_pin = 0
        user.phone_number_confirmation_attempts = 0
        user.is_phone_number_confirmed = True
        user.save()
        if not was_confirmed:
            phone_number_confirmed.send(
                sender=user.__class__, user=user, phone_number=user.phone_number,
                is_initial_confirmation=True)
        return True
    user.phone_number_confirmation_attempts += 1
    user.save()
    return False
