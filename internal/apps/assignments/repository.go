package assignments

import (
	"context"
	"database/sql"
	"errors"
	"strings"
	"time"

	"github.com/google/uuid"
)

var (
	ErrAssignmentNotFound = errors.New("Assignment not found")
	ErrSubmissionNotFound = errors.New("Submission not found")
	ErrNotLecturer        = errors.New("You are not a lecturer of this class.")
)

type User struct {
	ID       int64  `json:"id"`
	Email    string `json:"email"`
	FullName string `json:"full_name"`
	UserType string `json:"user_type"`
}
type Assignment struct {
	ID                 uuid.UUID  `json:"id"`
	Code               string     `json:"assignment_code"`
	ClassID            uuid.UUID  `json:"class_obj"`
	CreatedBy          User       `json:"created_by"`
	Title              string     `json:"title"`
	Description        string     `json:"description"`
	Instructions       string     `json:"instructions"`
	ObjectName         string     `json:"attachment"`
	DueDate            *time.Time `json:"due_date"`
	MaxScore           int        `json:"max_score"`
	IsActive           bool       `json:"is_active"`
	AllowLate          bool       `json:"allow_late_submission"`
	SubmissionCount    int        `json:"submission_count"`
	MySubmissionStatus *string    `json:"my_submission_status"`
	CreatedAt          time.Time  `json:"created_at"`
	UpdatedAt          time.Time  `json:"updated_at"`
}
type Submission struct {
	ID              uuid.UUID  `json:"id"`
	AssignmentID    uuid.UUID  `json:"assignment"`
	AssignmentTitle string     `json:"assignment_title"`
	AssignmentCode  string     `json:"assignment_code"`
	Student         User       `json:"student"`
	ResponseText    string     `json:"response_text"`
	ObjectName      string     `json:"attachment"`
	Status          string     `json:"status"`
	SubmittedAt     *time.Time `json:"submitted_at"`
	IsLate          bool       `json:"is_late"`
	Score           *int       `json:"score"`
	Feedback        string     `json:"feedback"`
	GradedBy        *User      `json:"graded_by"`
	GradedAt        *time.Time `json:"graded_at"`
}
type Repository struct{ DB *sql.DB }

func (r Repository) IsLecturer(ctx context.Context, classID uuid.UUID, userID int64) bool {
	var ok bool
	_ = r.DB.QueryRowContext(ctx, `SELECT EXISTS(SELECT 1 FROM classes_membership WHERE class_obj_id=$1 AND user_id=$2 AND role='lecturer')`, classID, userID).Scan(&ok)
	return ok
}
func (r Repository) List(ctx context.Context, classID uuid.UUID, userID int64) ([]Assignment, error) {
	rows, err := r.DB.QueryContext(ctx, `SELECT a.id,a.assignment_code,a.class_obj_id,a.title,a.description,a.instructions,NULLIF(a.attachment,''),a.due_date,a.max_score,a.is_active,a.allow_late_submission,a.created_at,a.updated_at,u.id,u.email,u.full_name,u.user_type,COUNT(s.id) FILTER(WHERE s.status IN ('submitted','graded','returned')),MAX(CASE WHEN s.student_id=$2 THEN s.status END) FROM assignments_assignment a JOIN authentication_user u ON u.id=a.created_by_id LEFT JOIN assignments_assignmentsubmission s ON s.assignment_id=a.id WHERE a.class_obj_id=$1 GROUP BY a.id,u.id ORDER BY a.created_at DESC`, classID, userID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := make([]Assignment, 0)
	for rows.Next() {
		var x Assignment
		var image sql.NullString
		var status sql.NullString
		if err := rows.Scan(&x.ID, &x.Code, &x.ClassID, &x.Title, &x.Description, &x.Instructions, &image, &x.DueDate, &x.MaxScore, &x.IsActive, &x.AllowLate, &x.CreatedAt, &x.UpdatedAt, &x.CreatedBy.ID, &x.CreatedBy.Email, &x.CreatedBy.FullName, &x.CreatedBy.UserType, &x.SubmissionCount, &status); err != nil {
			return nil, err
		}
		if image.Valid {
			x.ObjectName = image.String
		}
		if status.Valid {
			x.MySubmissionStatus = &status.String
		}
		out = append(out, x)
	}
	return out, rows.Err()
}
func (r Repository) Create(ctx context.Context, userID int64, x Assignment) (Assignment, error) {
	if !r.IsLecturer(ctx, x.ClassID, userID) {
		return Assignment{}, ErrNotLecturer
	}
	var out Assignment
	err := r.DB.QueryRowContext(ctx, `INSERT INTO assignments_assignment (id,assignment_code,title,description,instructions,attachment,due_date,max_score,is_active,allow_late_submission,created_at,updated_at,class_obj_id,created_by_id) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,NOW(),NOW(),$11,$12) RETURNING id,assignment_code,class_obj_id,title,description,instructions,attachment,due_date,max_score,is_active,allow_late_submission,created_at,updated_at`, uuid.New(), strings.ToUpper(uuid.NewString()[:8]), x.Title, x.Description, x.Instructions, x.ObjectName, x.DueDate, x.MaxScore, x.IsActive, x.AllowLate, x.ClassID, userID).Scan(&out.ID, &out.Code, &out.ClassID, &out.Title, &out.Description, &out.Instructions, &out.ObjectName, &out.DueDate, &out.MaxScore, &out.IsActive, &out.AllowLate, &out.CreatedAt, &out.UpdatedAt)
	return out, err
}
func (r Repository) Find(ctx context.Context, id uuid.UUID, userID int64) (Assignment, error) {
	var x Assignment
	err := r.DB.QueryRowContext(ctx, `SELECT a.id,a.assignment_code,a.class_obj_id,a.title,a.description,a.instructions,NULLIF(a.attachment,''),a.due_date,a.max_score,a.is_active,a.allow_late_submission,a.created_at,a.updated_at,u.id,u.email,u.full_name,u.user_type,COUNT(s.id) FILTER(WHERE s.status IN ('submitted','graded','returned')),MAX(CASE WHEN s.student_id=$2 THEN s.status END) FROM assignments_assignment a JOIN authentication_user u ON u.id=a.created_by_id LEFT JOIN assignments_assignmentsubmission s ON s.assignment_id=a.id WHERE a.id=$1 GROUP BY a.id,u.id`, id, userID).Scan(&x.ID, &x.Code, &x.ClassID, &x.Title, &x.Description, &x.Instructions, &x.ObjectName, &x.DueDate, &x.MaxScore, &x.IsActive, &x.AllowLate, &x.CreatedAt, &x.UpdatedAt, &x.CreatedBy.ID, &x.CreatedBy.Email, &x.CreatedBy.FullName, &x.CreatedBy.UserType, &x.SubmissionCount, &x.MySubmissionStatus)
	if errors.Is(err, sql.ErrNoRows) {
		return Assignment{}, ErrAssignmentNotFound
	}
	return x, err
}
func (r Repository) SaveSubmission(ctx context.Context, assignmentID uuid.UUID, studentID int64, response, attachment, status string) (Submission, error) {
	var due time.Time
	var allow bool
	if err := r.DB.QueryRowContext(ctx, `SELECT due_date,allow_late_submission FROM assignments_assignment WHERE id=$1`, assignmentID).Scan(&due, &allow); err != nil {
		return Submission{}, ErrAssignmentNotFound
	}
	if status == "submitted" && !allow && !due.IsZero() && time.Now().After(due) {
		return Submission{}, errors.New("The submission deadline has passed.")
	}
	submittedAt := any(nil)
	if status == "submitted" {
		submittedAt = time.Now().UTC()
	}
	var x Submission
	err := r.DB.QueryRowContext(ctx, `INSERT INTO assignments_assignmentsubmission (id,response_text,attachment,status,submitted_at,is_late,score,feedback,graded_at,created_at,updated_at,assignment_id,student_id) VALUES ($1,$2,$3,$4,$5,$6,NULL,'',NULL,NOW(),NOW(),$7,$8) ON CONFLICT(assignment_id,student_id) DO UPDATE SET response_text=EXCLUDED.response_text,attachment=EXCLUDED.attachment,status=EXCLUDED.status,submitted_at=EXCLUDED.submitted_at,is_late=EXCLUDED.is_late,updated_at=NOW() RETURNING id,assignment_id,response_text,attachment,status,submitted_at,is_late,score,feedback,graded_at`, uuid.New(), response, attachment, status, submittedAt, !due.IsZero() && time.Now().After(due), assignmentID, studentID).Scan(&x.ID, &x.AssignmentID, &x.ResponseText, &x.ObjectName, &x.Status, &x.SubmittedAt, &x.IsLate, &x.Score, &x.Feedback, &x.GradedAt)
	return x, err
}
func (r Repository) Submissions(ctx context.Context, id uuid.UUID, userID int64) ([]Submission, error) {
	rows, err := r.DB.QueryContext(ctx, `SELECT s.id,s.assignment_id,a.title,a.assignment_code,s.response_text,NULLIF(s.attachment,''),s.status,s.submitted_at,s.is_late,s.score,s.feedback,s.graded_at,u.id,u.email,u.full_name,u.user_type FROM assignments_assignmentsubmission s JOIN assignments_assignment a ON a.id=s.assignment_id JOIN authentication_user u ON u.id=s.student_id WHERE s.assignment_id=$1 AND (a.created_by_id=$2 OR s.student_id=$2) ORDER BY s.submitted_at DESC NULLS LAST`, id, userID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := make([]Submission, 0)
	for rows.Next() {
		var x Submission
		var image sql.NullString
		if err := rows.Scan(&x.ID, &x.AssignmentID, &x.AssignmentTitle, &x.AssignmentCode, &x.ResponseText, &image, &x.Status, &x.SubmittedAt, &x.IsLate, &x.Score, &x.Feedback, &x.GradedAt, &x.Student.ID, &x.Student.Email, &x.Student.FullName, &x.Student.UserType); err != nil {
			return nil, err
		}
		if image.Valid {
			x.ObjectName = image.String
		}
		out = append(out, x)
	}
	return out, rows.Err()
}
func (r Repository) Grade(ctx context.Context, id uuid.UUID, userID int64, score int, feedback, action string) (Submission, error) {
	var x Submission
	err := r.DB.QueryRowContext(ctx, `UPDATE assignments_assignmentsubmission s SET status=$3,score=$4,feedback=$5,graded_by_id=$2,graded_at=NOW(),updated_at=NOW() FROM assignments_assignment a WHERE s.id=$1 AND a.id=s.assignment_id AND a.created_by_id=$2 RETURNING s.id,s.assignment_id,s.status,s.score,s.feedback,s.graded_at`, id, userID, map[string]string{"grade": "graded", "return": "returned"}[action], score, feedback).Scan(&x.ID, &x.AssignmentID, &x.Status, &x.Score, &x.Feedback, &x.GradedAt)
	if errors.Is(err, sql.ErrNoRows) {
		return Submission{}, ErrSubmissionNotFound
	}
	return x, err
}
