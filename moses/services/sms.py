from moses.common import error_codes
from moses.enums import SMSType
from moses.models import CustomUser


def sms_unlock_time(user: CustomUser, sms_type: SMSType, candidate:bool = False):
    match sms_type:
        case SMSType.PASSWORD_RESET:
            return user.password_reset_code_sms_unlocks_at
        case SMSType.PHONE_NUMBER_CONFIRMATION:
            if candidate:
                return user.phone_number_candidate_confirmation_code_sms_unlocks_at
            return user.phone_number_confirmation_code_sms_unlocks_at
        case _:
            raise ValueError(error_codes.INVALID_SMS_TYPE)
