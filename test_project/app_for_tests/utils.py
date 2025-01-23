import base64
import random
import re
import string


def get_random_pin_non_equal_to(pin_str):
    while (new_pin := str(random.randint(0, 999999)).zfill(6)) == pin_str:
        continue
    return new_pin


SENT_SMS = {}


def remember_pin(to, body):
    numbers_in_body = re.findall(r'\d+', body)
    SENT_SMS[to] = int(numbers_in_body[0]) if len(numbers_in_body) else None


def get_random_mfa_key():
    return base64.b32encode(
        bytes(
            ''.join(
                random.choice(string.ascii_letters) for _ in range(16)
            ).encode('utf-8')
        )
    ).decode('utf-8')
