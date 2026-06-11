import uuid
from django.db import models
from django.conf import settings
from apps.core.utils.code_generator import generate_unique_code


class Assignment(models.Model):
    """An assignment created by a lecturer for a class.

    Students collect it (like Google Classroom), fill in their work,
    and submit. The lecturer can review and grade each submission.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    assignment_code = models.CharField(max_length=8, unique=True, editable=False, db_index=True)

    class_obj = models.ForeignKey(
        'classes.Class',
        on_delete=models.CASCADE,
        related_name='assignments',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='created_assignments',
    )

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    instructions = models.TextField(blank=True, help_text="Step-by-step instructions for students.")
    attachment = models.FileField(
        upload_to='assignments/attachments/',
        null=True,
        blank=True,
        help_text="Optional reference file (PDF, DOCX, etc.) for the assignment.",
    )

    due_date = models.DateTimeField(null=True, blank=True)
    max_score = models.PositiveSmallIntegerField(default=100)
    is_active = models.BooleanField(default=True, help_text="Inactive assignments hide from students.")
    allow_late_submission = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} [{self.assignment_code}] — {self.class_obj.name}"

    def save(self, *args, **kwargs):
        if not self.assignment_code:
            self.assignment_code = generate_unique_code(Assignment, 'assignment_code', 8)
        super().save(*args, **kwargs)


class AssignmentSubmission(models.Model):
    """A student's response to an assignment.

    Students can save a draft and submit when ready. Lecturers grade
    submitted work and leave feedback.
    """

    STATUS_DRAFT = 'draft'
    STATUS_SUBMITTED = 'submitted'
    STATUS_GRADED = 'graded'
    STATUS_RETURNED = 'returned'
    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Draft'),
        (STATUS_SUBMITTED, 'Submitted'),
        (STATUS_GRADED, 'Graded'),
        (STATUS_RETURNED, 'Returned for revision'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    assignment = models.ForeignKey(
        Assignment,
        on_delete=models.CASCADE,
        related_name='submissions',
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='assignment_submissions',
    )

    response_text = models.TextField(
        blank=True,
        help_text="Student's written response (like a Google Doc body).",
    )
    attachment = models.FileField(
        upload_to='assignments/submissions/',
        null=True,
        blank=True,
        help_text="Uploaded file as part of the submission.",
    )

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT, db_index=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    is_late = models.BooleanField(default=False)

    # Grading
    score = models.PositiveSmallIntegerField(null=True, blank=True)
    feedback = models.TextField(blank=True)
    graded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='graded_submissions',
    )
    graded_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-submitted_at', '-created_at']
        unique_together = [('assignment', 'student')]

    def __str__(self):
        return f"{self.student.full_name} → {self.assignment.title} ({self.status})"
