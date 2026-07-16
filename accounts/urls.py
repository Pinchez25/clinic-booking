from django.urls import path
from rest_framework.routers import DefaultRouter

from .throttles import AuthLoginThrottle
from .views import CustomTokenObtainPairView, CustomTokenRefreshView, UserViewSet

router = DefaultRouter()
router.register("auth", UserViewSet, basename="auth")

urlpatterns = [
    path(
        "auth/login/",
        CustomTokenObtainPairView.as_view(
            throttle_classes=[AuthLoginThrottle],
        ),
        name="auth-login",
    ),
    path(
        "auth/token/refresh/",
        CustomTokenRefreshView.as_view(),
        name="auth-token-refresh",
    ),
    *router.urls,
]
