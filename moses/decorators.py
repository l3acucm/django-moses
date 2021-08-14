from functools import wraps

from django.utils.translation import gettext as _
from rest_framework import status
from rest_framework.response import Response


def request_passes_test(test_func):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(view, request, *args, **kwargs):
            if test_func(request):
                return view_func(view, request, *args, **kwargs)
            return Response({'error': _("OTP not provided")}, status.HTTP_401_UNAUTHORIZED)
        return _wrapped_view
    return decorator


def otp_required(function=None):
    """
    Decorator for views that checks that the user is logged in, redirecting
    to the log-in page if necessary.
    """
    actual_decorator = request_passes_test(
        lambda request: request.user.check_mfa_otp(request.headers.get('OTP')),
    )
    if function:
        return actual_decorator(function)
    return actual_decorator