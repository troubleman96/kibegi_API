package classcomms

import (
	"database/sql"
	"encoding/json"
	"errors"
	"net/http"
	"strings"

	"github.com/google/uuid"
	"github.com/troubleman96/kibegi_API/internal/platform/httpx"
)

func (a App) PublicHandler() http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		parts := strings.Split(strings.Trim(strings.TrimPrefix(r.URL.Path, "/api/v1/public/class-comms/"), "/"), "/")
		if len(parts) != 2 {
			httpx.WriteEnvelope(w, 404, false, "Not found", nil, nil)
			return
		}
		switch {
		case parts[1] == "info" && r.Method == http.MethodGet:
			a.publicInfo(w, r, parts[0])
		case parts[1] == "register" && r.Method == http.MethodPost:
			a.publicRegister(w, r, parts[0])
		default:
			httpx.WriteEnvelope(w, 404, false, "Not found", nil, nil)
		}
	})
}

func (a App) publicProfile(ctx interface{ Done() <-chan struct{} }, token string) (Profile, error) {
	return Profile{}, nil
}

func (a App) publicInfo(w http.ResponseWriter, r *http.Request, token string) {
	var classID uuid.UUID
	var enabled bool
	err := a.Repository.DB.QueryRowContext(r.Context(), `SELECT class_obj_id,public_registration_enabled FROM classcomms_classcommsprofile WHERE public_token=$1`, token).Scan(&classID, &enabled)
	if errors.Is(err, sql.ErrNoRows) {
		httpx.WriteEnvelope(w, 404, false, "Class communications profile not found", nil, nil)
		return
	}
	if err != nil {
		httpx.WriteEnvelope(w, 503, false, "Class communications service unavailable", nil, nil)
		return
	}
	if !enabled {
		httpx.WriteEnvelope(w, 403, false, "Public registration is disabled for this class.", nil, nil)
		return
	}
	profile, err := a.Repository.Profile(r.Context(), classID)
	if err != nil {
		httpx.WriteEnvelope(w, 503, false, "Class communications service unavailable", nil, nil)
		return
	}
	wallet, err := a.Repository.Wallet(r.Context(), classID)
	if err != nil {
		httpx.WriteEnvelope(w, 503, false, "Class communications service unavailable", nil, nil)
		return
	}
	data := map[string]any{"class_id": profile.ClassID, "class_name": profile.ClassName, "class_code": profile.ClassCode, "registration_hint": profile.RegistrationHint, "join_hint": "Create a Kibegi account, then join the class to receive channel messages.", "public_registration_enabled": profile.PublicRegistrationEnabled, "default_sender_name": profile.DefaultSenderName, "credits_remaining": wallet.BalanceCredits, "contacts_registered": profile.ContactCount, "registration_urls": map[string]string{"info": "/api/v1/public/class-comms/" + token + "/info/", "register": "/api/v1/public/class-comms/" + token + "/register/"}}
	httpx.WriteEnvelope(w, 200, true, "Public registration info retrieved successfully", data, nil)
}

func (a App) publicRegister(w http.ResponseWriter, r *http.Request, token string) {
	var input struct {
		FullName       string `json:"full_name"`
		PhoneNumber    string `json:"phone_number"`
		ConsentGranted *bool  `json:"consent_granted"`
		Notes          string `json:"notes"`
	}
	if err := json.NewDecoder(r.Body).Decode(&input); err != nil || strings.TrimSpace(input.FullName) == "" || strings.TrimSpace(input.PhoneNumber) == "" {
		httpx.WriteEnvelope(w, 400, false, "Invalid contact details", nil, nil)
		return
	}
	var classID uuid.UUID
	var enabled bool
	if err := a.Repository.DB.QueryRowContext(r.Context(), `SELECT class_obj_id,public_registration_enabled FROM classcomms_classcommsprofile WHERE public_token=$1`, token).Scan(&classID, &enabled); err != nil {
		httpx.WriteEnvelope(w, 404, false, "Class communications profile not found", nil, nil)
		return
	}
	if !enabled {
		httpx.WriteEnvelope(w, 403, false, "Public registration is disabled for this class.", nil, nil)
		return
	}
	consent := true
	if input.ConsentGranted != nil {
		consent = *input.ConsentGranted
	}
	var c Contact
	err := a.Repository.DB.QueryRowContext(r.Context(), `INSERT INTO classcomms_classcontact (id,full_name,phone_number,consent_granted,consent_source,notes,is_active,verified_at,created_at,updated_at,class_obj_id,created_by_id) VALUES ($1,$2,$3,$4,'public',$5,true,NOW(),NOW(),NOW(),$6,NULL) ON CONFLICT(class_obj_id,phone_number) DO UPDATE SET full_name=EXCLUDED.full_name,consent_granted=EXCLUDED.consent_granted,notes=EXCLUDED.notes,is_active=true,updated_at=NOW() RETURNING id,class_obj_id,full_name,phone_number,consent_granted,consent_source,notes,is_active,member_id,created_at,updated_at`, uuid.New(), strings.TrimSpace(input.FullName), strings.TrimSpace(input.PhoneNumber), consent, input.Notes, classID).Scan(&c.ID, &c.ClassID, &c.FullName, &c.PhoneNumber, &c.ConsentGranted, &c.ConsentSource, &c.Notes, &c.IsActive, &c.MemberID, &c.CreatedAt, &c.UpdatedAt)
	if err != nil {
		httpx.WriteEnvelope(w, 400, false, "Could not register contact", nil, nil)
		return
	}
	httpx.WriteEnvelope(w, 201, true, "Contact registered successfully", c, nil)
}
