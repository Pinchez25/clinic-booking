from django.urls import path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .throttles import AuthLoginThrottle
from .views import UserViewSet

router = DefaultRouter()
router.register("auth", UserViewSet, basename="auth")

urlpatterns = [
    path(
        "auth/login/",
        TokenObtainPairView.as_view(throttle_classes=[AuthLoginThrottle]),
        name="auth-login",
    ),
    path(
        "auth/token/refresh/",
        TokenRefreshView.as_view(),
        name="auth-token-refresh",
    ),
    *router.urls,
]
