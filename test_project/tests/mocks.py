def send_sms_handler(a, b):
    from test_project.tests.accounts import remember_pin
    remember_pin(a, b)


def validate_phone_number(a):
    return True
