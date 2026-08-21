package authentication

import (
	"context"
	"encoding/json"
	"errors"
	"net/http"
	"strconv"
	"strings"
	"time"

	"github.com/troubleman96/kibegi_API/internal/platform/cache"
	"github.com/troubleman96/kibegi_API/internal/platform/httpx"
)

const profileCacheTTL = 120 * time.Second

type contextKey string

const userIDKey contextKey = "kibegi.authentication.user_id"

type App struct {
	Users     UserRepository
	Tokens    *TokenService
	Cache     *cache.Redis
	MediaBase string
}

type loginRequest struct {
	Email    string `json:"email"`
	Password string `json:"password"`
}

type loginData struct {
	User   Profile   `json:"user"`
	Tokens tokenPair `json:"tokens"`
}

type tokenPair struct {
	Refresh string `json:"refresh"`
	Access  string `json:"access"`
}

type Profile struct {
	ID              int64  `json:"id"`
	Email           string `json:"email"`
	Username        string `json:"username"`
	UserType        string `json:"user_type"`
	IsApproved      bool   `json:"is_approved"`
	University      string `json:"university"`
	PhoneNumber     string `json:"phone_number"`
	PhoneVerified   bool   `json:"phone_verified"`
	ProfileImage    any    `json:"profile_image"`
	ProfileImageURL any    `json:"profile_image_url"`
	DateJoined      string `json:"date_joined"`
}

func (a App) LoginHandler() http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			w.Header().Set("Allow", http.MethodPost)
			httpx.WriteEnvelope(w, http.StatusMethodNotAllowed, false, "method not allowed", nil, nil)
			return
		}

		var input loginRequest
		if err := json.NewDecoder(r.Body).Decode(&input); err != nil || strings.TrimSpace(input.Email) == "" || input.Password == "" {
			httpx.WriteEnvelope(w, http.StatusBadRequest, false, "Invalid input", nil, map[string]string{"detail": "email and password are required"})
			return
		}

		user, err := a.Users.FindByEmail(r.Context(), input.Email)
		if errors.Is(err, ErrUserNotFound) {
			httpx.WriteEnvelope(w, http.StatusUnauthorized, false, "Invalid email or password", nil, nil)
			return
		}
		if err != nil {
			httpx.WriteEnvelope(w, http.StatusServiceUnavailable, false, "Authentication service unavailable", nil, nil)
			return
		}
		valid, err := VerifyDjangoPassword(user.Password, input.Password)
		if err != nil || !valid || !user.IsActive {
			httpx.WriteEnvelope(w, http.StatusUnauthorized, false, "Invalid email or password", nil, nil)
			return
		}
		if user.UserType == "lecturer" && !user.IsApproved {
			httpx.WriteEnvelope(w, http.StatusForbidden, false, "Your lecturer account is pending admin approval. You will be notified once approved.", nil, nil)
			return
		}

		refresh, access, err := a.Tokens.IssuePair(user.ID, time.Now().UTC())
		if err != nil {
			httpx.WriteEnvelope(w, http.StatusServiceUnavailable, false, "Authentication service unavailable", nil, nil)
			return
		}
		httpx.WriteEnvelope(w, http.StatusOK, true, "Login successful", loginData{
			User:   a.profile(r, user),
			Tokens: tokenPair{Refresh: refresh, Access: access},
		}, nil)
	})
}

func (a App) ProfileHandler() http.Handler {
	return RequireAuth(a.Tokens, http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		userID, ok := UserIDFromContext(r.Context())
		if !ok {
			httpx.WriteEnvelope(w, http.StatusUnauthorized, false, "Authentication credentials were not provided.", nil, nil)
			return
		}

		if r.Method == http.MethodGet {
			a.getProfile(w, r, userID)
			return
		}
		if r.Method == http.MethodPut || r.Method == http.MethodPatch {
			a.updateProfile(w, r, userID)
			return
		}
		w.Header().Set("Allow", "GET, PUT, PATCH")
		httpx.WriteEnvelope(w, http.StatusMethodNotAllowed, false, "method not allowed", nil, nil)
	}))
}

func (a App) getProfile(w http.ResponseWriter, r *http.Request, userID int64) {
	cacheKey := "api-cache:profile:v1:user:" + formatInt64(userID)
	var cached httpx.Envelope
	if a.Cache != nil && a.Cache.Configured() {
		if err := a.Cache.Get(r.Context(), cacheKey, &cached); err == nil {
			httpx.WriteJSON(w, http.StatusOK, cached)
			return
		}
	}

	user, err := a.Users.FindByID(r.Context(), userID)
	if errors.Is(err, ErrUserNotFound) {
		httpx.WriteEnvelope(w, http.StatusNotFound, false, "User not found", nil, nil)
		return
	}
	if err != nil {
		httpx.WriteEnvelope(w, http.StatusServiceUnavailable, false, "Profile service unavailable", nil, nil)
		return
	}

	response := httpx.Envelope{Success: true, Message: "Success", Data: a.profile(r, user), Errors: nil}
	if a.Cache != nil && a.Cache.Configured() {
		_ = a.Cache.Set(r.Context(), cacheKey, response, profileCacheTTL)
	}
	httpx.WriteJSON(w, http.StatusOK, response)
}

func (a App) updateProfile(w http.ResponseWriter, r *http.Request, userID int64) {
	var input struct {
		Username    *string `json:"username"`
		University  *string `json:"university"`
		PhoneNumber *string `json:"phone_number"`
	}
	if err := json.NewDecoder(r.Body).Decode(&input); err != nil {
		httpx.WriteEnvelope(w, http.StatusBadRequest, false, "Invalid input", nil, nil)
		return
	}

	user, err := a.Users.FindByID(r.Context(), userID)
	if errors.Is(err, ErrUserNotFound) {
		httpx.WriteEnvelope(w, http.StatusNotFound, false, "User not found", nil, nil)
		return
	}
	if err != nil {
		httpx.WriteEnvelope(w, http.StatusServiceUnavailable, false, "Profile service unavailable", nil, nil)
		return
	}
	fullName := user.FullName
	university := user.University
	phoneNumber := user.PhoneNumber
	if input.Username != nil {
		fullName = strings.TrimSpace(*input.Username)
	}
	if input.University != nil {
		university = *input.University
	}
	if input.PhoneNumber != nil {
		phoneNumber = *input.PhoneNumber
	}
	if fullName == "" {
		httpx.WriteEnvelope(w, http.StatusBadRequest, false, "Invalid input", nil, map[string]string{"username": "This field may not be blank."})
		return
	}

	updated, err := a.Users.UpdateProfile(r.Context(), userID, fullName, university, phoneNumber)
	if err != nil {
		httpx.WriteEnvelope(w, http.StatusServiceUnavailable, false, "Profile service unavailable", nil, nil)
		return
	}
	if a.Cache != nil && a.Cache.Configured() {
		_ = a.Cache.Delete(r.Context(), "api-cache:profile:v1:user:"+formatInt64(userID))
	}
	httpx.WriteEnvelope(w, http.StatusOK, true, "Profile updated", a.profile(r, updated), nil)
}

func (a App) profile(r *http.Request, user User) Profile {
	var image any
	var imageURL any
	if user.ProfileImage != "" {
		image = user.ProfileImage
		imageURL = a.absoluteMediaURL(r, user.ProfileImage)
	}
	return Profile{
		ID:              user.ID,
		Email:           user.Email,
		Username:        user.FullName,
		UserType:        user.UserType,
		IsApproved:      user.IsApproved,
		University:      user.University,
		PhoneNumber:     user.PhoneNumber,
		PhoneVerified:   user.PhoneVerified,
		ProfileImage:    image,
		ProfileImageURL: imageURL,
		DateJoined:      user.DateJoined.UTC().Format(time.RFC3339Nano),
	}
}

func (a App) absoluteMediaURL(r *http.Request, imagePath string) string {
	if strings.HasPrefix(imagePath, "http://") || strings.HasPrefix(imagePath, "https://") {
		return imagePath
	}
	if a.MediaBase != "" {
		return strings.TrimRight(a.MediaBase, "/") + "/" + strings.TrimLeft(imagePath, "/")
	}
	if strings.HasPrefix(imagePath, "/") {
		return r.URL.Scheme + "://" + r.Host + imagePath
	}
	scheme := "http"
	if r.TLS != nil {
		scheme = "https"
	}
	return scheme + "://" + r.Host + "/media/" + strings.TrimLeft(imagePath, "/")
}

func formatInt64(value int64) string {
	return strconv.FormatInt(value, 10)
}

type refreshRequest struct {
	Refresh string `json:"refresh"`
}

func (a App) TokenRefreshHandler() http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			w.Header().Set("Allow", http.MethodPost)
			httpx.WriteEnvelope(w, http.StatusMethodNotAllowed, false, "method not allowed", nil, nil)
			return
		}
		var input refreshRequest
		if err := json.NewDecoder(r.Body).Decode(&input); err != nil || strings.TrimSpace(input.Refresh) == "" {
			httpx.WriteJSON(w, http.StatusBadRequest, map[string]string{"detail": "refresh is required"})
			return
		}
		claims, err := a.Tokens.ParseRefresh(input.Refresh)
		if err != nil || a.isRevoked(r.Context(), claims.JTI) {
			httpx.WriteJSON(w, http.StatusUnauthorized, map[string]string{"detail": "Token is invalid or expired"})
			return
		}
		refresh, access, oldClaims, err := a.Tokens.RotateRefresh(input.Refresh, time.Now().UTC())
		if err != nil {
			httpx.WriteJSON(w, http.StatusUnauthorized, map[string]string{"detail": "Token is invalid or expired"})
			return
		}
		if err := a.revoke(r.Context(), oldClaims); err != nil {
			httpx.WriteJSON(w, http.StatusServiceUnavailable, map[string]string{"detail": "Token service unavailable"})
			return
		}
		httpx.WriteJSON(w, http.StatusOK, tokenPair{Refresh: refresh, Access: access})
	})
}

func (a App) LogoutHandler() http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			w.Header().Set("Allow", http.MethodPost)
			httpx.WriteEnvelope(w, http.StatusMethodNotAllowed, false, "method not allowed", nil, nil)
			return
		}
		var input refreshRequest
		if err := json.NewDecoder(r.Body).Decode(&input); err != nil || strings.TrimSpace(input.Refresh) == "" {
			httpx.WriteEnvelope(w, http.StatusBadRequest, false, "Invalid token", nil, nil)
			return
		}
		claims, err := a.Tokens.ParseRefresh(input.Refresh)
		if err != nil || a.isRevoked(r.Context(), claims.JTI) {
			httpx.WriteEnvelope(w, http.StatusBadRequest, false, "Invalid token or already blacklisted", nil, nil)
			return
		}
		if err := a.revoke(r.Context(), claims); err != nil {
			httpx.WriteEnvelope(w, http.StatusServiceUnavailable, false, "Token service unavailable", nil, nil)
			return
		}
		httpx.WriteEnvelope(w, http.StatusOK, true, "Successfully logged out", nil, nil)
	})
}

func (a App) revoke(ctx context.Context, claims TokenClaims) error {
	if a.Cache == nil || !a.Cache.Configured() {
		return errors.New("redis is required for refresh token revocation")
	}
	ttl := time.Until(claims.ExpiresAt)
	if ttl <= 0 {
		return nil
	}
	return a.Cache.Set(ctx, "auth:blacklist:"+claims.JTI, true, ttl)
}

func (a App) isRevoked(ctx context.Context, jti string) bool {
	if a.Cache == nil || !a.Cache.Configured() {
		return false
	}
	var revoked bool
	if err := a.Cache.Get(ctx, "auth:blacklist:"+jti, &revoked); err != nil {
		return false
	}
	return revoked
}

func (a App) ChangePasswordHandler() http.Handler {
	return RequireAuth(a.Tokens, http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			w.Header().Set("Allow", http.MethodPost)
			httpx.WriteEnvelope(w, http.StatusMethodNotAllowed, false, "method not allowed", nil, nil)
			return
		}
		userID, ok := UserIDFromContext(r.Context())
		if !ok {
			httpx.WriteEnvelope(w, http.StatusUnauthorized, false, "Authentication credentials were not provided.", nil, nil)
			return
		}
		var input struct {
			CurrentPassword string `json:"current_password"`
			NewPassword     string `json:"new_password"`
			ConfirmPassword string `json:"confirm_password"`
		}
		if err := json.NewDecoder(r.Body).Decode(&input); err != nil {
			httpx.WriteEnvelope(w, http.StatusBadRequest, false, "Invalid input", nil, nil)
			return
		}
		if input.NewPassword != input.ConfirmPassword {
			httpx.WriteEnvelope(w, http.StatusBadRequest, false, "Password fields didn't match.", nil, nil)
			return
		}
		if err := validatePassword(input.NewPassword); err != nil {
			httpx.WriteEnvelope(w, http.StatusBadRequest, false, err.Error(), nil, nil)
			return
		}
		user, err := a.Users.FindByID(r.Context(), userID)
		if errors.Is(err, ErrUserNotFound) {
			httpx.WriteEnvelope(w, http.StatusNotFound, false, "User not found", nil, nil)
			return
		}
		if err != nil {
			httpx.WriteEnvelope(w, http.StatusServiceUnavailable, false, "Password service unavailable", nil, nil)
			return
		}
		valid, err := VerifyDjangoPassword(user.Password, input.CurrentPassword)
		if err != nil || !valid {
			httpx.WriteEnvelope(w, http.StatusBadRequest, false, "Current password is incorrect", nil, nil)
			return
		}
		encoded, err := EncodeDjangoPassword(input.NewPassword, 870000)
		if err != nil {
			httpx.WriteEnvelope(w, http.StatusServiceUnavailable, false, "Password service unavailable", nil, nil)
			return
		}
		if err := a.Users.UpdatePassword(r.Context(), userID, encoded); err != nil {
			httpx.WriteEnvelope(w, http.StatusServiceUnavailable, false, "Password service unavailable", nil, nil)
			return
		}
		if a.Cache != nil && a.Cache.Configured() {
			_ = a.Cache.Delete(r.Context(), "api-cache:profile:v1:user:"+formatInt64(userID))
		}
		httpx.WriteEnvelope(w, http.StatusOK, true, "Password changed successfully", nil, nil)
	}))
}

func validatePassword(password string) error {
	if len([]rune(password)) < 8 {
		return errors.New("This password is too short. It must contain at least 8 characters.")
	}
	allDigits := true
	for _, character := range password {
		if character < '0' || character > '9' {
			allDigits = false
			break
		}
	}
	if allDigits {
		return errors.New("This password is entirely numeric.")
	}
	return nil
}
