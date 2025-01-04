from typing import Dict, List

from rest_framework import status
from rest_framework.exceptions import APIException


class KwargsError(object):
    code: str
    kwargs: Dict[str, str]

    def __init__(self, code: str, kwargs: Dict[str, str] | None = None):
        self.code = code
        self.kwargs = kwargs


class CustomAPIException(APIException):
    default_detail = "Invalid input."
    default_code = "error"

    def __init__(self, errors: Dict[str, List[KwargsError]], status_code=status.HTTP_400_BAD_REQUEST):
        """
        :param errors: List of error dictionaries, each with `code` and optional `kwargs`.
        """
        if not isinstance(errors, dict):
            raise ValueError("Errors must be a dict.")
        self.detail = 'Bad request'
        self.status_code = status_code
        self.errors_repr = {
            field_name: [
                {
                    'error_code': error.code,
                    'kwargs': error.kwargs,
                }
                for error in errors
            ]
            for field_name, errors in errors.items()
        }
