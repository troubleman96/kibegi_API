import logging
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from drf_spectacular.utils import extend_schema

from apps.core.utils.responses import success_response, error_response
from apps.notifications.services import NotificationService
from .models import Assignment, AssignmentSubmission
from .serializers import (
    AssignmentSerializer,
    AssignmentCreateSerializer,
    SubmissionSerializer,
    SubmissionSaveSerializer,
    GradeSubmissionSerializer,
)

logger = logging.getLogger('kibegi')


def _is_class_lecturer(user, class_obj):
    from apps.classes.models import Membership
    return Membership.objects.filter(class_obj=class_obj, user=user, role='lecturer').exists()


def _is_class_member(user, class_obj):
    from apps.classes.models import Membership
    return Membership.objects.filter(class_obj=class_obj, user=user).exists()


@extend_schema(tags=['Assignments'])
class AssignmentListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(summary="List assignments for a class", responses={200: AssignmentSerializer(many=True)})
    def get(self, request, class_id):
        if not _is_class_member(request.user, class_id):
            return error_response(_("You are not a member of this class."), status.HTTP_403_FORBIDDEN)
        qs = Assignment.objects.filter(class_obj_id=class_id)
        if not _is_class_lecturer(request.user, class_id):
            qs = qs.filter(is_active=True)
        serializer = AssignmentSerializer(qs, many=True, context={'request': request})
        return success_response(data=serializer.data)

    @extend_schema(summary="Create an assignment (lecturer only)", request=AssignmentCreateSerializer, responses={201: AssignmentSerializer})
    def post(self, request, class_id):
        if not _is_class_lecturer(request.user, class_id):
            return error_response(_("Only lecturers can create assignments."), status.HTTP_403_FORBIDDEN)
        data = request.data.copy()
        data['class_obj'] = str(class_id)
        serializer = AssignmentCreateSerializer(data=data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        assignment = serializer.save(created_by=request.user)

        # Notify class members
        _notify_assignment_created(assignment, request.user)

        out = AssignmentSerializer(assignment, context={'request': request})
        return success_response(data=out.data, status_code=status.HTTP_201_CREATED)


@extend_schema(tags=['Assignments'])
class AssignmentDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_assignment(self, assignment_id, user):
        try:
            a = Assignment.objects.get(id=assignment_id)
        except Assignment.DoesNotExist:
            return None, error_response(_("Assignment not found."), status.HTTP_404_NOT_FOUND)
        if not _is_class_member(user, a.class_obj_id):
            return None, error_response(_("You are not a member of this class."), status.HTTP_403_FORBIDDEN)
        return a, None

    @extend_schema(summary="Get assignment details", responses={200: AssignmentSerializer})
    def get(self, request, assignment_id):
        assignment, err = self._get_assignment(assignment_id, request.user)
        if err:
            return err
        return success_response(data=AssignmentSerializer(assignment, context={'request': request}).data)

    @extend_schema(summary="Update an assignment (lecturer only)", request=AssignmentCreateSerializer, responses={200: AssignmentSerializer})
    def patch(self, request, assignment_id):
        assignment, err = self._get_assignment(assignment_id, request.user)
        if err:
            return err
        if not _is_class_lecturer(request.user, assignment.class_obj_id):
            return error_response(_("Only lecturers can edit assignments."), status.HTTP_403_FORBIDDEN)
        serializer = AssignmentCreateSerializer(
            assignment, data=request.data, partial=True, context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        assignment = serializer.save()
        return success_response(data=AssignmentSerializer(assignment, context={'request': request}).data)

    @extend_schema(summary="Delete an assignment (lecturer only)")
    def delete(self, request, assignment_id):
        assignment, err = self._get_assignment(assignment_id, request.user)
        if err:
            return err
        if not _is_class_lecturer(request.user, assignment.class_obj_id):
            return error_response(_("Only lecturers can delete assignments."), status.HTTP_403_FORBIDDEN)
        assignment.delete()
        return success_response(message=_("Assignment deleted."))


@extend_schema(tags=['Assignments'])
class SubmissionView(APIView):
    """Students save drafts or submit; lecturers view all submissions."""
    permission_classes = [IsAuthenticated]

    def _get_assignment(self, assignment_id, user):
        try:
            a = Assignment.objects.get(id=assignment_id, is_active=True)
        except Assignment.DoesNotExist:
            return None, error_response(_("Assignment not found."), status.HTTP_404_NOT_FOUND)
        if not _is_class_member(user, a.class_obj_id):
            return None, error_response(_("You are not a member of this class."), status.HTTP_403_FORBIDDEN)
        return a, None

    @extend_schema(
        summary="Get my submission or all submissions (lecturers see all)",
        responses={200: SubmissionSerializer(many=True)},
    )
    def get(self, request, assignment_id):
        assignment, err = self._get_assignment(assignment_id, request.user)
        if err:
            return err
        if _is_class_lecturer(request.user, assignment.class_obj_id):
            subs = assignment.submissions.select_related('student', 'graded_by').all()
        else:
            subs = assignment.submissions.filter(student=request.user)
        return success_response(data=SubmissionSerializer(subs, many=True, context={'request': request}).data)

    @extend_schema(
        summary="Save draft or submit assignment (students only)",
        request=SubmissionSaveSerializer,
        responses={200: SubmissionSerializer},
    )
    def post(self, request, assignment_id):
        assignment, err = self._get_assignment(assignment_id, request.user)
        if err:
            return err
        if _is_class_lecturer(request.user, assignment.class_obj_id):
            return error_response(_("Lecturers cannot submit assignments."), status.HTTP_403_FORBIDDEN)

        submission, _ = AssignmentSubmission.objects.get_or_create(
            assignment=assignment, student=request.user
        )
        if submission.status == AssignmentSubmission.STATUS_SUBMITTED and not _is_class_lecturer(request.user, assignment.class_obj_id):
            return error_response(_("Already submitted. Contact your lecturer to allow resubmission."), status.HTTP_400_BAD_REQUEST)

        serializer = SubmissionSaveSerializer(
            submission, data=request.data, partial=True,
            context={'request': request, 'assignment': assignment}
        )
        serializer.is_valid(raise_exception=True)

        if serializer.validated_data.get('status') == AssignmentSubmission.STATUS_SUBMITTED:
            submission.submitted_at = timezone.now()
            if assignment.due_date and timezone.now() > assignment.due_date:
                submission.is_late = True

        serializer.save()
        return success_response(data=SubmissionSerializer(submission, context={'request': request}).data)


@extend_schema(tags=['Assignments'])
class GradeSubmissionView(APIView):
    """Lecturers grade or return a specific submission."""
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Grade or return a student submission (lecturer only)",
        request=GradeSubmissionSerializer,
        responses={200: SubmissionSerializer},
    )
    def post(self, request, submission_id):
        try:
            submission = AssignmentSubmission.objects.select_related(
                'assignment__class_obj', 'student'
            ).get(id=submission_id)
        except AssignmentSubmission.DoesNotExist:
            return error_response(_("Submission not found."), status.HTTP_404_NOT_FOUND)

        assignment = submission.assignment
        if not _is_class_lecturer(request.user, assignment.class_obj_id):
            return error_response(_("Only lecturers can grade submissions."), status.HTTP_403_FORBIDDEN)

        if submission.status not in (AssignmentSubmission.STATUS_SUBMITTED, AssignmentSubmission.STATUS_GRADED):
            return error_response(_("Only submitted work can be graded."), status.HTTP_400_BAD_REQUEST)

        serializer = GradeSubmissionSerializer(
            data=request.data, context={'assignment': assignment}
        )
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        submission.score = data['score']
        submission.feedback = data['feedback']
        submission.graded_by = request.user
        submission.graded_at = timezone.now()
        submission.status = (
            AssignmentSubmission.STATUS_RETURNED
            if data['action'] == 'return'
            else AssignmentSubmission.STATUS_GRADED
        )
        submission.save()

        # Notify student
        try:
            NotificationService.create_notification(
                user=submission.student,
                notification_type='assignment_created',
                content=(
                    f"Your submission for '{assignment.title}' has been "
                    f"{'returned for revision' if data['action'] == 'return' else 'graded'}."
                    + (f" Score: {data['score']}/{assignment.max_score}." if data['action'] == 'grade' else "")
                ),
                related_id=str(submission.id),
            )
        except Exception as exc:
            logger.warning("Grade notification failed: %s", exc)

        return success_response(data=SubmissionSerializer(submission, context={'request': request}).data)


def _notify_assignment_created(assignment, creator):
    """Notify all class members (except the creator) about a new assignment."""
    try:
        from apps.classes.models import Membership
        from apps.notifications.services import ClassUpdateNotifier

        members = list(
            Membership.objects.filter(class_obj=assignment.class_obj)
            .exclude(user=creator)
            .select_related('user')
        )
        if not members:
            return

        content = (
            f"New assignment in {assignment.class_obj.name}: '{assignment.title}'."
            + (f" Due: {assignment.due_date.strftime('%b %d, %Y %H:%M')}" if assignment.due_date else "")
        )
        NotificationService.create_bulk([
            {
                'user': m.user,
                'notification_type': 'assignment_created',
                'content': content,
                'related_id': str(assignment.id),
            }
            for m in members
        ])

        # Email each member
        for membership in members:
            _send_assignment_email(membership.user, assignment, creator)

    except Exception as exc:
        logger.error("_notify_assignment_created failed: %s", exc, exc_info=True)


def _send_assignment_email(member, assignment, creator):
    from django.core.mail import EmailMultiAlternatives
    from django.conf import settings as django_settings

    from_email = getattr(django_settings, 'DEFAULT_FROM_EMAIL', None)
    if not from_email:
        return

    class_name = assignment.class_obj.name
    due_str = assignment.due_date.strftime("%b %d, %Y at %H:%M") if assignment.due_date else "No deadline set"
    subject = f"📝 New assignment in {class_name}: {assignment.title}"
    plain = (
        f"Hello {member.full_name},\n\n"
        f"{creator.full_name} posted a new assignment in {class_name}.\n\n"
        f"Title: {assignment.title}\nDue: {due_str}\n\n"
        f"Log in to Kibegi to view the full details and submit your work.\n\n© 2025 Kibegi."
    )
    html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#F9FAFB;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
<table width="100%" cellspacing="0" cellpadding="0"><tr><td align="center" style="padding:40px 20px;">
  <table width="600" cellspacing="0" cellpadding="0" style="background:#fff;border-radius:16px;box-shadow:0 4px 6px rgba(0,0,0,.05);">
    <tr><td style="padding:30px 40px;border-bottom:1px solid #E5E7EB;text-align:center;">
      <div style="display:inline-block;background:linear-gradient(135deg,#4F46E5,#3730A3);padding:10px 22px;border-radius:10px;">
        <span style="font-size:22px;font-weight:700;color:#fff;">📚 Kibegi</span>
      </div>
    </td></tr>
    <tr><td style="padding:35px 40px;">
      <h2 style="margin:0 0 16px;font-size:20px;color:#1F2937;">New Assignment Posted</h2>
      <p style="margin:0 0 12px;font-size:15px;color:#6B7280;">Hello <strong>{member.full_name}</strong>,</p>
      <p style="margin:0 0 20px;font-size:15px;color:#6B7280;line-height:1.6;">
        <strong>{creator.full_name}</strong> posted a new assignment in <strong>{class_name}</strong>:
      </p>
      <div style="background:#EEF2FF;border-left:4px solid #4F46E5;border-radius:8px;padding:16px 20px;margin-bottom:20px;">
        <p style="margin:0;font-size:16px;font-weight:700;color:#1F2937;">📝 {assignment.title}</p>
        <p style="margin:6px 0 0;font-size:14px;color:#6B7280;">Due: {due_str}</p>
        {f'<p style="margin:8px 0 0;font-size:14px;color:#1F2937;">{assignment.description}</p>' if assignment.description else ''}
      </div>
      <p style="margin:0;font-size:14px;color:#6B7280;">Log in to Kibegi to view the full assignment and submit your work.</p>
    </td></tr>
    <tr><td style="padding:20px 40px 30px;background:#F9FAFB;border-radius:0 0 16px 16px;text-align:center;">
      <p style="margin:0;font-size:12px;color:#6B7280;">© 2025 Kibegi. All rights reserved.</p>
    </td></tr>
  </table>
</td></tr></table>
</body></html>"""
    try:
        msg = EmailMultiAlternatives(subject, plain, from_email, [member.email])
        msg.attach_alternative(html, "text/html")
        msg.send(fail_silently=True)
    except Exception as exc:
        logger.warning("Assignment email to %s failed: %s", member.email, exc)
