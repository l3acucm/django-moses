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
