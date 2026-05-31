import logging

from drf_spectacular.utils import OpenApiExample, OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.core.utils.api_cache import build_cache_key, cache_response, get_cached_response
from apps.core.utils.responses import error_response, success_response

from .models import SearchHistory
from .serializers import (
    SearchHistorySerializer,
    SearchResponseSerializer,
    SearchSuggestionSerializer,
)
from .services import ALL_CATEGORIES, SearchService

logger = logging.getLogger('kibegi')


@extend_schema(tags=['Search'])
class SearchAPIView(APIView):
    """
    Global search across users, classes, files, friends, and the library.

    Results are permission-aware — users only see content they have access to.
    Each search is recorded in the user's search history.
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Global search",
        description="""
Search across all Kibegi apps in a single query.

**Categories:** `users`, `classes`, `files`, `friends`, `library`

**Examples:**
```
GET /api/v1/search/?q=calculus
GET /api/v1/search/?q=john&limit=5&categories=users,friends
GET /api/v1/search/?q=math&categories=library
```
        """,
        parameters=[
            OpenApiParameter('q', str, OpenApiParameter.QUERY, required=True,
                             description='Search query (min 2 characters)'),
            OpenApiParameter('limit', int, OpenApiParameter.QUERY, required=False,
                             description='Max results per category (default 10, max 50)'),
            OpenApiParameter('categories', str, OpenApiParameter.QUERY, required=False,
                             description='Comma-separated categories: users, classes, files, friends, library'),
        ],
        responses={200: SearchResponseSerializer, 400: dict, 401: dict},
        examples=[
            OpenApiExample(
                'Search for calculus',
                value={
                    'success': True,
                    'message': "Found 4 result(s) for 'calculus'",
                    'data': {
                        'query': 'calculus',
                        'total_results': 4,
                        'results': {
                            'library': [
                                {
                                    'id': 'uuid',
                                    'type': 'library',
                                    'title': 'Calculus Past Papers 2023',
                                    'file_type': 'past_paper',
                                    'subject': 'Mathematics',
                                    'is_featured': True,
                                    'view_count': 120,
                                    'download_count': 45,
                                }
                            ],
                        },
                        'counts': {'users': 0, 'classes': 0, 'files': 0, 'friends': 0, 'library': 4},
                    },
                },
            )
        ],
    )
    def get(self, request):
        cache_key = build_cache_key(request, 'search')
        cached = get_cached_response(cache_key)
        if cached is not None:
            return cached

        query = request.query_params.get('q', '').strip()
        limit_str = request.query_params.get('limit', '10')
        categories_str = request.query_params.get('categories', '')

        if not query:
            return error_response(
                message='Search query is required',
                errors={'q': ['This field is required.']},
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        if len(query) < 2:
            return error_response(
                message='Search query must be at least 2 characters',
                errors={'q': ['Ensure this field has at least 2 characters.']},
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        try:
            limit = max(1, min(50, int(limit_str)))
        except ValueError:
            limit = 10

        categories = None
        if categories_str:
            parsed = [c.strip().lower() for c in categories_str.split(',')]
            categories = [c for c in parsed if c in ALL_CATEGORIES] or None

        try:
            results = SearchService.search(
                query=query,
                user=request.user,
                limit=limit,
                categories=categories,
            )
        except Exception as exc:
            logger.error(f"Search error for {request.user.email}: {exc}", exc_info=True)
            return error_response(
                message='An error occurred while searching',
                errors={'detail': str(exc)},
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        response = success_response(
            message=f"Found {results['total_results']} result(s) for '{query}'",
            data=results,
        )
        return cache_response(cache_key, response, 'search')


@extend_schema(tags=['Search'])
class SearchSuggestionsAPIView(APIView):
    """
    Fast autocomplete suggestions.

    Returns up to 5 prefix-matched suggestions across users, classes, and
    library items. Does not record search history.
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Search suggestions (autocomplete)",
        parameters=[
            OpenApiParameter('q', str, OpenApiParameter.QUERY, required=True,
                             description='Prefix to autocomplete (min 1 character)'),
            OpenApiParameter('limit', int, OpenApiParameter.QUERY, required=False,
                             description='Max suggestions (default 5, max 10)'),
        ],
        responses={200: SearchSuggestionSerializer(many=True), 400: dict},
    )
    def get(self, request):
        query = request.query_params.get('q', '').strip()

        if not query:
            return error_response(
                message='Query is required',
                errors={'q': ['This field is required.']},
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        try:
            limit = max(1, min(10, int(request.query_params.get('limit', '5'))))
        except ValueError:
            limit = 5

        suggestions = SearchService.suggestions(query=query, user=request.user, limit=limit)
        return success_response(
            message=f'{len(suggestions)} suggestion(s)',
            data=suggestions,
        )


@extend_schema(tags=['Search'])
class SearchHistoryAPIView(APIView):
    """
    User's personal search history.

    GET  — list the 20 most recent searches.
    DELETE — clear all search history for the current user.
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Get search history",
        responses={200: SearchHistorySerializer(many=True)},
    )
    def get(self, request):
        history = SearchHistory.objects.filter(user=request.user)[:20]
        data = SearchHistorySerializer(history, many=True).data
        return success_response(
            message=f'{len(data)} recent search(es)',
            data=list(data),
        )

    @extend_schema(
        summary="Clear search history",
        responses={200: dict},
    )
    def delete(self, request):
        deleted_count, _ = SearchHistory.objects.filter(user=request.user).delete()
        return success_response(message=f'Cleared {deleted_count} search record(s)')
