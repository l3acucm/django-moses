import random
from datetime import timedelta

from django.core.mail import send_mail
from django.utils import translation, timezone
from django.utils.timezone import now

from moses.common import error_codes
from moses.common.exceptions import CustomAPIException, KwargsError
from moses.conf import settings as moses_settings
from moses.constants import strings
from moses.enums import Credential, SMSType
from moses.services.sms import sms_unlock_time


def send_email_confirmation_message(email: str, body: str):
    send_mail(str(strings.EMAIL_CONFIRMATION_PIN_TITLE), body, moses_settings.SENDER_EMAIL, [email])


def try_to_confirm_credential(user, credential: Credential, main_pin_str: str, candidate_pin_str: str):
    match credential:
        case Credential.PHONE_NUMBER:
            attempts_field = 'phone_number_confirmation_attempts'
            current_credential_field = 'phone_number'
            candidate_credential_field = 'phone_number_candidate'
            current_credential_confirmation_field = 'is_phone_number_confirmed'
            max_attempts_limit = moses_settings.PHONE_NUMBER_CONFIRMATION_ATTEMPTS_LIMIT
            current_pin_field = 'phone_number_confirmation_pin'
            candidate_pin_field = 'phone_number_candidate_confirmation_pin'
        case Credential.EMAIL:
            attempts_field = 'email_confirmation_attempts'
            current_credential_field = 'email'
            candidate_credential_field = 'email_candidate'
            current_credential_confirmation_field = 'is_email_confirmed'
            max_attempts_limit = moses_settings.EMAIL_CONFIRMATION_ATTEMPTS_LIMIT
            current_pin_field = 'email_confirmation_pin'
            candidate_pin_field = 'email_candidate_confirmation_pin'
        case _:
            raise ValueError(error_codes.INVALID_CREDENTIAL)
    if getattr(user, attempts_field) >= max_attempts_limit:
        raise CustomAPIException(
            {
                '': [
                    KwargsError(
                        code=error_codes.ATTEMPTS_LIMIT_REACHED)
                ]
            }
        )
    received_pin, received_candidate_pin = int(main_pin_str or '0'), int(candidate_pin_str or '0')
    is_main_pin_correct = received_pin == getattr(user, current_pin_field)
    is_candidate_pin_correct = None
    if getattr(user, candidate_credential_field):
        is_candidate_pin_correct = getattr(user, candidate_pin_field) == received_candidate_pin
    if is_main_pin_correct and (is_candidate_pin_correct is None or is_candidate_pin_correct):
        setattr(user, current_pin_field, 0)
        setattr(user, candidate_pin_field, 0)
        setattr(user, current_credential_confirmation_field, True)
        setattr(user, attempts_field, 0)
        if candidate := getattr(user, candidate_credential_field):
            setattr(user, current_credential_field, candidate)
            setattr(user, candidate_credential_field, '')
        user.save()
    else:
        setattr(user, attempts_field, getattr(user, attempts_field) + 1)
        user.save()
    return is_main_pin_correct, is_candidate_pin_correct


def send_credential_confirmation_code(
        user,
        credential_type:
        Credential,
        candidate=False,
        generate_new=False,
        ignore_frequency_limit=False
):
    match credential_type:
        case Credential.PHONE_NUMBER:
            send_function = moses_settings.SEND_SMS_HANDLER
            message_body = str(strings.PHONE_NUMBER_CONFIRMATION_PIN_BODY)
            if candidate:
                unlock_time_field = 'phone_number_candidate_confirmation_code_sms_unlocks_at'
                credential_field = 'phone_number_candidate'
                pin_field = 'phone_number_candidate_confirmation_pin'
            else:
                unlock_time_field = 'phone_number_confirmation_code_sms_unlocks_at'
                credential_field = 'phone_number'
                pin_field = 'phone_number_confirmation_pin'
            if (
                    (
                            sut := sms_unlock_time(
                                user,
                                SMSType.PHONE_NUMBER_CONFIRMATION,
                                candidate=candidate)
                    ) is None or sut <= timezone.now() or ignore_frequency_limit
            ):
                new_unlock_time = now() + timedelta(minutes=moses_settings.PHONE_NUMBER_CONFIRMATION_SMS_MINUTES_PERIOD)
                setattr(user, unlock_time_field, new_unlock_time)
            else:
                raise CustomAPIException(
                    {
                        '': [
                            KwargsError(code=error_codes.TOO_FREQUENT_SMS_REQUESTS)
                        ]
                    }
                )
        case Credential.EMAIL:
            send_function = send_email_confirmation_message
            message_body = str(strings.EMAIL_CONFIRMATION_PIN_BODY)
            if candidate:
                credential_field = 'email_candidate'
                pin_field = 'email_candidate_confirmation_pin'
            else:
                credential_field = 'email'
                pin_field = 'email_confirmation_pin'
        case _:
            raise ValueError(error_codes.INVALID_CREDENTIAL_TYPE)

    if generate_new:
        setattr(user, pin_field, random.randint(100000, 999999))
    user.save()
    with translation.override(user.preferred_language):
        send_function(getattr(user, credential_field), message_body % getattr(user, pin_field))
