from typing import List

from rest_framework import status
from rest_framework.response import Response


class UnifiedResponse:
    def __init__(
            self,
            data: List[dict] | dict | None = None,
            errors: dict | None = None,
            status_code: int = status.HTTP_200_OK
    ):
        if data is None and errors is None:
            raise ValueError("Data and errors can't be both None")
        self.data = data
        self.errors = errors or []
        self.status_code = status_code

        super().__init__()

    def to_response(self) -> Response:
        return Response(
            {
                'data': self.data,
                'errors': self.errors
            },
            status=self.status_code
        )
