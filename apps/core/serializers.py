"""
Core serializers for the Kibegi API.

This module contains serializers for cross-cutting functionality
including global search results.
"""

from rest_framework import serializers


# ============================================================================
# Search Result Serializers
# ============================================================================

class UserSearchResultSerializer(serializers.Serializer):
    """Serializer for user search results."""
    id = serializers.CharField(read_only=True)
    type = serializers.CharField(read_only=True, default="user")
    email = serializers.EmailField(read_only=True)
    full_name = serializers.CharField(read_only=True)
    user_type = serializers.CharField(read_only=True)
    profile_image = serializers.CharField(read_only=True, allow_null=True)
    profile_image_url = serializers.CharField(read_only=True, allow_null=True)


class ClassSearchResultSerializer(serializers.Serializer):
    """Serializer for class search results."""
    id = serializers.CharField(read_only=True)
    type = serializers.CharField(read_only=True, default="class")
    name = serializers.CharField(read_only=True)
    description = serializers.CharField(read_only=True)
    class_code = serializers.CharField(read_only=True)
    is_verified = serializers.BooleanField(read_only=True)
    member_count = serializers.IntegerField(read_only=True)
    creator_name = serializers.CharField(read_only=True)


class FileSearchResultSerializer(serializers.Serializer):
    """Serializer for file/upload search results."""
    id = serializers.CharField(read_only=True)
    type = serializers.CharField(read_only=True, default="file")
    file_name = serializers.CharField(read_only=True)
    file_type = serializers.CharField(read_only=True)
    file_size = serializers.IntegerField(read_only=True)
    file_code = serializers.CharField(read_only=True)
    uploader_name = serializers.CharField(read_only=True)
    class_name = serializers.CharField(read_only=True, allow_null=True)
    is_own = serializers.BooleanField(read_only=True)
    created_at = serializers.CharField(read_only=True)


class FriendSearchResultSerializer(serializers.Serializer):
    """Serializer for friend search results."""
    id = serializers.CharField(read_only=True)
    type = serializers.CharField(read_only=True, default="friend")
    friend_id = serializers.CharField(read_only=True)
    friend_email = serializers.EmailField(read_only=True)
    friend_name = serializers.CharField(read_only=True)
    friend_type = serializers.CharField(read_only=True)
    friend_profile_image = serializers.CharField(read_only=True, allow_null=True)
    friend_profile_image_url = serializers.CharField(read_only=True, allow_null=True)
    nickname = serializers.CharField(read_only=True, allow_blank=True)
    accepted_at = serializers.CharField(read_only=True, allow_null=True)


class SearchResultsSerializer(serializers.Serializer):
    """
    Serializer for categorized search results.
    
    Contains results from all searchable categories:
    - users: Matching users
    - classes: Matching classes
    - files: Matching files/uploads
    - friends: Matching friends
    """
    users = UserSearchResultSerializer(many=True, required=False)
    classes = ClassSearchResultSerializer(many=True, required=False)
    files = FileSearchResultSerializer(many=True, required=False)
    friends = FriendSearchResultSerializer(many=True, required=False)


class SearchCountsSerializer(serializers.Serializer):
    """Serializer for result counts per category."""
    users = serializers.IntegerField(required=False, default=0)
    classes = serializers.IntegerField(required=False, default=0)
    files = serializers.IntegerField(required=False, default=0)
    friends = serializers.IntegerField(required=False, default=0)


class GlobalSearchResponseSerializer(serializers.Serializer):
    """
    Serializer for the complete global search response.
    
    Example response:
    {
        "query": "john",
        "total_results": 15,
        "results": {
            "users": [...],
            "classes": [...],
            "files": [...],
            "friends": [...]
        },
        "counts": {
            "users": 5,
            "classes": 3,
            "files": 4,
            "friends": 3
        }
    }
    """
    query = serializers.CharField(read_only=True, help_text="The search query")
    total_results = serializers.IntegerField(read_only=True, help_text="Total number of results across all categories")
    results = SearchResultsSerializer(read_only=True, help_text="Categorized search results")
    counts = SearchCountsSerializer(read_only=True, help_text="Result counts per category")
    error = serializers.CharField(read_only=True, required=False, allow_null=True, help_text="Error message if any")


class SearchQuerySerializer(serializers.Serializer):
    """
    Serializer for validating search query parameters.
    
    Used for input validation in the search endpoint.
    """
    q = serializers.CharField(
        min_length=2,
        max_length=100,
        help_text="Search query (min 2 characters, max 100)"
    )
    limit = serializers.IntegerField(
        min_value=1,
        max_value=50,
        default=10,
        required=False,
        help_text="Maximum results per category (default: 10, max: 50)"
    )
    categories = serializers.ListField(
        child=serializers.ChoiceField(choices=['users', 'classes', 'files', 'friends']),
        required=False,
        help_text="Categories to search. Leave empty to search all. Options: users, classes, files, friends"
    )
