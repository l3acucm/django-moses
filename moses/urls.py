from django.urls import path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import (
    TokenRefreshView
)

from .views.token_obtain_pair import TokenObtainPairView
from .views.user import UserViewSet

router = DefaultRouter()
router.register("users", UserViewSet)

app_name = 'moses'

urlpatterns = [
                  path('token/obtain/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
                  path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
              ] + router.urls
