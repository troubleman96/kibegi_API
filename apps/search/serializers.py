from rest_framework import serializers


class UserSearchResultSerializer(serializers.Serializer):
    id = serializers.CharField(read_only=True)
    type = serializers.CharField(read_only=True)
    email = serializers.EmailField(read_only=True)
    full_name = serializers.CharField(read_only=True)
    user_type = serializers.CharField(read_only=True)
    profile_image = serializers.CharField(read_only=True, allow_null=True)
    profile_image_url = serializers.CharField(read_only=True, allow_null=True)


class ClassSearchResultSerializer(serializers.Serializer):
    id = serializers.CharField(read_only=True)
    type = serializers.CharField(read_only=True)
    name = serializers.CharField(read_only=True)
    description = serializers.CharField(read_only=True)
    class_code = serializers.CharField(read_only=True)
    is_verified = serializers.BooleanField(read_only=True)
    member_count = serializers.IntegerField(read_only=True)
    creator_name = serializers.CharField(read_only=True)


class FileSearchResultSerializer(serializers.Serializer):
    id = serializers.CharField(read_only=True)
    type = serializers.CharField(read_only=True)
    file_name = serializers.CharField(read_only=True)
    file_type = serializers.CharField(read_only=True)
    file_size = serializers.IntegerField(read_only=True)
    file_code = serializers.CharField(read_only=True)
    uploader_name = serializers.CharField(read_only=True)
    class_name = serializers.CharField(read_only=True, allow_null=True)
    is_own = serializers.BooleanField(read_only=True)
    created_at = serializers.CharField(read_only=True)


class FriendSearchResultSerializer(serializers.Serializer):
    id = serializers.CharField(read_only=True)
    type = serializers.CharField(read_only=True)
    friend_id = serializers.CharField(read_only=True)
    friend_email = serializers.EmailField(read_only=True)
    friend_name = serializers.CharField(read_only=True)
    friend_type = serializers.CharField(read_only=True)
    friend_profile_image = serializers.CharField(read_only=True, allow_null=True)
    friend_profile_image_url = serializers.CharField(read_only=True, allow_null=True)
    nickname = serializers.CharField(read_only=True, allow_blank=True)
    accepted_at = serializers.CharField(read_only=True, allow_null=True)


class LibrarySearchResultSerializer(serializers.Serializer):
    id = serializers.CharField(read_only=True)
    type = serializers.CharField(read_only=True)
    item_code = serializers.CharField(read_only=True)
    title = serializers.CharField(read_only=True)
    description = serializers.CharField(read_only=True, allow_blank=True)
    file_type = serializers.CharField(read_only=True)
    subject = serializers.CharField(read_only=True, allow_blank=True)
    course_code = serializers.CharField(read_only=True, allow_blank=True)
    author_name = serializers.CharField(read_only=True, allow_blank=True)
    category_name = serializers.CharField(read_only=True, allow_null=True)
    is_featured = serializers.BooleanField(read_only=True)
    view_count = serializers.IntegerField(read_only=True)
    download_count = serializers.IntegerField(read_only=True)


class SearchResultsSerializer(serializers.Serializer):
    users = UserSearchResultSerializer(many=True, required=False)
    classes = ClassSearchResultSerializer(many=True, required=False)
    files = FileSearchResultSerializer(many=True, required=False)
    friends = FriendSearchResultSerializer(many=True, required=False)
    library = LibrarySearchResultSerializer(many=True, required=False)


class SearchCountsSerializer(serializers.Serializer):
    users = serializers.IntegerField(required=False, default=0)
    classes = serializers.IntegerField(required=False, default=0)
    files = serializers.IntegerField(required=False, default=0)
    friends = serializers.IntegerField(required=False, default=0)
    library = serializers.IntegerField(required=False, default=0)


class SearchResponseSerializer(serializers.Serializer):
    query = serializers.CharField(read_only=True)
    total_results = serializers.IntegerField(read_only=True)
    results = SearchResultsSerializer(read_only=True)
    counts = SearchCountsSerializer(read_only=True)


class SearchSuggestionSerializer(serializers.Serializer):
    type = serializers.CharField(read_only=True)
    label = serializers.CharField(read_only=True)
    sub = serializers.CharField(read_only=True)


class SearchHistorySerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    query = serializers.CharField(read_only=True)
    result_count = serializers.IntegerField(read_only=True)
    categories_searched = serializers.ListField(child=serializers.CharField(), read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
