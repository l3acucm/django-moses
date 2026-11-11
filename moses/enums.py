from enum import Enum


class Credential(Enum):
    EMAIL = 1
    PHONE_NUMBER = 2


class SMSType(Enum):
    PASSWORD_RESET = 1
    PHONE_NUMBER_CONFIRMATION = 2
