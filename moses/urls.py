from django.urls import path, include

from . import views as moses_views
from djoser import views as djoser_views
from rest_framework_simplejwt.views import (
    TokenRefreshView
)

app_name = 'moses'

urlpatterns = [
    path('token/obtain/', moses_views.TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/validate_auth/', moses_views.ValidateAuthView.as_view(), name='token_verify_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    path('mfa/', moses_views.MFAView.as_view(), name='mfa'),

    path('confirm_phone_number/', moses_views.ConfirmPhoneNumber.as_view(), name='confirm_phone_number'),
    path('confirm_email/', moses_views.ConfirmEmail.as_view(), name='confirm_phone_number'),

    path('request_phone_number_pin/', moses_views.RequestPhoneNumberConfirmPin.as_view(),
         name='request_phone_number_confirm_pin'),
    path('request_email_pin/', moses_views.RequestEmailConfirmPin.as_view(), name='request_email_confirm_pin'),

    path('password/', moses_views.SetPasswordView.as_view(), name='set_password'),
    path('password/reset/', moses_views.ResetPassword.as_view(), name='reset-password'),
    path('password/reset/confirm/', djoser_views.UserViewSet.as_view({'post': 'reset_password_confirm'}), name='reset-password-confirm'),
    path('is_email_available/', moses_views.CheckEmailAvailability.as_view(),
         name='check_email_availability'),
    path('is_mfa_enabled_for_phone_number/', moses_views.CheckIsMFAEnabled.as_view(),
         name='check_is_mfa_enabled'),
    path('token/', moses_views.TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    path('roles/', moses_views.GetUserRoles.as_view(), name='user_roles'),

    path('user_by_phone_or_email/', moses_views.UserByPhoneOrEmail.as_view(), name='get_user_by_phone_or_email'),

    path('', include('djoser.urls'))
]
