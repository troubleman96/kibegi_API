from rest_framework import serializers
from django.utils import timezone
from .models import Assignment, AssignmentSubmission
from apps.authentication.serializers import UserSummarySerializer


class AssignmentSerializer(serializers.ModelSerializer):
    created_by = UserSummarySerializer(read_only=True)
    submission_count = serializers.SerializerMethodField()
    my_submission_status = serializers.SerializerMethodField()

    class Meta:
        model = Assignment
        fields = [
            'id', 'assignment_code', 'class_obj', 'created_by',
            'title', 'description', 'instructions', 'attachment',
            'due_date', 'max_score', 'is_active', 'allow_late_submission',
            'submission_count', 'my_submission_status',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'assignment_code', 'created_by', 'created_at', 'updated_at']

    def get_submission_count(self, obj):
        return obj.submissions.filter(status__in=['submitted', 'graded', 'returned']).count()

    def get_my_submission_status(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return None
        sub = obj.submissions.filter(student=request.user).first()
        return sub.status if sub else None


class AssignmentCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Assignment
        fields = [
            'class_obj', 'title', 'description', 'instructions',
            'attachment', 'due_date', 'max_score', 'is_active', 'allow_late_submission',
        ]

    def validate_class_obj(self, value):
        request = self.context['request']
        from apps.classes.models import Membership
        if not Membership.objects.filter(class_obj=value, user=request.user, role='lecturer').exists():
            raise serializers.ValidationError("You are not a lecturer of this class.")
        return value


class SubmissionSerializer(serializers.ModelSerializer):
    student = UserSummarySerializer(read_only=True)
    graded_by = UserSummarySerializer(read_only=True)
    assignment_title = serializers.CharField(source='assignment.title', read_only=True)
    assignment_code = serializers.CharField(source='assignment.assignment_code', read_only=True)
    is_late = serializers.BooleanField(read_only=True)

    class Meta:
        model = AssignmentSubmission
        fields = [
            'id', 'assignment', 'assignment_title', 'assignment_code',
            'student', 'response_text', 'attachment',
            'status', 'submitted_at', 'is_late',
            'score', 'feedback', 'graded_by', 'graded_at',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'student', 'submitted_at', 'is_late',
            'graded_by', 'graded_at', 'created_at', 'updated_at',
        ]


class SubmissionSaveSerializer(serializers.ModelSerializer):
    """Used by students to save draft or submit."""

    class Meta:
        model = AssignmentSubmission
        fields = ['response_text', 'attachment', 'status']

    def validate_status(self, value):
        if value not in (AssignmentSubmission.STATUS_DRAFT, AssignmentSubmission.STATUS_SUBMITTED):
            raise serializers.ValidationError("Students may only set status to 'draft' or 'submitted'.")
        return value

    def validate(self, attrs):
        assignment = self.context['assignment']
        if attrs.get('status') == AssignmentSubmission.STATUS_SUBMITTED:
            if not assignment.allow_late_submission and assignment.due_date:
                if timezone.now() > assignment.due_date:
                    raise serializers.ValidationError("The submission deadline has passed.")
        return attrs


class GradeSubmissionSerializer(serializers.Serializer):
    score = serializers.IntegerField(min_value=0)
    feedback = serializers.CharField(allow_blank=True, default='')
    action = serializers.ChoiceField(choices=['grade', 'return'])

    def validate(self, attrs):
        assignment = self.context['assignment']
        if attrs['score'] > assignment.max_score:
            raise serializers.ValidationError(
                f"Score cannot exceed the assignment's max score of {assignment.max_score}."
            )
        return attrs
