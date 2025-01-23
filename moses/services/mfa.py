import pyotp as pyotp
from django.conf import settings as django_settings

def check_mfa_otp(self, otp):
    if self.is_superuser and not django_settings.DEBUG and not self.mfa_secret_key:
        return False
    elif not self.mfa_secret_key:
        return True
    totp = pyotp.totp.TOTP(self.mfa_secret_key.encode('utf-8'))
    return totp.verify(otp)
