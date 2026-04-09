from hashlib import md5

from django.core.cache import cache
from rest_framework.response import Response


CACHE_TIMEOUTS = {
    "profile": 120,
    "classes": 120,
    "uploads": 90,
    "files": 90,
    "sharing": 90,
    "friends": 90,
    "schedule": 60,
    "notifications": 60,
    "storage": 60,
    "search": 45,
}


def _version_key(namespace: str) -> str:
    return f"api_cache_version:{namespace}"


def get_namespace_version(namespace: str) -> int:
    return cache.get(_version_key(namespace), 1)


def invalidate_cache_namespaces(*namespaces: str) -> None:
    for namespace in {ns for ns in namespaces if ns}:
        key = _version_key(namespace)
        cache.set(key, get_namespace_version(namespace) + 1, None)


def build_cache_key(request, *namespaces: str, extra: str = "") -> str:
    user_id = getattr(request.user, "id", "anon") if getattr(request, "user", None) else "anon"
    versions = "|".join(f"{ns}:{get_namespace_version(ns)}" for ns in namespaces if ns)
    raw_key = f"{request.method}|{request.get_full_path()}|{user_id}|{versions}|{extra}"
    return f"api-cache:{md5(raw_key.encode('utf-8')).hexdigest()}"


def get_cached_response(cache_key: str):
    cached = cache.get(cache_key)
    if cached is None:
        return None
    return Response(cached["data"], status=cached["status"])


def cache_response(cache_key: str, response, namespace: str):
    if getattr(response, "streaming", False):
        return response
    if response.status_code == 200:
        cache.set(
            cache_key,
            {"data": response.data, "status": response.status_code},
            CACHE_TIMEOUTS.get(namespace, 60),
        )
    return response
