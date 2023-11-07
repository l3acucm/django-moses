import random
import uuid
from datetime import timedelta
from enum import Enum

import pyotp as pyotp
from django.conf import settings as django_settings
from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.core.mail import send_mail
from django.db import models
from django.utils import timezone, translation
from django.utils.translation import gettext as _

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
        user.send_phone_number_confirmation_sms(generate_new=True)
        user.send_email_confirmation_email(generate_new=True)
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
    EMAIL = 'email'
    PHONE_NUMBER = 'phone_number'


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
    last_password_reset_sms_sent_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name=_("Last password reset sms sent at")
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
    last_phone_number_confirmation_pin_sent = models.DateTimeField(null=True, blank=True)
    last_phone_number_candidate_confirmation_pin_sent = models.DateTimeField(null=True, blank=True)
    userpic = models.ImageField(upload_to='images/userpics/', blank=True, null=True)

    USERNAME_FIELD = 'phone_number'

    objects = CustomUserManager()

    def check_mfa_otp(self, otp):
        if self.is_superuser and not django_settings.DEBUG and not self.mfa_secret_key:
            return False
        elif not self.mfa_secret_key:
            return True
        totp = pyotp.totp.TOTP(self.mfa_secret_key.encode('utf-8'))
        return totp.verify(otp)

    def send_phone_number_confirmation_sms(self, generate_new=False):
        if generate_new or self.phone_number_confirmation_pin == 0:
            self.phone_number_confirmation_pin = random.randint(0, 999999)
        self.last_phone_number_confirmation_pin_sent = timezone.now()
        self.save()
        with translation.override(self.preferred_language):
            moses_settings.SEND_SMS_HANDLER(
                self.phone_number,
                _("Phone number confirmation PIN: ") + str(self.phone_number_confirmation_pin).zfill(6)
            )

    def send_phone_number_candidate_confirmation_sms(self, generate_new=False):
        if not self.phone_number_candidate:
            return
        if generate_new or self.phone_number_candidate_confirmation_pin == 0:
            self.phone_number_candidate_confirmation_pin = random.randint(0, 999999)
        if (
                self.last_phone_number_candidate_confirmation_pin_sent is not None and
                self.last_phone_number_candidate_confirmation_pin_sent > timezone.now() - timedelta(
            minutes=moses_settings.MINUTES_BETWEEN_CONFIRMATION_PIN_SMS
        )):
            return
        self.last_phone_number_candidate_confirmation_pin_sent = timezone.now()
        self.save()
        with translation.override(self.preferred_language):
            moses_settings.SEND_SMS_HANDLER(
                self.phone_number_candidate,
                _("Phone number confirmation PIN: ") + str(
                    self.phone_number_candidate_confirmation_pin).zfill(
                    6))

    def try_to_confirm_credential(self, credential: Credential, main_pin_str: str, candidate_pin_str: str):
        match credential:
            case Credential.PHONE_NUMBER:
                attempts_field = 'phone_number_confirmation_attempts'
                current_credential_field = 'phone_number'
                candidate_credential_field = 'phone_number_candidate'
                current_credential_confirmation_field = 'is_phone_number_confirmed'
                max_attempts_limit = moses_settings.MAX_PHONE_NUMBER_CONFIRMATION_ATTEMPTS
                current_pin_field = 'phone_number_confirmation_pin'
                candidate_pin_field = 'phone_number_candidate_confirmation_pin'
            case Credential.EMAIL:
                attempts_field = 'email_confirmation_attempts'
                current_credential_field = 'email'
                candidate_credential_field = 'email_candidate'
                current_credential_confirmation_field = 'is_email_confirmed'
                max_attempts_limit = moses_settings.MAX_EMAIL_CONFIRMATION_ATTEMPTS
                current_pin_field = 'email_confirmation_pin'
                candidate_pin_field = 'email_candidate_confirmation_pin'
            case _:
                raise ValueError('invalid_credential')
        if getattr(self, attempts_field) == max_attempts_limit:
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

    def send_email_confirmation_email(self, generate_new=False):
        if generate_new or self.email_confirmation_pin == 0:
            self.email_confirmation_pin = random.randint(0, 999999)
            self.save()
        with translation.override(self.preferred_language):
            send_mail(_("Email confirmation PIN"),
                      _("Your email confirmation PIN is: ") + str(self.email_confirmation_pin),
                      'noreply@' + moses_settings.DOMAIN, [self.email])

    def send_email_candidate_confirmation_email(self, generate_new=False):
        if not self.email_candidate:
            return
        if generate_new or self.email_candidate_confirmation_pin == 0:
            self.email_candidate_confirmation_pin = random.randint(0, 999999)
            self.save()
        with translation.override(self.preferred_language):
            send_mail(_("Email confirmation PIN"),
                      _("Your email confirmation PIN is: ") + str(self.email_candidate_confirmation_pin),
                      'noreply@' + django_settings.DOMAIN, [self.email_candidate])

    def __str__(self):
        return f'{self.first_name} {self.last_name}'
