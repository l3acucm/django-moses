from functools import wraps

from django.utils.translation import gettext as _
from rest_framework import status
from rest_framework.response import Response

from moses.common import error_codes
from moses.common.exceptions import CustomAPIException, KwargsError
from moses.services.mfa import check_mfa_otp


def request_passes_test(test_func):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(view, request, *args, **kwargs):
            if test_func(request):
                return view_func(view, request, *args, **kwargs)
            return Response(
                {'errors': {'__all__': [_("OTP not provided")]}, 'data': {}},
                status.HTTP_401_UNAUTHORIZED,
            )
        return _wrapped_view
    return decorator


def otp_required(function=None):
    """
    Decorator for views that checks that the user is logged in, redirecting
    to the log-in page if necessary.
    """
    actual_decorator = request_passes_test(
        lambda request: check_mfa_otp(request.user, request.headers.get('OTP')),
    )
    if function:
        return actual_decorator(function)
    return actual_decorator


def phone_number_confirmed_required(function=None):
    """
    Decorator for views that must only run for users with a confirmed phone
    number (e.g. an action gated separately from login, when
    MOSES['REQUIRE_PHONE_NUMBER_CONFIRMATION_FOR_LOGIN'] is off — see
    moses.serializers.TokenObtainPairSerializer). Raises CustomAPIException
    with PHONE_NUMBER_NOT_CONFIRMED otherwise, so the client can prompt for
    confirmation instead of failing generically.
    """

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(view, request, *args, **kwargs):
            if request.user.is_phone_number_confirmed:
                return view_func(view, request, *args, **kwargs)
            raise CustomAPIException(
                {'': [KwargsError(kwargs={}, code=error_codes.PHONE_NUMBER_NOT_CONFIRMED)]},
                status_code=status.HTTP_403_FORBIDDEN,
            )
        return _wrapped_view

    if function:
        return decorator(function)
    return decorator