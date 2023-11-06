from rest_framework.exceptions import ValidationError

from moses import errors


def send_sms_handler(a, b):
    from test_project.tests.confirmations import remember_pin
    remember_pin(a, b)


def validate_phone_number(a):
    if len(a) < 10 and len(a) != 2:
        raise ValidationError(errors.INCORRECT_PHONE_NUMBER)
