package classcomms

import (
	"database/sql"
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
		rest := strings.TrimPrefix(r.URL.Path, "/api/v1/classcomms/")
		if rest == r.URL.Path {
			rest = strings.TrimPrefix(r.URL.Path, "/api/v1/class-comms/")
		}
		rest = strings.Trim(rest, "/")
		parts := strings.Split(rest, "/")
		switch {
		case len(parts) == 3 && parts[0] == "classes" && parts[2] == "profile":
			a.profile(w, r, userID, parts[1])
		case len(parts) == 3 && parts[0] == "classes" && parts[2] == "wallet":
			a.wallet(w, r, userID, parts[1])
		case len(parts) == 3 && parts[0] == "classes" && parts[2] == "contacts":
			a.contacts(w, r, userID, parts[1])
		case len(parts) == 3 && parts[0] == "classes" && parts[2] == "broadcasts":
			a.broadcasts(w, r, userID, parts[1])
		case len(parts) == 3 && parts[0] == "classes" && parts[2] == "representatives" && r.Method == http.MethodPost:
			a.representative(w, r, userID, parts[1])
		case len(parts) == 2 && parts[0] == "contacts":
			a.contactDetail(w, r, parts[1])
		case len(parts) == 2 && parts[0] == "broadcasts" && r.Method == http.MethodGet:
			a.broadcastDetail(w, r, userID, parts[1])
		default:
			httpx.WriteEnvelope(w, 404, false, "Not found", nil, nil)
		}
	}))
}
func (a App) profile(w http.ResponseWriter, r *http.Request, userID int64, raw string) {
	id, err := uuid.Parse(raw)
	if err != nil {
		httpx.WriteEnvelope(w, 404, false, "Class not found", nil, nil)
		return
	}
	p, err := a.Repository.Profile(r.Context(), id)
	if err != nil {
		httpx.WriteEnvelope(w, 404, false, "Class not found", nil, nil)
		return
	}
	if r.Method == http.MethodPatch || r.Method == http.MethodPut {
		var input struct {
			PublicRegistrationEnabled *bool   `json:"public_registration_enabled"`
			DefaultSenderName         *string `json:"default_sender_name"`
			RegistrationHint          *string `json:"registration_hint"`
		}
		if err := json.NewDecoder(r.Body).Decode(&input); err != nil {
			httpx.WriteEnvelope(w, 400, false, "Invalid input", nil, nil)
			return
		}
		if input.PublicRegistrationEnabled != nil {
			_, _ = a.Repository.DB.ExecContext(r.Context(), `UPDATE classcomms_classcommsprofile SET public_registration_enabled=$2,updated_at=NOW() WHERE class_obj_id=$1`, id, *input.PublicRegistrationEnabled)
		}
		if input.DefaultSenderName != nil {
			_, _ = a.Repository.DB.ExecContext(r.Context(), `UPDATE classcomms_classcommsprofile SET default_sender_name=$2,updated_at=NOW() WHERE class_obj_id=$1`, id, *input.DefaultSenderName)
		}
		if input.RegistrationHint != nil {
			_, _ = a.Repository.DB.ExecContext(r.Context(), `UPDATE classcomms_classcommsprofile SET registration_hint=$2,updated_at=NOW() WHERE class_obj_id=$1`, id, *input.RegistrationHint)
		}
		p, _ = a.Repository.Profile(r.Context(), id)
	}
	httpx.WriteEnvelope(w, 200, true, "Class communications profile retrieved successfully", p, nil)
}
func (a App) wallet(w http.ResponseWriter, r *http.Request, userID int64, raw string) {
	id, err := uuid.Parse(raw)
	if err != nil {
		httpx.WriteEnvelope(w, 404, false, "Class not found", nil, nil)
		return
	}
	wallet, err := a.Repository.Wallet(r.Context(), id)
	if err != nil {
		httpx.WriteEnvelope(w, 503, false, "Class communications wallet unavailable", nil, nil)
		return
	}
	httpx.WriteEnvelope(w, 200, true, "Class communications wallet retrieved successfully", wallet, nil)
}
func (a App) contacts(w http.ResponseWriter, r *http.Request, userID int64, raw string) {
	id, err := uuid.Parse(raw)
	if err != nil {
		httpx.WriteEnvelope(w, 404, false, "Class not found", nil, nil)
		return
	}
	if r.Method == http.MethodGet {
		items, err := a.Repository.Contacts(r.Context(), id)
		if err != nil {
			httpx.WriteEnvelope(w, 503, false, "Class communications service unavailable", nil, nil)
			return
		}
		httpx.WriteEnvelope(w, 200, true, "Class contacts retrieved successfully", items, nil)
		return
	}
	if r.Method != http.MethodPost {
		httpx.WriteEnvelope(w, 405, false, "method not allowed", nil, nil)
		return
	}
	var input Contact
	if err := json.NewDecoder(r.Body).Decode(&input); err != nil || strings.TrimSpace(input.FullName) == "" || strings.TrimSpace(input.PhoneNumber) == "" {
		httpx.WriteEnvelope(w, 400, false, "Full name and phone number are required", nil, nil)
		return
	}
	item, err := a.Repository.UpsertContact(r.Context(), id, userID, input)
	if err != nil {
		httpx.WriteEnvelope(w, 400, false, err.Error(), nil, nil)
		return
	}
	httpx.WriteEnvelope(w, 201, true, "Class contact saved successfully", item, nil)
}
func (a App) contactDetail(w http.ResponseWriter, r *http.Request, raw string) {
	id, err := uuid.Parse(raw)
	if err != nil {
		httpx.WriteEnvelope(w, 404, false, "Contact not found", nil, nil)
		return
	}
	if r.Method != http.MethodDelete {
		httpx.WriteEnvelope(w, 405, false, "method not allowed", nil, nil)
		return
	}
	if err := a.Repository.DeleteContact(r.Context(), id); errors.Is(err, ErrNotFound) {
		httpx.WriteEnvelope(w, 404, false, "Contact not found", nil, nil)
		return
	} else if err != nil {
		httpx.WriteEnvelope(w, 503, false, "Class communications service unavailable", nil, nil)
		return
	}
	httpx.WriteEnvelope(w, 200, true, "Class contact removed successfully", nil, nil)
}
func (a App) representative(w http.ResponseWriter, r *http.Request, userID int64, raw string) {
	classID, err := uuid.Parse(raw)
	if err != nil {
		httpx.WriteEnvelope(w, 404, false, "Class not found", nil, nil)
		return
	}
	var allowed bool
	if err := a.Repository.DB.QueryRowContext(r.Context(), `SELECT EXISTS(SELECT 1 FROM classes_class c WHERE c.id=$1 AND (c.creator_id=$2 OR EXISTS(SELECT 1 FROM classes_membership m WHERE m.class_obj_id=c.id AND m.user_id=$2 AND m.role IN ('lecturer','admin'))))`, classID, userID).Scan(&allowed); err != nil || !allowed {
		httpx.WriteEnvelope(w, 403, false, "You do not have permission to manage class communications", nil, nil)
		return
	}
	var input struct {
		UserID int64  `json:"user_id"`
		Role   string `json:"role"`
	}
	if json.NewDecoder(r.Body).Decode(&input) != nil || input.UserID == 0 || strings.TrimSpace(input.Role) == "" {
		httpx.WriteEnvelope(w, 400, false, "Invalid representative details", nil, nil)
		return
	}
	item, err := a.Repository.SetRepresentative(r.Context(), classID, input.UserID, input.Role)
	if errors.Is(err, sql.ErrNoRows) {
		httpx.WriteEnvelope(w, 404, false, "Class member not found", nil, nil)
		return
	}
	if err != nil {
		httpx.WriteEnvelope(w, 503, false, "Class communications service unavailable", nil, nil)
		return
	}
	httpx.WriteEnvelope(w, 200, true, "Class representative role updated successfully", item, nil)
}
func (a App) broadcastDetail(w http.ResponseWriter, r *http.Request, userID int64, raw string) {
	id, err := uuid.Parse(raw)
	if err != nil {
		httpx.WriteEnvelope(w, 404, false, "Class broadcast not found", nil, nil)
		return
	}
	item, err := a.Repository.FindBroadcast(r.Context(), id)
	if errors.Is(err, sql.ErrNoRows) {
		httpx.WriteEnvelope(w, 404, false, "Class broadcast not found", nil, nil)
		return
	}
	if err != nil {
		httpx.WriteEnvelope(w, 503, false, "Class communications service unavailable", nil, nil)
		return
	}
	var allowed bool
	_ = a.Repository.DB.QueryRowContext(r.Context(), `SELECT EXISTS(SELECT 1 FROM classes_class c WHERE c.id=$1 AND (c.creator_id=$2 OR EXISTS(SELECT 1 FROM classes_membership m WHERE m.class_obj_id=c.id AND m.user_id=$2)))`, item.ClassID, userID).Scan(&allowed)
	if !allowed {
		httpx.WriteEnvelope(w, 403, false, "You do not have permission to view this broadcast", nil, nil)
		return
	}
	httpx.WriteEnvelope(w, 200, true, "Class broadcast retrieved successfully", item, nil)
}

func (a App) broadcasts(w http.ResponseWriter, r *http.Request, userID int64, raw string) {
	if r.Method != http.MethodPost {
		httpx.WriteEnvelope(w, 405, false, "method not allowed", nil, nil)
		return
	}
	id, err := uuid.Parse(raw)
	if err != nil {
		httpx.WriteEnvelope(w, 404, false, "Class not found", nil, nil)
		return
	}
	var input struct {
		Subject string `json:"subject"`
		Message string `json:"message"`
		Venue   string `json:"venue"`
	}
	if err := json.NewDecoder(r.Body).Decode(&input); err != nil || strings.TrimSpace(input.Message) == "" {
		httpx.WriteEnvelope(w, 400, false, "Message is required", nil, nil)
		return
	}
	item, err := a.Repository.CreateBroadcast(r.Context(), id, userID, input.Subject, input.Message, input.Venue)
	if err != nil {
		httpx.WriteEnvelope(w, 503, false, "Class communications service unavailable", nil, nil)
		return
	}
	httpx.WriteEnvelope(w, 201, true, "Class broadcast created successfully", item, nil)
}
