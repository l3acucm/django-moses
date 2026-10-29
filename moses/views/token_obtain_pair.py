from rest_framework.exceptions import NotFound
from rest_framework_simplejwt.views import TokenViewBase

from moses.conf import login_methods, WITH_PASSWORD
from moses.serializers import TokenObtainPairSerializer


class TokenObtainPairView(TokenViewBase):
    serializer_class = TokenObtainPairSerializer

    def get_serializer_context(self):
        return {
            'request': self.request
        }

    def post(self, request, *args, **kwargs):
        if WITH_PASSWORD not in login_methods():
            raise NotFound()
        return super().post(request, *args, **kwargs)
