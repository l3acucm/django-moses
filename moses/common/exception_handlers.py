from rest_framework.views import exception_handler

from moses.common.exceptions import CustomAPIException


def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)

    if response is not None and isinstance(exc, CustomAPIException):
        response.data = {
            "errors": exc.errors_repr,
            "data": {},
        }
        response.status_code = exc.status_code
    elif response is not None:
        response.data = {
            "errors": response.data,
            "data": {},
        }

    return response