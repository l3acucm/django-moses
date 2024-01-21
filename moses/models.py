import random
import uuid
from enum import Enum

import pyotp as pyotp
from django.conf import settings as django_settings
from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.core.mail import send_mail
from django.db import models
from django.utils import timezone, translation
from django.utils.timezone import now
from django.utils.translation import gettext as _

from moses import errors
from moses.conf import settings as moses_settings


class CustomUserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, phone_number, password, **extra_fields):
        user = self.model(phone_number=phone_number, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, phone_number=None, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        extra_fields.setdefault('is_active', True)
        user = self._create_user(phone_number, password, **extra_fields)
        user.send_credential_confirmation_code(Credential.EMAIL, generate_new=True)
        user.send_credential_confirmation_code(Credential.PHONE_NUMBER, generate_new=True)
        return user

    def create_superuser(self, phone_number, password, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self._create_user(phone_number, password, **extra_fields)


class Credential(Enum):
    EMAIL = 1
    PHONE_NUMBER = 2


class SMSType(Enum):
    PASSWORD_RESET = 1
    PHONE_NUMBER_CONFIRMATION = 2


class CustomUser(AbstractBaseUser, PermissionsMixin):
    class Meta:
        verbose_name = _("User")
        verbose_name_plural = _("Users")
        constraints = [
            models.UniqueConstraint(fields=['site', 'phone_number'], name='one_phone_number_per_site'),
            models.UniqueConstraint(fields=['site', 'email'], name='one_email_per_site')
        ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    site = models.ForeignKey(
        'sites.Site',
        related_name='users',
        on_delete=models.CASCADE
    )

    email = models.EmailField(blank=False)
    email_candidate = models.EmailField(blank=True, verbose_name=_("Email candidate"))
    is_email_confirmed = models.BooleanField(default=False, verbose_name=_("Is email confirmed"))
    email_confirmation_pin = models.PositiveIntegerField(default=0, verbose_name=_("Email confirm PIN"))
    email_candidate_confirmation_pin = models.PositiveIntegerField(default=0,
                                                                   verbose_name=_("Email candidate confirm PIN"))
    email_confirmation_attempts = models.PositiveSmallIntegerField(default=0, verbose_name=_("Email confirm attempts"))

    phone_number = models.CharField(max_length=20, verbose_name=_("Phone number"))
    phone_number_candidate = models.CharField(max_length=20, blank=True, verbose_name=_("Phone number candidate"))
    is_phone_number_confirmed = models.BooleanField(default=False, verbose_name=_("Is phone number confirmed"))
    phone_number_confirmation_pin = models.PositiveIntegerField(default=0, verbose_name=_("Phone number confirm PIN"))
    phone_number_candidate_confirmation_pin = models.PositiveIntegerField(default=0, verbose_name=_(
        "Phone number candidate confirm PIN"))
    phone_number_confirmation_attempts = models.PositiveSmallIntegerField(
        default=0,
        verbose_name=_("Phone number confirm attempts")
    )
    password_reset_code_sms_sent_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name=_("Last password reset code sent at")
    )
    phone_number_confirmation_code_sms_sent_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name=_("Last phone number confirmation code sent at")
    )
    password_reset_code = models.PositiveIntegerField(
        blank=True,
        null=True
    )

    first_name = models.CharField(max_length=200, verbose_name=_("First name"), blank=True)
    last_name = models.CharField(max_length=200, verbose_name=_("Last name"), blank=True)

    is_active = models.BooleanField(default=True, verbose_name=_("Is active"))
    is_staff = models.BooleanField(default=False, verbose_name=_("Is staff"))

    preferred_language = models.CharField(
        choices=moses_settings.LANGUAGE_CHOICES,
        default=moses_settings.DEFAULT_LANGUAGE,
        max_length=10,
        verbose_name=_("Preferred language")
    )
    created_at = models.DateTimeField(default=timezone.now, blank=True, null=True, verbose_name=_("Created at"))

    mfa_secret_key = models.CharField(blank=True, default='', max_length=160)
    last_phone_number_confirmation_pins_sent = models.DateTimeField(null=True, blank=True)

    USERNAME_FIELD = 'phone_number'

    objects = CustomUserManager()

    @property
    def mfa_url(self):
        return pyotp.totp.TOTP(
                    self.mfa_secret_key.encode('utf-8')
                ).provisioning_uri(
                    f"{self.first_name} {self.last_name}",
                    moses_settings.DOMAIN
                )

    def check_mfa_otp(self, otp):
        if self.is_superuser and not django_settings.DEBUG and not self.mfa_secret_key:
            return False
        elif not self.mfa_secret_key:
            return True
        totp = pyotp.totp.TOTP(self.mfa_secret_key.encode('utf-8'))
        return totp.verify(otp)

    def try_to_confirm_credential(self, credential: Credential, main_pin_str: str, candidate_pin_str: str):
        match credential:
            case Credential.PHONE_NUMBER:
                attempts_field = 'phone_number_confirmation_attempts'
                current_credential_field = 'phone_number'
                candidate_credential_field = 'phone_number_candidate'
                current_credential_confirmation_field = 'is_phone_number_confirmed'
                max_attempts_limit = moses_settings.PHONE_NUMBER_CONFIRMATION_ATTEMPTS_LIMIT
                current_pin_field = 'phone_number_confirmation_pin'
                candidate_pin_field = 'phone_number_candidate_confirmation_pin'
            case Credential.EMAIL:
                attempts_field = 'email_confirmation_attempts'
                current_credential_field = 'email'
                candidate_credential_field = 'email_candidate'
                current_credential_confirmation_field = 'is_email_confirmed'
                max_attempts_limit = moses_settings.EMAIL_CONFIRMATION_ATTEMPTS_LIMIT
                current_pin_field = 'email_confirmation_pin'
                candidate_pin_field = 'email_candidate_confirmation_pin'
            case _:
                raise ValueError('invalid_credential')
        if getattr(self, attempts_field) >= max_attempts_limit:
            return False, False
        received_pin, received_candidate_pin = int(main_pin_str or '0'), int(candidate_pin_str or '0')
        is_main_pin_correct = received_pin == getattr(self, current_pin_field)
        is_candidate_pin_correct = None
        if getattr(self, candidate_credential_field):
            is_candidate_pin_correct = getattr(self, candidate_pin_field) == received_candidate_pin
        if is_main_pin_correct and (is_candidate_pin_correct is None or is_candidate_pin_correct):
            setattr(self, current_pin_field, 0)
            setattr(self, candidate_pin_field, 0)
            setattr(self, current_credential_confirmation_field, True)
            setattr(self, attempts_field, 0)
            if candidate := getattr(self, candidate_credential_field):
                setattr(self, current_credential_field, candidate)
                setattr(self, candidate_credential_field, '')
            self.save()
        else:
            setattr(self, attempts_field, getattr(self, attempts_field) + 1)
            self.save()
        return is_main_pin_correct, is_candidate_pin_correct

    def send_credential_confirmation_code(self, credential_type: Credential, candidate=False, generate_new=False):
        match credential_type:
            case Credential.PHONE_NUMBER:
                send_function = moses_settings.SEND_SMS_HANDLER
                if not self.is_sms_timeout(SMSType.PHONE_NUMBER_CONFIRMATION):
                    setattr(self, 'last_phone_number_confirmation_pins_sent', now())
                if candidate:
                    credential_field = 'phone_number_candidate'
                    pin_field = 'phone_number_candidate_confirmation_pin'
                else:
                    credential_field = 'phone_number'
                    pin_field = 'phone_number_confirmation_pin'
                is_attempts_limit_reached = self.phone_number_confirmation_attempts >= moses_settings.PHONE_NUMBER_CONFIRMATION_ATTEMPTS_LIMIT
            case Credential.EMAIL:
                def send_email_confirmation_message(email: str, body: str):
                    send_mail(_("Email confirmation PIN"), body, 'noreply@' + moses_settings.DOMAIN, [email])

                send_function = send_email_confirmation_message
                if candidate:
                    credential_field = 'email_candidate'
                    pin_field = 'email_candidate_confirmation_pin'
                else:
                    credential_field = 'email'
                    pin_field = 'email_confirmation_pin'

                is_attempts_limit_reached = self.email_confirmation_attempts >= moses_settings.EMAIL_CONFIRMATION_ATTEMPTS_LIMIT
            case _:
                raise ValueError('invalid_credential')
        if is_attempts_limit_reached:
            raise ValueError('attempts_limit_reached')
        if self.is_sms_timeout(SMSType.PHONE_NUMBER_CONFIRMATION):
            raise ValueError('sms_timeout')
        if generate_new:
            setattr(self, pin_field, random.randint(0, 999999))
        self.save()
        with translation.override(self.preferred_language):
            send_function(getattr(self, credential_field),
                          _("Your confirmation PIN is: ") + str(getattr(self, pin_field)).zfill(6))

    def is_sms_timeout(self, sms_type: SMSType):
        match sms_type:
            case SMSType.PASSWORD_RESET:
                timeout_in_minutes = moses_settings.PASSWORD_RESET_SMS_MINUTES_PERIOD
                last_sms_sent = self.password_reset_code_sms_sent_at
            case SMSType.PHONE_NUMBER_CONFIRMATION:
                timeout_in_minutes = moses_settings.PHONE_NUMBER_CONFIRMATION_SMS_MINUTES_PERIOD
                last_sms_sent = self.phone_number_confirmation_code_sms_sent_at
            case _:
                raise ValueError('invalid_sms_type')
        return last_sms_sent is not None and (timezone.now() - last_sms_sent).seconds < 60 * timeout_in_minutes

    def send_password_reset_code(self, credential: str) -> bool:
        if self.is_sms_timeout(SMSType.PASSWORD_RESET):
            raise ValueError('sms_timeout')
        self.password_reset_code = random.randint(0, 1000000)
        self.save()
        message_body = _(f"Your password reset code is {self.password_reset_code}")
        match credential:
            case self.email:
                if self.is_email_confirmed:
                    send_mail(_("Password reset"), message_body, 'noreply@' + moses_settings.DOMAIN, [self.email])
                    return True
                return False
            case self.phone_number:
                if self.is_phone_number_confirmed:
                    if not self.is_sms_timeout(SMSType.PASSWORD_RESET):
                        self.password_reset_code_sms_sent_at = timezone.now()
                        self.save()
                        moses_settings.SEND_SMS_HANDLER(self.phone_number, message_body)
                        return True
                    else:
                        raise TimeoutError(errors.TOO_FREQUENT_SMS_REQUESTS)
                return False
            case _:
                return False

    def __str__(self):
        return f'{self.first_name} {self.last_name}'


def generate_sms_code():
    return random.randint(0, 1000000)
