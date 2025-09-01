import uuid

import pyotp as pyotp
from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext as _

from moses.conf import settings as moses_settings
from moses.enums import Credential


class CustomUserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, phone_number, password, **extra_fields):
        user = self.model(phone_number=phone_number, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, phone_number=None, password=None, **extra_fields):
        from moses.services.credentials_confirmation import send_credential_confirmation_code
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        extra_fields.setdefault('is_active', True)
        user = self._create_user(phone_number, password, **extra_fields)
        if moses_settings.REQUIRE_EMAIL_CONFIRMATION:
            send_credential_confirmation_code(user, Credential.EMAIL, generate_new=True)
        if moses_settings.REQUIRE_PHONE_NUMBER_CONFIRMATION:
            send_credential_confirmation_code(user, Credential.PHONE_NUMBER, generate_new=True)
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
    password_reset_code_sms_unlocks_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name=_("Password reset code unlocks at")
    )
    phone_number_confirmation_code_sms_unlocks_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name=_("Phone number confirmation code unlocks at")
    )
    phone_number_candidate_confirmation_code_sms_unlocks_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name=_("Phone number candidate confirmation code unlocks at")
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

    def __str__(self):
        return f'{self.first_name} {self.last_name}'
