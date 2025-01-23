from rest_framework.exceptions import NotAuthenticated
from rest_framework.views import exception_handler

from moses.common.exceptions import CustomAPIException


def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)

    if response is not None:
        if isinstance(exc, CustomAPIException):
            response.data = {
                "errors": exc.errors_repr,
                "data": {},
            }
            response.status_code = exc.status_code
        elif isinstance(exc, NotAuthenticated):
            response.data = {
                "errors": {
                    '':[
                        {'error_code': exc.default_code, 'kwargs': {}}
                    ]
                },
                "data": {},
            }
        else:
            response.data = {
                "errors": response.data,
                "data": {},
            }

    return response