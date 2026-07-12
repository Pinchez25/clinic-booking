from rest_framework.throttling import AnonRateThrottle


class AuthLoginThrottle(AnonRateThrottle):
    scope = "auth_login"
    rate = "10/min"


class AuthRegisterThrottle(AnonRateThrottle):
    scope = "auth_register"
    rate = "5/min"
