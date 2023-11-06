import base64
import random
import string


def get_random_mfa_key():
    return base64.b32encode(
        bytes(
            ''.join(
                random.choice(string.ascii_letters) for _ in range(16)
            ).encode('utf-8')
        )
    ).decode('utf-8')
