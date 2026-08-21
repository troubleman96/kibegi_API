package classcomms

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
		rest := strings.Trim(strings.TrimPrefix(r.URL.Path, "/api/v1/classcomms/"), "/")
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
		case len(parts) == 2 && parts[0] == "contacts":
			a.contactDetail(w, r, parts[1])
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
