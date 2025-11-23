import json
import logging
import time
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
        return None

    def process_response(self, request, response):
        try:
            duration = (time.perf_counter() - getattr(request, '_start_time', time.perf_counter())) * 1000
            user = getattr(request, 'user', None)
            user_obj = None
            user_identifier = 'anon'
            user_email = None
            
            if user and hasattr(user, 'email') and user.is_authenticated:
                user_obj = user
                user_identifier = getattr(user, 'email', str(user))
                user_email = user.email

            # attempt to extract JSON body safely
            body = None
            try:
                if request.content_type == 'application/json' and request.body:
                    payload = json.loads(request.body.decode('utf-8'))
                    body = _redact_sensitive(payload)
            except Exception:
                body = None

            # Log to file
            logger.info(
                "%(method)s %(path)s status=%(status)d user=%(user)s time_ms=%(time).1f body=%(body)s",
                {
                    'method': request.method,
                    'path': request.get_full_path(),
                    'status': getattr(response, 'status_code', 0),
                    'user': user_identifier,
                    'time': duration,
                    'body': json.dumps(body) if body is not None else ''
                }
            )
            
            # Save to database (async to avoid performance impact)
            try:
                from core.models import RequestLog
                RequestLog.objects.create(
                    method=request.method,
                    path=request.path[:500],  # Truncate if too long
                    full_path=request.get_full_path(),
                    user=user_obj,
                    user_email=user_email,
                    ip_address=_get_client_ip(request),
                    user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
                    status_code=getattr(response, 'status_code', 0),
                    response_time_ms=duration,
                    request_body=body,
                )
            except Exception as e:
                logger.error(f'Failed to save request log to database: {e}')
                
        except Exception:
            # do not let logging failures break responses
            logger.exception('RequestLoggingMiddleware failed')

        return response
