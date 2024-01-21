from django import forms
from django.contrib import admin
from django.contrib.admin.forms import AdminAuthenticationForm
from django.contrib.auth import authenticate
from django.contrib.auth.admin import UserAdmin

from .models import CustomUser


class OTPAdminAuthenticationForm(AdminAuthenticationForm):
    otp = forms.CharField(required=False)
    domain = forms.CharField(required=False)

    def clean(self):
        username = self.cleaned_data.get('username')
        password = self.cleaned_data.get('password')
        otp = self.cleaned_data.get('otp')
        domain = self.cleaned_data.get('domain')

        if username is not None and password:
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

        return self.cleaned_data


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
            'password_reset_code_sms_sent_at',
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
            'fields': ('phone_number', 'email', 'password1', 'password2'),
        }),
    )

    list_display = (
        'id', 'first_name', 'last_name', 'phone_number', 'email', 'created_at')
    readonly_fields = ('mfa_url', )
    ordering = ('-created_at',)
    list_filter = ('is_staff', 'is_superuser', 'is_active', 'groups')
    search_fields = ('phone_number', 'first_name', 'last_name', 'email', 'id')


admin.site.register(CustomUser, CustomUserAdmin)
