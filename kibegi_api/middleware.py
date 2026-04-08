import json
import logging
import time
import traceback

from django.http import QueryDict
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger('kibegi')


def _redact_sensitive(data):
    """Redact known sensitive fields in a dict-like object."""
    if not isinstance(data, dict):
        return data
    sensitive_keys = {'password', 'new_password', 'confirm_password', 'current_password', 'otp', 'refresh', 'token'}
    redacted = {}
    for k, v in data.items():
        if k.lower() in sensitive_keys:
            redacted[k] = '*****'
        else:
            # do not attempt deep redact for complex nested structures
            redacted[k] = v
    return redacted


def _should_log_request(request):
    """Log API traffic and auth compatibility endpoints."""
    path = getattr(request, 'path', '') or ''
    return path.startswith('/api/') or path in {'/login/', '/register/'}


def _extract_request_payload(request):
    """Extract request payload safely across JSON, form, and query requests."""
    try:
        if request.method in {'GET', 'DELETE', 'HEAD', 'OPTIONS'}:
            query_params = request.GET.dict() if isinstance(request.GET, QueryDict) else {}
            return _redact_sensitive(query_params) or None

        if request.content_type == 'application/json' and request.body:
            payload = json.loads(request.body.decode('utf-8'))
            return _redact_sensitive(payload)

        if request.POST:
            return _redact_sensitive(request.POST.dict())
    except Exception:
        return None

    return None


def _get_client_ip(request):
    """Extract client IP from request."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


class RequestLoggingMiddleware(MiddlewareMixin):
    """Middleware that logs basic request/response info for each HTTP request.

    Logs: timestamp, method, path, user (email or 'anon'), status_code, duration_ms, body (redacted)
    Saves logs to both file and database.
    """

    def process_request(self, request):
        request._start_time = time.perf_counter()
        request._request_payload = _extract_request_payload(request)
        request._request_logged = False
        return None

    def _save_request_log(self, request, status_code, error_message=None):
        duration = (time.perf_counter() - getattr(request, '_start_time', time.perf_counter())) * 1000
        user = getattr(request, 'user', None)
        user_obj = None
        user_identifier = 'anon'
        user_email = None

        if user and hasattr(user, 'email') and user.is_authenticated:
            user_obj = user
            user_identifier = getattr(user, 'email', str(user))
            user_email = user.email

        body = getattr(request, '_request_payload', None)

        logger.info(
            "%(method)s %(path)s status=%(status)d user=%(user)s time_ms=%(time).1f body=%(body)s error=%(error)s",
            {
                'method': request.method,
                'path': request.get_full_path(),
                'status': status_code,
                'user': user_identifier,
                'time': duration,
                'body': json.dumps(body) if body is not None else '',
                'error': error_message or '',
            }
        )

        from apps.core.models import RequestLog

        RequestLog.objects.create(
            method=request.method,
            path=request.path[:500],
            full_path=request.get_full_path(),
            user=user_obj,
            user_email=user_email,
            ip_address=_get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
            status_code=status_code,
            response_time_ms=duration,
            request_body=body,
            error_message=error_message[:5000] if error_message else None,
        )
        request._request_logged = True

    def process_response(self, request, response):
        try:
            if _should_log_request(request) and not getattr(request, '_request_logged', False):
                self._save_request_log(
                    request=request,
                    status_code=getattr(response, 'status_code', 0),
                )
        except Exception:
            # do not let logging failures break responses
            logger.exception('RequestLoggingMiddleware failed')

        return response

    def process_exception(self, request, exception):
        try:
            if _should_log_request(request) and not getattr(request, '_request_logged', False):
                error_message = ''.join(
                    traceback.format_exception_only(type(exception), exception)
                ).strip()
                self._save_request_log(
                    request=request,
                    status_code=500,
                    error_message=error_message,
                )
        except Exception:
            logger.exception('RequestLoggingMiddleware exception logging failed')

        return None
