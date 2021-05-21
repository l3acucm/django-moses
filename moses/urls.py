from django.urls import path

from django.urls import include

from . import views as accounts_views
from rest_framework_simplejwt.views import (
    TokenRefreshView
)

from .views import TokenObtainPairView, TokenVerifyView, ConfirmPhoneNumber, ConfirmEmail, \
    RequestPhoneNumberConfirmPin, RequestEmailConfirmPin

app_name = 'moses'

urlpatterns = [
    path('token/obtain/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/verify_mfa/', TokenVerifyView.as_view(), name='token_verify_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    path('mfa/', accounts_views.MFAView.as_view(), name='mfa'),

    path('confirm_phone_number/', ConfirmPhoneNumber.as_view(), name='confirm_phone_number'),
    path('confirm_email/', ConfirmEmail.as_view(), name='confirm_phone_number'),

    path('request_phone_number_pin/', RequestPhoneNumberConfirmPin.as_view(),
         name='request_phone_number_confirm_pin'),
    path('request_email_pin/', RequestEmailConfirmPin.as_view(), name='request_email_confirm_pin'),

    path('password/', accounts_views.SetPasswordView.as_view(), name='set_password'),
    path('password/reset/', accounts_views.ResetPassword.as_view(), name='reset-password'),
    path('is_email_available/', accounts_views.CheckEmailAvailability.as_view(),
         name='check_email_availability'),
    path('is_mfa_enabled_for_phone_number/', accounts_views.CheckIsMFAEnabled.as_view(),
         name='check_is_mfa_enabled'),
    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('', include('djoser.urls'))
]
