import secrets
from datetime import timedelta

from django.conf import settings as django_settings
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

from moses.common import error_codes
from moses.common.exceptions import CustomAPIException, KwargsError
from moses.conf import settings as moses_settings
from moses.enums import SMSType, Credential
from moses.models import CustomUser
from moses.services import otp_login
from moses.services.messages import render_message
from moses.services.sms import sms_unlock_time


def start_reset_pause(user) -> None:
    """Refuses inside the PASSWORD_RESET_TIMEOUT_SECONDS pause (phone and email share it), else starts it."""
    if (sut := sms_unlock_time(user, SMSType.PASSWORD_RESET)) is not None and sut > timezone.now():
        raise CustomAPIException({'': [KwargsError(kwargs={}, code=error_codes.TOO_FREQUENT_SMS_REQUESTS)]})
    user.password_reset_code_sms_unlocks_at = timezone.now() + timedelta(
        seconds=moses_settings.PASSWORD_RESET_TIMEOUT_SECONDS)


def send_password_reset_code(user, credential: Credential) -> bool:
    bypass_confirmation = moses_settings.CAN_RESET_PASSWORD_WITHOUT_PHONE_NUMBER_CONFIRMATION
    match credential:
        case user.email:
            if user.is_email_confirmed or bypass_confirmation:
                start_reset_pause(user)
                user.password_reset_code = secrets.randbelow(1000001)
                user.password_reset_code_attempts = 0
                user.save()
                title = render_message('PASSWORD_RESET_PIN_TITLE', user, pin=user.password_reset_code)
                body = render_message('PASSWORD_RESET_EMAIL_BODY', user, pin=user.password_reset_code)
                send_mail(title, body, moses_settings.SENDER_EMAIL, [user.email])
                return True
            return False
        case user.phone_number:
            if user.is_phone_number_confirmed or bypass_confirmation:
                start_reset_pause(user)
                # Shares the per-phone count of unused codes with login codes.
                otp_login.check_phone_codes_limit(user)
                user.password_reset_code = 100000 + secrets.randbelow(900000)
                user.password_reset_code_attempts = 0
                user.save()
                body = render_message('PASSWORD_RESET_SMS_BODY', user, pin=user.password_reset_code)
                moses_settings.SEND_SMS_HANDLER(user.phone_number, body)
                otp_login.count_phone_code(user)
                return True

            raise CustomAPIException(
                {
                    'credential': [
                        KwargsError(
                            kwargs={},
                            code=error_codes.PHONE_NUMBER_NOT_CONFIRMED)
                    ]
                }
            )
        case _:
            raise CustomAPIException(
                {
                    'credential': [
                        KwargsError(
                            kwargs={},
                            code=error_codes.INVALID_CREDENTIAL)
                    ]
                }
            )


def use_password_reset_code(user, code: int):
    """Checks a reset code on a row-locked fresh copy and returns it with the code burned.

    Mirrors verify_login_code: PHONE_NUMBER_CONFIRMATION_ATTEMPTS_LIMIT wrong
    guesses burn the code, after which every try gets attempts_limit_reached
    until a new code is sent. The right code works once.
    """
    with transaction.atomic():
        user = CustomUser.objects.select_for_update().get(pk=user.pk)
        limit = moses_settings.PHONE_NUMBER_CONFIRMATION_ATTEMPTS_LIMIT
        if user.password_reset_code_attempts >= limit:
            raise CustomAPIException({'': [KwargsError(code=error_codes.ATTEMPTS_LIMIT_REACHED)]})
        if ((user.password_reset_code is not None and code == user.password_reset_code)
                or (django_settings.DEBUG and code == 123456)):
            user.password_reset_code = None
            user.password_reset_code_attempts = 0
            user.save(update_fields=['password_reset_code', 'password_reset_code_attempts'])
            otp_login.uncount_used_code(user)
            return user
        user.password_reset_code_attempts += 1
        if user.password_reset_code_attempts >= limit:
            user.password_reset_code = None
        user.save(update_fields=['password_reset_code', 'password_reset_code_attempts'])
    # Raised outside the atomic block so the attempt increment is committed.
    raise CustomAPIException({'code': [KwargsError(code=error_codes.INVALID_CONFIRMATION_CODE)]})
