from django.urls import path
from .views import (
    AssignmentListCreateView,
    AssignmentDetailView,
    SubmissionView,
    GradeSubmissionView,
)

app_name = 'assignments'

urlpatterns = [
    # Lecturer creates / lists assignments per class
    path('classes/<uuid:class_id>/', AssignmentListCreateView.as_view(), name='assignment_list_create'),

    # Assignment detail (get, patch, delete)
    path('<uuid:assignment_id>/', AssignmentDetailView.as_view(), name='assignment_detail'),

    # Student submits; lecturer views all submissions for an assignment
    path('<uuid:assignment_id>/submissions/', SubmissionView.as_view(), name='submission'),

    # Lecturer grades a specific submission
    path('submissions/<uuid:submission_id>/grade/', GradeSubmissionView.as_view(), name='grade_submission'),
]
