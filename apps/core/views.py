"""
Core views for the Kibegi API.

This module contains cross-cutting views including the global search endpoint.
"""

import logging
from django.db import connections
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiExample
from drf_spectacular.types import OpenApiTypes

from .services import GlobalSearchService
from .serializers import GlobalSearchResponseSerializer, SearchQuerySerializer
from .utils.responses import success_response, error_response

logger = logging.getLogger('kibegi')


@extend_schema(tags=['Health'])
class HealthCheckAPIView(APIView):
    """Simple health endpoint for uptime monitoring."""

    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(
        summary="Health check",
        description="Lightweight uptime endpoint for probes such as Uptime Kuma.",
        responses={200: dict, 503: dict},
    )
    def get(self, request):
        db_ok = True
        db_error = None

        try:
            connections["default"].cursor()
        except Exception as exc:
            db_ok = False
            db_error = str(exc)

        status_code = status.HTTP_200_OK if db_ok else status.HTTP_503_SERVICE_UNAVAILABLE

        return success_response(
            message="healthy" if db_ok else "unhealthy",
            data={
                "status": "ok" if db_ok else "error",
                "service": "kibegi_api",
                "timestamp": timezone.now().isoformat(),
                "checks": {
                    "database": {
                        "status": "ok" if db_ok else "error",
                        "error": db_error,
                    }
                },
            },
            status_code=status_code,
        )


@extend_schema(tags=['Search'])
class GlobalSearchAPIView(APIView):
    """
    Global search across all Kibegi apps.
    
    Search through users, classes, files, and friends in a single query.
    Results are categorized and permission-aware (users only see what they have access to).
    
    **Searchable Categories:**
    - **users**: Search by email or full name
    - **classes**: Search by class name, description, or code
    - **files**: Search by filename (own files + accepted shared files)
    - **friends**: Search friends by name or email
    
    **Features:**
    - Minimum 2 character query
    - Configurable limit per category (default: 10, max: 50)
    - Filter by specific categories
    - Permission-aware results
    """
    
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        summary="Global search",
        description="""
Search across all Kibegi apps in a single query.

**Query Parameters:**
- `q` (required): Search query (min 2 characters)
- `limit` (optional): Max results per category (default: 10, max: 50)
- `categories` (optional): Comma-separated list of categories to search.
  Options: `users`, `classes`, `files`, `friends`. Leave empty to search all.

**Example:**
```
GET /api/v1/search/?q=john&limit=5&categories=users,friends
```

**Permission Notes:**
- Users: Shows all active users except yourself
- Classes: Shows classes you're a member of OR public classes
- Files: Shows your uploads OR files shared with you (accepted)
- Friends: Shows only accepted friendships
        """,
        parameters=[
            OpenApiParameter(
                name='q',
                description='Search query (min 2 characters)',
                required=True,
                type=str,
                location=OpenApiParameter.QUERY
            ),
            OpenApiParameter(
                name='limit',
                description='Maximum results per category (default: 10, max: 50)',
                required=False,
                type=int,
                location=OpenApiParameter.QUERY
            ),
            OpenApiParameter(
                name='categories',
                description='Comma-separated categories to search: users, classes, files, friends',
                required=False,
                type=str,
                location=OpenApiParameter.QUERY
            ),
        ],
        responses={
            200: GlobalSearchResponseSerializer,
            400: dict,
            401: dict,
        },
        examples=[
            OpenApiExample(
                'Successful Search',
                summary='Search results for "john"',
                value={
                    "success": True,
                    "message": "Found 8 results for 'john'",
                    "data": {
                        "query": "john",
                        "total_results": 8,
                        "results": {
                            "users": [
                                {
                                    "id": "uuid-1",
                                    "type": "user",
                                    "email": "john@example.com",
                                    "full_name": "John Doe",
                                    "user_type": "student"
                                }
                            ],
                            "classes": [
                                {
                                    "id": "uuid-2",
                                    "type": "class",
                                    "name": "John's Study Group",
                                    "description": "A study group...",
                                    "class_code": "ABC123",
                                    "is_verified": False,
                                    "member_count": 5,
                                    "creator_name": "John Doe"
                                }
                            ],
                            "files": [
                                {
                                    "id": "uuid-3",
                                    "type": "file",
                                    "file_name": "john_notes.pdf",
                                    "file_type": "document",
                                    "file_size": 1024000,
                                    "file_code": "XYZ789",
                                    "uploader_name": "John Doe",
                                    "class_name": "CS101",
                                    "is_own": True,
                                    "created_at": "2025-11-25T10:00:00Z"
                                }
                            ],
                            "friends": [
                                {
                                    "id": "15",
                                    "type": "friend",
                                    "friend_id": "uuid-4",
                                    "friend_email": "johnny@example.com",
                                    "friend_name": "Johnny Smith",
                                    "friend_type": "lecturer",
                                    "nickname": "Johnny Boy",
                                    "accepted_at": "2025-11-20T15:30:00Z"
                                }
                            ]
                        },
                        "counts": {
                            "users": 1,
                            "classes": 1,
                            "files": 1,
                            "friends": 1
                        }
                    }
                }
            ),
            OpenApiExample(
                'Query Too Short',
                summary='Error when query is too short',
                value={
                    "success": False,
                    "message": "Search query must be at least 2 characters",
                    "data": None,
                    "errors": {"q": ["Ensure this field has at least 2 characters."]}
                }
            )
        ]
    )
    def get(self, request):
        """
        Perform a global search across all apps.
        
        Returns categorized results from users, classes, files, and friends.
        """
        # Get and validate query parameters
        query = request.query_params.get('q', '').strip()
        limit_str = request.query_params.get('limit', '10')
        categories_str = request.query_params.get('categories', '')
        
        logger.debug(f"Search request from {request.user.email}: q='{query}', limit={limit_str}, categories={categories_str}")
        
        # Validate query
        if not query:
            return error_response(
                message="Search query is required",
                errors={"q": ["This field is required."]},
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        if len(query) < 2:
            return error_response(
                message="Search query must be at least 2 characters",
                errors={"q": ["Ensure this field has at least 2 characters."]},
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate limit
        try:
            limit = int(limit_str)
            limit = max(1, min(50, limit))  # Clamp between 1 and 50
        except ValueError:
            limit = 10
        
        # Parse categories
        categories = None
        if categories_str:
            valid_categories = ['users', 'classes', 'files', 'friends']
            categories = [c.strip().lower() for c in categories_str.split(',')]
            categories = [c for c in categories if c in valid_categories]
            if not categories:
                categories = None  # Search all if none valid
        
        # Perform search
        try:
            results = GlobalSearchService.search(
                query=query,
                user=request.user,
                limit=limit,
                categories=categories
            )
            
            # Check for error in results
            if results.get('error'):
                return error_response(
                    message=results['error'],
                    status_code=status.HTTP_400_BAD_REQUEST
                )
            
            logger.info(f"Search completed for {request.user.email}: '{query}' -> {results['total_results']} results")
            
            return success_response(
                message=f"Found {results['total_results']} result(s) for '{query}'",
                data=results
            )
            
        except Exception as e:
            logger.error(f"Search error for {request.user.email}: {str(e)}", exc_info=True)
            return error_response(
                message="An error occurred while searching",
                errors={"detail": str(e)},
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
