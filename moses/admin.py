import logging

from django import forms
from django.contrib import admin
from django.contrib.admin.forms import AdminAuthenticationForm
from django.contrib.auth import authenticate
from django.contrib.auth.signals import user_login_failed
from django.contrib.auth.admin import UserAdmin
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.translation import gettext_lazy as _

from .common.exceptions import CustomAPIException
from .conf import WITH_PASSWORD, WITHOUT_PASSWORD, login_methods
from .models import CustomUser
from .services import otp_login
from .services.anonymize import anonymize_user


logger = logging.getLogger(__name__)


class OTPAdminAuthenticationForm(AdminAuthenticationForm):
    """Admin login by password and/or by SMS code, per MOSES["LOGIN_METHODS"]."""
    otp = forms.CharField(required=False)
    domain = forms.CharField(required=False)
    code_sent_message = _('Если номер принадлежит сотруднику, код отправлен')

    def __init__(self, request=None, *args, **kwargs):
        super().__init__(request, *args, **kwargs)
        methods = login_methods()
        self.code_sent = False
        if WITH_PASSWORD not in methods:
            del self.fields['password']
        elif WITHOUT_PASSWORD in methods:
            self.fields['password'].required = False
        if WITHOUT_PASSWORD in methods:
            self.fields['code'] = forms.CharField(required=False, label=_('Код из SMS'))

    def clean(self):
        username = self.cleaned_data.get('username')
        password = self.cleaned_data.get('password')
        code = self.cleaned_data.get('code')
        otp = self.cleaned_data.get('otp')
        domain = self.cleaned_data.get('domain')

        if 'code' in self.fields and 'send_code' in self.data:
            if username:
                self._send_code(username, domain)
            # Same answer whoever the number belongs to; the template shows it
            # as a notice, not an error. The form stays invalid, so no login.
            self.code_sent = True
            raise ValidationError(self.code_sent_message, code='code_sent')

        if username and code:
            self.user_cache = self._user_by_code(username, domain, code, otp)
            if self.user_cache is None:
                user_login_failed.send(
                    sender=__name__, credentials={'username': username, 'domain': domain}, request=self.request)
                raise self.get_invalid_login_error()
            self.confirm_login_allowed(self.user_cache)
        elif username is not None and password:
            self.user_cache = authenticate(
                self.request,
                username=username,
                password=password,
                otp=otp,
                domain=domain
            )
            if self.user_cache is None:
                raise self.get_invalid_login_error()
            else:
                self.confirm_login_allowed(self.user_cache)
        elif not self.errors:  # nothing to log in with
            raise self.get_invalid_login_error()

        return self.cleaned_data

    @staticmethod
    def _staff(username, domain):
        return CustomUser.objects.filter(
            site__domain=domain or '', phone_number=username, is_staff=True, is_active=True)

    def _send_code(self, username, domain):
        """Never creates users; limits and the resend pause are swallowed so
        a refusal can't tell a staff number from any other."""
        try:
            otp_login.check_request_ip_limit(self.request)
            with transaction.atomic():
                user = self._staff(username, domain).select_for_update().first()
                if user is not None:
                    otp_login.send_login_code(user)
        except CustomAPIException:
            pass
        except Exception:  # SMS gateway down etc.: same neutral answer
            logger.exception('Admin login code could not be sent')

    def _user_by_code(self, username, domain, code, otp):
        user = self._staff(username, domain).first()
        if user is None:
            return None
        try:
            result = otp_login.verify_login_code(user, code, otp=otp)
        except CustomAPIException:  # right code but bad TOTP, or attempts limit
            return None
        if result is None:
            return None
        user.backend = 'moses.authentication.MFAModelBackend'
        return user


class CustomUserAdmin(UserAdmin):
    model = CustomUser

    fieldsets = (

        ('Personal info', {
            'fields': (
                'first_name',
                'last_name',
                'preferred_language',)
        }),('Site', {
            'fields': (
                'site',
                )
        }),
        ('Contacts', {'fields': (
            'email',
            'email_candidate',
            'is_email_confirmed',
            'email_confirmation_pin',
            'email_candidate_confirmation_pin',
            'email_confirmation_attempts',
            'phone_number',
            'phone_number_candidate',
            'is_phone_number_confirmed',
            'phone_number_confirmation_pin',
            'phone_number_candidate_confirmation_pin',
            'phone_number_confirmation_attempts',
            'password_reset_code_sms_unlocks_at',
        )}),
        ('Access', {
            'fields': (
                'is_active',
                'is_staff'
            ),
        }),
        ('Security', {'fields': ('password', 'mfa_secret_key', 'mfa_url')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide', ),
            'fields': ('phone_number', 'email', 'password1', 'password2', 'site'),
        }),
    )

    list_display = (
        'id', 'first_name', 'last_name', 'phone_number', 'email', 'created_at')
    readonly_fields = ('mfa_url', )
    ordering = ('-created_at',)
    list_filter = ('is_staff', 'is_superuser', 'is_active', 'groups')
    search_fields = ('phone_number', 'first_name', 'last_name', 'email', 'id')

    # «Delete» anonymizes (see moses.services.anonymize) instead of cascading
    # away everything that points at the user.
    def delete_model(self, request, obj):
        anonymize_user(obj)

    def delete_queryset(self, request, queryset):
        with transaction.atomic():
            for user in queryset:
                anonymize_user(user)

    def has_delete_permission(self, request, obj=None):
        # Refuse up front, before Django logs the deletion and reports success.
        if obj is not None and obj.is_superuser:
            return False
        return super().has_delete_permission(request, obj)

    def get_deleted_objects(self, objs, request):
        # Nothing cascades: only the users themselves. A superuser among them
        # lands in perms_needed, which makes delete_selected refuse the whole action.
        to_delete = [str(o) for o in objs]
        perms_needed = {str(o) for o in objs if o.is_superuser}
        return to_delete, {self.opts.verbose_name_plural: len(to_delete)}, perms_needed, []


admin.site.register(CustomUser, CustomUserAdmin)
