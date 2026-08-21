package authentication

import (
	"crypto/rand"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"os"
	"strings"
	"time"

	"github.com/troubleman96/kibegi_API/internal/platform/httpx"
	platformsms "github.com/troubleman96/kibegi_API/internal/platform/sms"
)

func (a App) GoogleLoginHandler() http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			httpx.WriteEnvelope(w, 405, false, "method not allowed", nil, nil)
			return
		}
		var input map[string]any
		if err := json.NewDecoder(r.Body).Decode(&input); err != nil {
			httpx.WriteEnvelope(w, 400, false, "Invalid input", nil, nil)
			return
		}
		token, _ := input["access_token"].(string)
		if token == "" {
			token, _ = input["credential"].(string)
		}
		if token == "" {
			token, _ = input["id_token"].(string)
		}
		if strings.TrimSpace(token) == "" {
			httpx.WriteEnvelope(w, 400, false, "Google access_token or credential is required.", nil, nil)
			return
		}
		info, err := googleUserInfo(r, token, input["credential"] != nil || input["id_token"] != nil)
		if err != nil {
			httpx.WriteEnvelope(w, 401, false, "Invalid or expired Google access token.", nil, nil)
			return
		}
		email, _ := info["email"].(string)
		email = strings.ToLower(strings.TrimSpace(email))
		verified, _ := info["email_verified"].(bool)
		if email == "" || !verified {
			httpx.WriteEnvelope(w, 400, false, "Google email address is not verified.", nil, nil)
			return
		}
		user, err := a.Users.FindByEmail(r.Context(), email)
		if errors.Is(err, ErrUserNotFound) {
			name, _ := info["name"].(string)
			if strings.TrimSpace(name) == "" {
				name = strings.Split(email, "@")[0]
			}
			ut, _ := input["user_type"].(string)
			if ut != "lecturer" {
				ut = "student"
			}
			approved := ut != "lecturer"
			err = a.Users.DB.QueryRowContext(r.Context(), `INSERT INTO authentication_user (password,last_login,is_superuser,email,full_name,user_type,is_active,is_staff,is_approved,date_joined,university,phone_number,phone_verified) VALUES ('',NULL,false,$1,$2,$3,true,false,$4,NOW(),'','','false') RETURNING id`, email, name, ut, approved).Scan(&user.ID)
			if err == nil {
				user, err = a.Users.FindByID(r.Context(), user.ID)
			}
		}
		if err != nil {
			httpx.WriteEnvelope(w, 503, false, "Authentication service unavailable", nil, nil)
			return
		}
		if !user.IsActive {
			httpx.WriteEnvelope(w, 403, false, "Your account is inactive. Please contact support.", nil, nil)
			return
		}
		if user.UserType == "lecturer" && !user.IsApproved {
			httpx.WriteEnvelope(w, 403, false, "pending_approval", nil, nil)
			return
		}
		refresh, access, err := a.Tokens.IssuePair(user.ID, time.Now().UTC())
		if err != nil {
			httpx.WriteEnvelope(w, 503, false, "Authentication service unavailable", nil, nil)
			return
		}
		httpx.WriteEnvelope(w, 200, true, "Google login successful", loginData{User: a.profile(r, user), Tokens: tokenPair{Refresh: refresh, Access: access}}, nil)
	})
}
func googleUserInfo(r *http.Request, token string, idToken bool) (map[string]any, error) {
	var endpoint string
	if idToken {
		endpoint = "https://oauth2.googleapis.com/tokeninfo?" + url.Values{"id_token": []string{token}}.Encode()
	} else {
		endpoint = "https://www.googleapis.com/oauth2/v3/userinfo"
	}
	req, _ := http.NewRequestWithContext(r.Context(), http.MethodGet, endpoint, nil)
	if !idToken {
		req.Header.Set("Authorization", "Bearer "+token)
	}
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return nil, fmt.Errorf("google returned %s", resp.Status)
	}
	var out map[string]any
	err = json.NewDecoder(resp.Body).Decode(&out)
	return out, err
}

func normalizePhone(raw string) string {
	raw = strings.TrimSpace(raw)
	if strings.HasPrefix(raw, "+255") && len(raw) == 13 {
		return raw
	}
	if strings.HasPrefix(raw, "0") && len(raw) == 10 {
		return "+255" + raw[1:]
	}
	if (strings.HasPrefix(raw, "7") || strings.HasPrefix(raw, "6")) && len(raw) == 9 {
		return "+255" + raw
	}
	return ""
}
func (a App) PhoneSendOTPHandler() http.Handler {
	return RequireAuth(a.Tokens, http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			httpx.WriteEnvelope(w, 405, false, "method not allowed", nil, nil)
			return
		}
		uid, ok := UserIDFromContext(r.Context())
		if !ok {
			httpx.WriteEnvelope(w, 401, false, "Authentication credentials were not provided.", nil, nil)
			return
		}
		var input map[string]string
		if json.NewDecoder(r.Body).Decode(&input) != nil {
			httpx.WriteEnvelope(w, 400, false, "Invalid input", nil, nil)
			return
		}
		phone := normalizePhone(input["phone_number"])
		if phone == "" {
			phone = normalizePhone(input["phone"])
		}
		if phone == "" {
			httpx.WriteEnvelope(w, 400, false, "Invalid Tanzania phone number. Use 0XXXXXXXXX, 7XXXXXXXX, or +255XXXXXXXXX", nil, nil)
			return
		}
		var duplicate bool
		if err := a.Users.DB.QueryRowContext(r.Context(), `SELECT EXISTS(SELECT 1 FROM authentication_user WHERE phone_number=$1 AND id<>$2 AND phone_number<>'')`, phone, uid).Scan(&duplicate); err != nil {
			httpx.WriteEnvelope(w, 503, false, "Phone verification service unavailable", nil, nil)
			return
		}
		if duplicate {
			httpx.WriteEnvelope(w, 400, false, "This phone number is already in use.", nil, nil)
			return
		}
		var recent int
		if err := a.Users.DB.QueryRowContext(r.Context(), `SELECT COUNT(*) FROM authentication_phoneotp WHERE user_id=$1 AND phone=$2 AND created_at>=NOW()-INTERVAL '1 hour'`, uid, phone).Scan(&recent); err != nil {
			httpx.WriteEnvelope(w, 503, false, "Phone verification service unavailable", nil, nil)
			return
		}
		if recent >= 3 {
			httpx.WriteEnvelope(w, 429, false, "Too many OTP requests. Please wait before trying again.", nil, nil)
			return
		}
		code := randomDigits(6)
		if _, err := a.Users.DB.ExecContext(r.Context(), `INSERT INTO authentication_phoneotp (phone,otp,attempts,verified,expires_at,created_at,user_id) VALUES ($1,$2,0,false,NOW()+INTERVAL '10 minutes',NOW(),$3)`, phone, code, uid); err != nil {
			httpx.WriteEnvelope(w, 503, false, "Phone verification service unavailable", nil, nil)
			return
		}
		client := platformsms.NewClient(platformsms.Config{APIKey: os.Getenv("SENDAFRICA_API_KEY"), BaseURL: os.Getenv("SENDAFRICA_BASE_URL"), SenderID: os.Getenv("SENDAFRICA_SENDER_ID")})
		if client.Configured() {
			if _, _, err := client.Send(r.Context(), phone, "Kibegi code: "+code+". Expires in 10 min.", ""); err != nil {
				httpx.WriteEnvelope(w, 503, false, "Could not send SMS", nil, nil)
				return
			}
		}
		httpx.WriteEnvelope(w, 200, true, "OTP sent to your phone number", map[string]string{"phone": phone}, nil)
	}))
}
func (a App) PhoneVerifyOTPHandler() http.Handler {
	return RequireAuth(a.Tokens, http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			httpx.WriteEnvelope(w, 405, false, "method not allowed", nil, nil)
			return
		}
		uid, ok := UserIDFromContext(r.Context())
		if !ok {
			httpx.WriteEnvelope(w, 401, false, "Authentication credentials were not provided.", nil, nil)
			return
		}
		var input map[string]string
		_ = json.NewDecoder(r.Body).Decode(&input)
		phone := normalizePhone(input["phone_number"])
		if phone == "" {
			phone = normalizePhone(input["phone"])
		}
		code := strings.TrimSpace(input["otp"])
		if phone == "" || code == "" {
			httpx.WriteEnvelope(w, 400, false, "phone_number and otp are required", nil, nil)
			return
		}
		var id int64
		var expected string
		var attempts int
		var expires time.Time
		if err := a.Users.DB.QueryRowContext(r.Context(), `SELECT id,otp,attempts,expires_at FROM authentication_phoneotp WHERE user_id=$1 AND phone=$2 AND verified=false ORDER BY created_at DESC LIMIT 1`, uid, phone).Scan(&id, &expected, &attempts, &expires); err != nil {
			httpx.WriteEnvelope(w, 400, false, "No pending OTP for this number. Please request a new one.", nil, nil)
			return
		}
		if time.Now().After(expires) {
			httpx.WriteEnvelope(w, 400, false, "OTP has expired. Please request a new one.", nil, nil)
			return
		}
		if attempts >= 5 {
			httpx.WriteEnvelope(w, 400, false, "Too many failed attempts. Please request a new OTP.", nil, nil)
			return
		}
		if expected != code {
			_, _ = a.Users.DB.ExecContext(r.Context(), `UPDATE authentication_phoneotp SET attempts=attempts+1 WHERE id=$1`, id)
			httpx.WriteEnvelope(w, 400, false, "Incorrect OTP.", nil, nil)
			return
		}
		_, err := a.Users.DB.ExecContext(r.Context(), `UPDATE authentication_phoneotp SET verified=true WHERE id=$1`, id)
		if err == nil {
			_, err = a.Users.DB.ExecContext(r.Context(), `UPDATE authentication_user SET phone_number=$2,phone_verified=true WHERE id=$1`, uid, phone)
		}
		if err != nil {
			httpx.WriteEnvelope(w, 503, false, "Phone verification service unavailable", nil, nil)
			return
		}
		httpx.WriteEnvelope(w, 200, true, "Phone number verified successfully", map[string]any{"phone_number": phone, "phone_verified": true}, nil)
	}))
}
func randomDigits(n int) string {
	b := make([]byte, n)
	if _, err := rand.Read(b); err != nil {
		return "000000"
	}
	for i := range b {
		b[i] = '0' + b[i]%10
	}
	return string(b)
}

func (a App) LecturerApprovalHandler(mailer RegistrationMailer) http.Handler {
	return RequireAuth(a.Tokens, http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		uid, ok := UserIDFromContext(r.Context())
		if !ok {
			httpx.WriteEnvelope(w, 401, false, "Authentication credentials were not provided.", nil, nil)
			return
		}
		var admin bool
		if err := a.Users.DB.QueryRowContext(r.Context(), `SELECT is_staff OR is_superuser FROM authentication_user WHERE id=$1`, uid).Scan(&admin); err != nil || !admin {
			httpx.WriteEnvelope(w, 403, false, "You do not have permission to perform this action", nil, nil)
			return
		}
		if r.Method == http.MethodGet {
			rows, err := a.Users.DB.QueryContext(r.Context(), `SELECT id FROM authentication_user WHERE user_type='lecturer' AND is_active=true AND is_approved=false ORDER BY id`)
			if err != nil {
				httpx.WriteEnvelope(w, 503, false, "Authentication service unavailable", nil, nil)
				return
			}
			defer rows.Close()
			out := []Profile{}
			for rows.Next() {
				var id int64
				_ = rows.Scan(&id)
				if u, e := a.Users.FindByID(r.Context(), id); e == nil {
					out = append(out, a.profile(r, u))
				}
			}
			httpx.WriteEnvelope(w, 200, true, "Success", out, nil)
			return
		}
		var input struct {
			UserID int64  `json:"user_id"`
			Action string `json:"action"`
		}
		if json.NewDecoder(r.Body).Decode(&input) != nil || input.UserID == 0 || (input.Action != "approve" && input.Action != "reject") {
			httpx.WriteEnvelope(w, 400, false, "Provide user_id and action ('approve' or 'reject').", nil, nil)
			return
		}
		approved := input.Action == "approve"
		active := approved
		if _, err := a.Users.DB.ExecContext(r.Context(), `UPDATE authentication_user SET is_approved=$2,is_active=$3 WHERE id=$1 AND user_type='lecturer'`, input.UserID, approved, active); err != nil {
			httpx.WriteEnvelope(w, 503, false, "Authentication service unavailable", nil, nil)
			return
		}
		if mailer != nil {
			u, _ := a.Users.FindByID(r.Context(), input.UserID)
			subject := "Lecturer account update"
			body := "Your Kibegi lecturer account has been " + input.Action + "d."
			_ = mailer.SendOTP(u.Email, subject, body)
		}
		httpx.WriteEnvelope(w, 200, true, "Lecturer "+input.Action+"d and notified via email.", nil, nil)
	}))
}

var _ = io.EOF

func (a App) ProfileImageHandler() http.Handler {
	return RequireAuth(a.Tokens, http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		uid, ok := UserIDFromContext(r.Context())
		if !ok {
			httpx.WriteEnvelope(w, 401, false, "Authentication credentials were not provided.", nil, nil)
			return
		}
		switch r.Method {
		case http.MethodPost:
			if a.Storage == nil || !a.Storage.Configured() {
				httpx.WriteEnvelope(w, 503, false, "Profile image storage is unavailable", nil, nil)
				return
			}
			r.Body = http.MaxBytesReader(w, r.Body, 5*1024*1024)
			if err := r.ParseMultipartForm(5 * 1024 * 1024); err != nil {
				httpx.WriteEnvelope(w, 400, false, "Invalid profile image upload", nil, nil)
				return
			}
			file, header, err := r.FormFile("profile_image")
			if err != nil {
				file, header, err = r.FormFile("image")
			}
			if err != nil {
				httpx.WriteEnvelope(w, 400, false, "profile_image is required", nil, nil)
				return
			}
			defer file.Close()
			if header.Size <= 0 || header.Size > 5*1024*1024 {
				httpx.WriteEnvelope(w, 400, false, "Profile image must be 5MB or smaller", nil, nil)
				return
			}
			contentType := header.Header.Get("Content-Type")
			if contentType == "" {
				contentType = "application/octet-stream"
			}
			if contentType != "image/jpeg" && contentType != "image/png" && contentType != "image/gif" && contentType != "image/webp" {
				httpx.WriteEnvelope(w, 400, false, "Unsupported profile image format", nil, nil)
				return
			}
			ext := "jpg"
			switch contentType {
			case "image/png":
				ext = "png"
			case "image/gif":
				ext = "gif"
			case "image/webp":
				ext = "webp"
			}
			objectName := fmt.Sprintf("profiles/%d/profile.%s", uid, ext)
			user, err := a.Users.FindByID(r.Context(), uid)
			if err != nil {
				httpx.WriteEnvelope(w, 404, false, "User not found", nil, nil)
				return
			}
			if _, err := a.Storage.Put(r.Context(), objectName, file, header.Size, contentType); err != nil {
				httpx.WriteEnvelope(w, 503, false, "Profile image storage is unavailable", nil, nil)
				return
			}
			if user.ProfileImage != "" {
				_ = a.Storage.Remove(r.Context(), user.ProfileImage)
			}
			if _, err := a.Users.DB.ExecContext(r.Context(), `UPDATE authentication_user SET profile_image=$2 WHERE id=$1`, uid, objectName); err != nil {
				httpx.WriteEnvelope(w, 503, false, "Profile service unavailable", nil, nil)
				return
			}
			if a.Cache != nil && a.Cache.Configured() {
				_ = a.Cache.Delete(r.Context(), "api-cache:profile:v1:user:"+formatInt64(uid))
			}
			updated, _ := a.Users.FindByID(r.Context(), uid)
			httpx.WriteEnvelope(w, 200, true, "Profile image uploaded successfully", a.profile(r, updated), nil)
		case http.MethodDelete:
			user, err := a.Users.FindByID(r.Context(), uid)
			if err != nil {
				httpx.WriteEnvelope(w, 404, false, "User not found", nil, nil)
				return
			}
			if user.ProfileImage == "" {
				httpx.WriteEnvelope(w, 400, false, "No profile image to remove", nil, nil)
				return
			}
			if a.Storage != nil && a.Storage.Configured() {
				_ = a.Storage.Remove(r.Context(), user.ProfileImage)
			}
			if _, err := a.Users.DB.ExecContext(r.Context(), `UPDATE authentication_user SET profile_image=NULL WHERE id=$1`, uid); err != nil {
				httpx.WriteEnvelope(w, 503, false, "Profile service unavailable", nil, nil)
				return
			}
			if a.Cache != nil && a.Cache.Configured() {
				_ = a.Cache.Delete(r.Context(), "api-cache:profile:v1:user:"+formatInt64(uid))
			}
			httpx.WriteEnvelope(w, 200, true, "Profile image removed successfully", nil, nil)
		default:
			httpx.WriteEnvelope(w, 405, false, "method not allowed", nil, nil)
		}
	}))
}
