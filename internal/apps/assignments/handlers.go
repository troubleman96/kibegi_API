package assignments

import (
	"encoding/json"
	"errors"
	"net/http"
	"strings"

	"github.com/google/uuid"
	"github.com/troubleman96/kibegi_API/internal/apps/authentication"
	"github.com/troubleman96/kibegi_API/internal/platform/httpx"
)

type App struct {
	Repository Repository
	Auth       *authentication.TokenService
}

func (a App) PathHandler() http.Handler {
	return authentication.RequireAuth(a.Auth, http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		userID, ok := authentication.UserIDFromContext(r.Context())
		if !ok {
			httpx.WriteEnvelope(w, 401, false, "Authentication credentials were not provided.", nil, nil)
			return
		}
		rest := strings.Trim(strings.TrimPrefix(r.URL.Path, "/api/v1/assignments/"), "/")
		parts := strings.Split(rest, "/")
		switch {
		case len(parts) == 2 && parts[0] == "classes":
			a.listCreate(w, r, userID, parts[1])
		case len(parts) == 2 && parts[1] == "submissions":
			a.submissions(w, r, userID, parts[0])
		case len(parts) == 3 && parts[0] == "submissions" && parts[2] == "grade":
			a.grade(w, r, userID, parts[1])
		case len(parts) == 1 && parts[0] != "":
			a.detail(w, r, userID, parts[0])
		default:
			httpx.WriteEnvelope(w, 404, false, "Not found", nil, nil)
		}
	}))
}
func (a App) listCreate(w http.ResponseWriter, r *http.Request, userID int64, rawClass string) {
	classID, err := uuid.Parse(rawClass)
	if err != nil {
		httpx.WriteEnvelope(w, 404, false, "Class not found", nil, nil)
		return
	}
	if r.Method == http.MethodGet {
		items, err := a.Repository.List(r.Context(), classID, userID)
		if err != nil {
			httpx.WriteEnvelope(w, 503, false, "Assignments service unavailable", nil, nil)
			return
		}
		httpx.WriteEnvelope(w, 200, true, "Assignments retrieved successfully", items, nil)
		return
	}
	if r.Method != http.MethodPost {
		httpx.WriteEnvelope(w, 405, false, "method not allowed", nil, nil)
		return
	}
	var input Assignment
	if err := json.NewDecoder(r.Body).Decode(&input); err != nil {
		httpx.WriteEnvelope(w, 400, false, "Invalid assignment input", nil, nil)
		return
	}
	input.ClassID = classID
	item, err := a.Repository.Create(r.Context(), userID, input)
	if errors.Is(err, ErrNotLecturer) {
		httpx.WriteEnvelope(w, 403, false, err.Error(), nil, nil)
		return
	}
	if err != nil {
		httpx.WriteEnvelope(w, 400, false, err.Error(), nil, nil)
		return
	}
	httpx.WriteEnvelope(w, 201, true, "Assignment created successfully", item, nil)
}
func (a App) detail(w http.ResponseWriter, r *http.Request, userID int64, raw string) {
	id, err := uuid.Parse(raw)
	if err != nil {
		httpx.WriteEnvelope(w, 404, false, "Assignment not found", nil, nil)
		return
	}
	item, err := a.Repository.Find(r.Context(), id, userID)
	if errors.Is(err, ErrAssignmentNotFound) {
		httpx.WriteEnvelope(w, 404, false, "Assignment not found", nil, nil)
		return
	}
	if err != nil {
		httpx.WriteEnvelope(w, 503, false, "Assignments service unavailable", nil, nil)
		return
	}
	if r.Method == http.MethodGet {
		httpx.WriteEnvelope(w, 200, true, "Assignment retrieved successfully", item, nil)
		return
	}
	if !a.Repository.IsLecturer(r.Context(), item.ClassID, userID) {
		httpx.WriteEnvelope(w, 403, false, "You are not a lecturer of this class.", nil, nil)
		return
	}
	httpx.WriteEnvelope(w, 501, false, "Assignment mutation is pending the attachment storage slice", nil, nil)
}
func (a App) submissions(w http.ResponseWriter, r *http.Request, userID int64, raw string) {
	id, err := uuid.Parse(raw)
	if err != nil {
		httpx.WriteEnvelope(w, 404, false, "Assignment not found", nil, nil)
		return
	}
	if r.Method == http.MethodGet {
		items, err := a.Repository.Submissions(r.Context(), id, userID)
		if err != nil {
			httpx.WriteEnvelope(w, 503, false, "Assignments service unavailable", nil, nil)
			return
		}
		httpx.WriteEnvelope(w, 200, true, "Submissions retrieved successfully", items, nil)
		return
	}
	if r.Method != http.MethodPost {
		httpx.WriteEnvelope(w, 405, false, "method not allowed", nil, nil)
		return
	}
	var input struct {
		ResponseText string `json:"response_text"`
		Attachment   string `json:"attachment"`
		Status       string `json:"status"`
	}
	if err := json.NewDecoder(r.Body).Decode(&input); err != nil {
		httpx.WriteEnvelope(w, 400, false, "Invalid submission input", nil, nil)
		return
	}
	if input.Status == "" {
		input.Status = "draft"
	}
	if input.Status != "draft" && input.Status != "submitted" {
		httpx.WriteEnvelope(w, 400, false, "Students may only set status to 'draft' or 'submitted'.", nil, nil)
		return
	}
	item, err := a.Repository.SaveSubmission(r.Context(), id, userID, input.ResponseText, input.Attachment, input.Status)
	if err != nil {
		httpx.WriteEnvelope(w, 400, false, err.Error(), nil, nil)
		return
	}
	httpx.WriteEnvelope(w, 200, true, "Submission saved successfully", item, nil)
}
func (a App) grade(w http.ResponseWriter, r *http.Request, userID int64, raw string) {
	if r.Method != http.MethodPost {
		httpx.WriteEnvelope(w, 405, false, "method not allowed", nil, nil)
		return
	}
	id, err := uuid.Parse(raw)
	if err != nil {
		httpx.WriteEnvelope(w, 404, false, "Submission not found", nil, nil)
		return
	}
	var input struct {
		Score    int    `json:"score"`
		Feedback string `json:"feedback"`
		Action   string `json:"action"`
	}
	if err := json.NewDecoder(r.Body).Decode(&input); err != nil || input.Action != "grade" && input.Action != "return" {
		httpx.WriteEnvelope(w, 400, false, "Invalid grading input", nil, nil)
		return
	}
	item, err := a.Repository.Grade(r.Context(), id, userID, input.Score, input.Feedback, input.Action)
	if errors.Is(err, ErrSubmissionNotFound) {
		httpx.WriteEnvelope(w, 404, false, "Submission not found", nil, nil)
		return
	}
	if err != nil {
		httpx.WriteEnvelope(w, 503, false, "Assignments service unavailable", nil, nil)
		return
	}
	httpx.WriteEnvelope(w, 200, true, "Submission graded successfully", item, nil)
}
