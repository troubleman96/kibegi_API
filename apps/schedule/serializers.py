from rest_framework import serializers

from .models import ScheduleCalendar, ScheduleEvent


class ScheduleEventSerializer(serializers.ModelSerializer):
    """Serializer used for reading and writing schedule events."""

    class Meta:
        model = ScheduleEvent
        fields = [
            "id",
            "calendar",
            "title",
            "description",
            "location",
            "start_at",
            "end_at",
            "event_type",
            "recurrence",
            "days",
            "reminder_minutes",
            "source",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "calendar", "source", "created_at", "updated_at"]

    def validate(self, attrs):
        # During update we merge the missing values so validation still sees the
        # effective start/end pair and recurrence configuration.
        instance = getattr(self, "instance", None)
        start_at = attrs.get("start_at", getattr(instance, "start_at", None))
        end_at = attrs.get("end_at", getattr(instance, "end_at", None))
        recurrence = attrs.get("recurrence", getattr(instance, "recurrence", ScheduleEvent.RECURRENCE_NONE))
        days = attrs.get("days", getattr(instance, "days", None))

        if start_at and end_at and end_at <= start_at:
            raise serializers.ValidationError({"end_at": "End time must be after start time."})

        if recurrence == ScheduleEvent.RECURRENCE_WEEKLY and not days:
            raise serializers.ValidationError({"days": "Weekly recurring events must include at least one day."})

        return attrs


class ScheduleCalendarSerializer(serializers.ModelSerializer):
    """Calendar serializer with event counts for list/detail screens."""

    event_count = serializers.SerializerMethodField()

    class Meta:
        model = ScheduleCalendar
        fields = [
            "id",
            "name",
            "calendar_type",
            "description",
            "is_public_sync",
            "calendar_code",
            "event_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "calendar_type", "calendar_code", "event_count", "created_at", "updated_at"]

    def get_event_count(self, obj):
        # Use a prefetched/annotated count when available, otherwise fall back
        # to a direct count so update responses remain stable.
        return getattr(obj, "event_count", obj.events.count())


class ScheduleCalendarDetailSerializer(ScheduleCalendarSerializer):
    """Calendar detail serializer that includes nested events for convenience."""

    events = ScheduleEventSerializer(many=True, read_only=True)

    class Meta(ScheduleCalendarSerializer.Meta):
        fields = ScheduleCalendarSerializer.Meta.fields + ["events"]


class ScheduleShareSerializer(serializers.Serializer):
    """Serializer for tokenized schedule share info."""

    calendar_id = serializers.CharField(read_only=True)
    calendar_type = serializers.CharField(read_only=True)
    calendar_code = serializers.CharField(read_only=True)
    subscribe_url = serializers.URLField(read_only=True)
    download_url = serializers.URLField(read_only=True)
    webcal_url = serializers.CharField(read_only=True)
    subscription_page_url = serializers.URLField(read_only=True)
    frontend_subscription_url = serializers.URLField(read_only=True, allow_null=True)
    code_lookup_url = serializers.URLField(read_only=True)


class PublicScheduleInfoSerializer(serializers.Serializer):
    """Public-facing calendar metadata returned without authentication."""

    name = serializers.CharField(read_only=True)
    calendar_type = serializers.CharField(read_only=True)
    description = serializers.CharField(read_only=True, allow_null=True)
    calendar_code = serializers.CharField(read_only=True)
    event_count = serializers.IntegerField(read_only=True)
    subscribe_url = serializers.URLField(read_only=True)
    download_url = serializers.URLField(read_only=True)
    webcal_url = serializers.CharField(read_only=True)
    subscription_page_url = serializers.URLField(read_only=True)
    frontend_subscription_url = serializers.URLField(read_only=True, allow_null=True)
