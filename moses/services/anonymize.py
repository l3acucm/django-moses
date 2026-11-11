import secrets

from django.db import transaction
from rest_framework import status

from moses.common import error_codes
from moses.common.exceptions import CustomAPIException, KwargsError
from moses.models import CustomUser
from moses.signals import user_anonymized


def superuser_error():
    return CustomAPIException(
        {'': [KwargsError(error_codes.SUPERUSER_CANNOT_BE_DELETED)]}, status_code=status.HTTP_403_FORBIDDEN)


def _placeholder_phone(site_id):
    # Letters make it an invalid phone; 20 chars = the field's max_length.
    while True:
        phone = 'deleted-' + secrets.token_hex(6)
        if not CustomUser.objects.filter(site_id=site_id, phone_number=phone).exists():
            return phone


@transaction.atomic
def anonymize_user(user) -> None:
    """"Deletes" a user: the row (and everything pointing at it) stays, personal data goes."""
    if user.is_superuser:
        raise superuser_error()
    user.first_name = user.last_name = 'DELETED'
    user.phone_number = _placeholder_phone(user.site_id)
    user.email = user.email_candidate = user.phone_number_candidate = ''
    user.set_unusable_password()
    user.google_sub = user.telegram_id = ''
    user.mfa_secret_key = ''
    user.is_active = False
    user.is_staff = False
    user.is_email_confirmed = False
    user.is_phone_number_confirmed = False
    user.email_confirmation_pin = user.email_candidate_confirmation_pin = 0
    user.phone_number_confirmation_pin = user.phone_number_candidate_confirmation_pin = 0
    user.password_reset_code = None
    user.save()
    user.groups.clear()
    user.user_permissions.clear()
    user_anonymized.send(sender=CustomUser, user=user)
