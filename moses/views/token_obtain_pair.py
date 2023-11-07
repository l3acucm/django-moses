from rest_framework_simplejwt.views import TokenViewBase

from moses.serializers import TokenObtainPairSerializer


class TokenObtainPairView(TokenViewBase):
    serializer_class = TokenObtainPairSerializer

    def get_serializer_context(self):
        return {
            'request': self.request
        }
