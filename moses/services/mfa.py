import pyotp as pyotp
from django.conf import settings as django_settings

def check_mfa_otp(user, otp):
    if user.is_superuser and not django_settings.DEBUG and not user.mfa_secret_key:
        return False
    elif not user.mfa_secret_key:
        return True
    totp = pyotp.totp.TOTP(user.mfa_secret_key.encode('utf-8'))
    return totp.verify(otp)
