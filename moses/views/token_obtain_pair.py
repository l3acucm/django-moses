from rest_framework.exceptions import NotFound
from rest_framework_simplejwt.views import TokenViewBase

from moses.conf import settings as moses_settings
from moses.serializers import TokenObtainPairSerializer


class TokenObtainPairView(TokenViewBase):
    serializer_class = TokenObtainPairSerializer

    def get_serializer_context(self):
        return {
            'request': self.request
        }

    def post(self, request, *args, **kwargs):
        if moses_settings.PHONE_OTP_LOGIN:
            raise NotFound()
        return super().post(request, *args, **kwargs)
