import random

import pyotp as pyotp
from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.core.mail import send_mail
from django.db import models
from django.utils import timezone, translation
from django.utils.timezone import now
from django.utils.translation import gettext as _

from moses.conf import settings as moses_settings
from django.conf import settings as django_settings


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


class CustomUser(AbstractBaseUser, PermissionsMixin):
    class Meta:
        verbose_name = _("User")
        verbose_name_plural = _("Users")

    email = models.EmailField(unique=True, blank=False)
    email_candidate = models.EmailField(blank=True, verbose_name=_("Email candidate"))
    is_email_confirmed = models.BooleanField(default=False, verbose_name=_("Is email confirmed"))
    email_confirm_pin = models.PositiveIntegerField(default=0, verbose_name=_("Email confirm PIN"))
    email_candidate_confirm_pin = models.PositiveIntegerField(default=0, verbose_name=_("Email candidate confirm PIN"))
    email_confirm_attempts = models.PositiveSmallIntegerField(default=0, verbose_name=_("Email confirm attempts"))

    phone_number = models.CharField(max_length=200, unique=True, verbose_name=_("Phone number"))
    phone_number_candidate = models.CharField(max_length=200, blank=True,
                                              verbose_name=_("Phone number candidate"))
    is_phone_number_confirmed = models.BooleanField(default=False, verbose_name=_("Is phone number confirmed"))
    phone_number_confirm_pin = models.PositiveIntegerField(default=0, verbose_name=_("Phone number confirm PIN"))
    phone_number_candidate_confirm_pin = models.PositiveIntegerField(default=0, verbose_name=_(
        "Phone number candidate confirm PIN"))
    phone_number_confirm_attempts = models.PositiveSmallIntegerField(default=0, verbose_name=_("Phone number confirm attempts"))
    last_password_reset_sms_sent_at = models.DateTimeField(blank=True, null=True,
                                                           verbose_name=_("Last password reset sms sent at"))

    first_name = models.CharField(max_length=200, verbose_name=_("First name"), blank=True)
    last_name = models.CharField(max_length=200, verbose_name=_("Last name"), blank=True)

    is_active = models.BooleanField(default=True, verbose_name=_("Is active"))
    is_staff = models.BooleanField(default=False, verbose_name=_("Is staff"))

    preferred_language = models.CharField(choices=moses_settings.LANGUAGE_CHOICES,
                                          default=moses_settings.DEFAULT_LANGUAGE,
                                          max_length=10,
                                          verbose_name=_("Preferred language"))
    created_at = models.DateTimeField(default=timezone.now, blank=True, null=True, verbose_name=_("Created at"))

    mfa_secret_key = models.CharField(blank=True, default='', max_length=160)
    last_phone_number_confirm_pin_sent = models.DateTimeField(default=now)
    last_phone_number_candidate_confirm_pin_sent = models.DateTimeField(default=now)
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
        if generate_new or self.phone_number_confirm_pin == 0:
            self.phone_number_confirm_pin = random.randint(0, 999999)
        self.last_phone_number_confirm_pin_sent = timezone.now()
        self.save()
        with translation.override(self.preferred_language):
            moses_settings.SEND_SMS_HANDLER(self.phone_number,
                                            _("Phone number confirmation PIN: ") + str(
                                                self.phone_number_confirm_pin).zfill(6))

    def send_phone_number_candidate_confirmation_sms(self, generate_new=False):
        if not self.phone_number_candidate:
            return
        if generate_new or self.phone_number_candidate_confirm_pin == 0:
            self.phone_number_candidate_confirm_pin = random.randint(0, 999999)
        self.last_phone_number_candidate_confirm_pin_sent = timezone.now()
        self.save()
        with translation.override(self.preferred_language):
            moses_settings.SEND_SMS_HANDLER(self.phone_number_candidate,
                                            _("Phone number confirmation PIN: ") + str(
                                                self.phone_number_candidate_confirm_pin).zfill(
                                                6))

    def try_to_confirm_email(self, main_pin_str: str, candidate_pin_str: str):
        if self.email_confirm_attempts > 4:
            return False
        try:
            received_pin, received_candidate_pin = int(main_pin_str), int(candidate_pin_str or '0')
            if received_pin == self.email_confirm_pin and (
                    not self.email_candidate or self.email_candidate_confirm_pin == received_candidate_pin):
                self.email_confirm_pin = self.email_candidate_confirm_pin = 0
                self.is_email_confirmed = True
                self.email_confirm_attempts = 0
                if self.email_candidate:
                    self.email = self.email_candidate
                    self.email_candidate = ''
                self.save()
                return True
            else:
                self.email_confirm_attempts += 1
                self.save()
                return False
        except ValueError:
            self.email_confirm_attempts += 1
            self.save()
            return False

    def try_to_confirm_phone_number(self, main_pin_str: str, candidate_pin_str: str):
        try:
            received_pin, received_candidate_pin = int(main_pin_str), int(candidate_pin_str or '0')
            if received_pin == self.phone_number_confirm_pin and \
                    (not self.phone_number_candidate or
                     self.phone_number_candidate_confirm_pin == received_candidate_pin):
                self.phone_number_confirm_pin = 0
                self.is_phone_number_confirmed = True
                self.phone_number_confirm_attempts = 0
                if self.phone_number_candidate:
                    self.phone_number = self.phone_number_candidate
                    self.phone_number_candidate = ''
                self.save()
                return True
            else:
                return False
        except ValueError:
            self.phone_number_confirm_attempts += 1
            self.save()
            return False

    def send_email_confirmation_email(self, generate_new=False):
        if generate_new or self.email_confirm_pin == 0:
            self.email_confirm_pin = random.randint(0, 999999)
            self.save()
        with translation.override(self.preferred_language):
            send_mail(_("Email confirmation PIN"), _("Your email confirmation PIN is: ") + str(self.email_confirm_pin),
                      'noreply@' + django_settings.DOMAIN, [self.email])

    def send_payeer_wallet_changed_email(self):
        with translation.override(self.preferred_language):
            send_mail(_("Payeer wallet has been updated"), _("Your payeer wallet has been updated "),
                      'noreply@' + django_settings.DOMAIN, [self.email])

    def send_email_candidate_confirmation_email(self, generate_new=False):
        if not self.email_candidate:
            return
        if generate_new or self.email_candidate_confirm_pin == 0:
            self.email_candidate_confirm_pin = random.randint(0, 999999)
            self.save()
        with translation.override(self.preferred_language):
            send_mail(_("Email confirmation PIN"),
                      _("Your email confirmation PIN is: ") + str(self.email_candidate_confirm_pin),
                      'noreply@' + django_settings.DOMAIN, [self.email_candidate])

    def __str__(self):
        return f'{self.first_name} {self.last_name}'
