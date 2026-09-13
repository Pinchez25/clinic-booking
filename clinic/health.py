from django.db import connection
from django.db.utils import DatabaseError
from django.http import JsonResponse


def liveness_check(request):
    return JsonResponse({"status": "ok"})


def readiness_check(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except DatabaseError:
        return JsonResponse(
            {"status": "unavailable", "checks": {"database": "unavailable"}},
            status=503,
        )

    return JsonResponse({"status": "ok", "checks": {"database": "ok"}})


def health_check(request):
    return liveness_check(request)
