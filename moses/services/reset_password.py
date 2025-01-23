import random
from datetime import timedelta

from django.core.mail import send_mail
from django.utils import timezone

from moses.common import error_codes
from moses.common.exceptions import CustomAPIException, KwargsError
from moses.conf import settings as moses_settings
from moses.constants import strings
from moses.enums import SMSType, Credential
from moses.services.sms import sms_unlock_time


def send_password_reset_code(user, credential: Credential) -> bool:
    match credential:
        case user.email:
            if user.is_email_confirmed:
                user.password_reset_code = random.randint(0, 1000000)
                user.save()
                message_body = str(strings.PASSWORD_RESET_PIN_BODY) % user.password_reset_code
                send_mail(str(strings.PASSWORD_RESET_PIN_TITLE), message_body, moses_settings.SENDER_EMAIL, [user.email])
                return True
            return False
        case user.phone_number:
            if user.is_phone_number_confirmed:
                if (sut:=sms_unlock_time(user, SMSType.PASSWORD_RESET)) is None or sut <= timezone.now():
                    user.password_reset_code = random.randint(100000, 999999)
                    user.password_reset_code_sms_unlocks_at = timezone.now() + timedelta(
                        minutes=moses_settings.PASSWORD_RESET_TIMEOUT_MINUTES)
                    user.save()
                    message_body = str(strings.PASSWORD_RESET_PIN_BODY) % user.password_reset_code
                    moses_settings.SEND_SMS_HANDLER(user.phone_number, message_body)
                    return True
                else:
                    raise CustomAPIException(
                        {
                            '': [
                                KwargsError(
                                    kwargs={},
                                    code=error_codes.TOO_FREQUENT_SMS_REQUESTS)
                            ]
                        }
                    )

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
