import logging

from django.db import connections
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

from .utils.responses import success_response

logger = logging.getLogger('kibegi')


@extend_schema(tags=['Health'])
class HealthCheckAPIView(APIView):
    """Simple health endpoint for uptime monitoring."""

    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(
        summary='Health check',
        description='Lightweight uptime endpoint for probes such as Uptime Kuma.',
        responses={200: dict, 503: dict},
    )
    def get(self, request):
        db_ok = True
        db_error = None

        try:
            connections['default'].cursor()
        except Exception as exc:
            db_ok = False
            db_error = str(exc)

        return success_response(
            message='healthy' if db_ok else 'unhealthy',
            data={
                'status': 'ok' if db_ok else 'error',
                'service': 'kibegi_api',
                'timestamp': timezone.now().isoformat(),
                'checks': {
                    'database': {
                        'status': 'ok' if db_ok else 'error',
                        'error': db_error,
                    }
                },
            },
            status_code=status.HTTP_200_OK if db_ok else status.HTTP_503_SERVICE_UNAVAILABLE,
        )
