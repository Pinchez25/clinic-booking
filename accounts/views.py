import logging

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .serializers import (
    CustomTokenObtainPairSerializer,
    RegisterSerializer,
    UserSerializer,
)
from .throttles import AuthRegisterThrottle

logger = logging.getLogger("users.auth")


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer

    @extend_schema(
        summary="Login",
        description="Authenticate a user and return JWT access and refresh tokens.",
        tags=["Authentication"],
        responses={200: OpenApiResponse(description="JWT tokens issued successfully")},
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


@extend_schema(
    summary="Refresh token",
    description="Get a new access token using a refresh token.",
    tags=["Authentication"],
    responses={200: OpenApiResponse(description="New access token issued successfully")},
)
class CustomTokenRefreshView(TokenRefreshView):
    pass


@extend_schema(tags=["Authentication"])
class UserViewSet(GenericViewSet):
    serializer_class = UserSerializer

    @extend_schema(
        summary="Register a new patient",
        description="Create a new account for a patient and return JWT tokens.",
        request=RegisterSerializer,
        responses={
            201: OpenApiResponse(
                description="Account created successfully.",
            )
        },
    )
    @action(
        detail=False,
        methods=["post"],
        url_path="register",
        authentication_classes=[],
        permission_classes=[AllowAny],
        throttle_classes=[AuthRegisterThrottle],
        serializer_class=RegisterSerializer,
    )
    def register(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.save()

        logger.info("New patient registered: user=%s", user.id)

        refresh = CustomTokenObtainPairSerializer.get_token(user)

        return Response(
            {
                "user": UserSerializer(user).data,
                "access": str(refresh.access_token),
                "refresh": str(refresh),
            },
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        summary="Logout",
        description="Blacklist a refresh token to revoke the current session.",
        request={
            "application/json": {
                "type": "object",
                "properties": {"refresh": {"type": "string"}},
                "required": ["refresh"],
            }
        },
        responses={204: None},
    )
    @action(detail=False, methods=["post"], url_path="logout")
    def logout(self, request):
        refresh_token = request.data.get("refresh")

        if not refresh_token:
            return Response(
                {"detail": "Refresh token is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            RefreshToken(refresh_token).blacklist()

        except TokenError:
            logger.warning("Logout failed due to an invalid refresh token.")

            return Response(
                {"detail": "Invalid refresh token."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        logger.info("User logged out: user=%s", request.user.id)

        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        summary="Current user profile",
        description="Return the authenticated user's profile information.",
        responses={200: UserSerializer},
    )
    @action(detail=False, methods=["get"], url_path="me")
    def me(self, request):
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)
