"""
Health check views with Datadog metrics integration.

This module provides health check endpoints that report availability metrics to Datadog.
"""

import logging

from datadog import statsd
from django.conf import settings
from django.db import connection
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response

logger = logging.getLogger(__name__)


def check_database() -> tuple[bool, str]:
    """
    Check database connectivity.

    Returns:
        Tuple of (is_healthy, message)
    """
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        return True, "Database connection successful"
    except Exception as e:
        logger.error("Database health check failed", extra={"error": str(e)})
        return False, f"Database connection failed: {str(e)}"


@api_view(["GET"])
@permission_classes([AllowAny])
def readiness_check(request: Request) -> Response:
    """
    Readiness probe endpoint that checks if the service can accept traffic.

    This endpoint:
    - Checks database connectivity
    - Reports availability to Datadog as a gauge metric (1=available, 0=unavailable)
    - Returns 200 if healthy, 503 if not ready
    """
    checks = {
        "database": check_database(),
    }

    is_ready = all(check[0] for check in checks.values())
    status_code = 200 if is_ready else 503

    # Report availability to Datadog as a gauge metric
    # 1 = service is available, 0 = service is unavailable
    availability_value = 1 if is_ready else 0

    try:
        statsd.gauge(
            "firetower.ready",
            availability_value,
            tags=[
                f"environment:{getattr(settings, 'DJANGO_ENV', 'dev')}",
                f"status:{'ready' if is_ready else 'not_ready'}",
            ],
        )
        logger.info(
            "Readiness check completed",
            extra={
                "is_ready": is_ready,
                "availability_metric": availability_value,
            },
        )
    except Exception as e:
        logger.error(
            "Failed to send Datadog metric",
            extra={"error": str(e)},
        )

    response_data = {
        "status": "ready" if is_ready else "not_ready",
        "checks": {
            name: {
                "status": "pass" if passed else "fail",
                "message": message,
            }
            for name, (passed, message) in checks.items()
        },
    }

    return Response(response_data, status=status_code)


@api_view(["GET"])
@permission_classes([AllowAny])
def liveness_check(request: Request) -> Response:
    """
    Liveness probe endpoint that checks if the service is running.

    This is a simple check that returns 200 if the application is responsive.
    It does not check external dependencies.
    """
    return Response({"status": "alive"}, status=200)
