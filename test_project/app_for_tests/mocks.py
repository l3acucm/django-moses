from rest_framework.exceptions import ValidationError

from moses import errors


def send_sms_handler(to, body):
    from test_project.app_for_tests.utils import remember_pin
    remember_pin(to, body)


def validate_phone_number(a):
    if len(a) < 10 and len(a) != 2:
        raise ValidationError(errors.INCORRECT_PHONE_NUMBER)
