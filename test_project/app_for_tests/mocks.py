def send_sms_handler(to, body):
    print('inside sms handler: %s'% body)
    from test_project.app_for_tests.utils import remember_pin, remember_raw_sms
    remember_pin(to, body)
    remember_raw_sms(to, body)


def validate_phone_number(a) -> bool:
    return len(a) > 10 or len(a) == 2
