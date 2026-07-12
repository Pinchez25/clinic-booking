from .base import *

DEBUG = True
ALLOWED_HOSTS = ["*"]

CORS_ALLOW_ALL_ORIGINS = True

# Use HS256 with a simple secret in dev to avoid managing RSA keys locally

SIMPLE_JWT = {
    **SIMPLE_JWT,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,
    "VERIFYING_KEY": None,
}
