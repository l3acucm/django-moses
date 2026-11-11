from django.urls import path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import (
    TokenRefreshView
)

from .views.google_auth import GoogleSignInView, GoogleCompleteRegistrationView
from .views.telegram_auth import TelegramSignInView, TelegramCompleteRegistrationView
from .views.token_obtain_pair import TokenObtainPairView
from .views.user import UserViewSet

router = DefaultRouter()
router.register("users", UserViewSet)

app_name = 'moses'

urlpatterns = [
                  path('token/obtain/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
                  path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
                  path('token/google/', GoogleSignInView.as_view(), name='google_sign_in'),
                  path('token/google/complete/', GoogleCompleteRegistrationView.as_view(), name='google_complete_registration'),
                  path('token/telegram/', TelegramSignInView.as_view(), name='telegram_sign_in'),
                  path('token/telegram/complete/', TelegramCompleteRegistrationView.as_view(), name='telegram_complete_registration'),
              ] + router.urls
