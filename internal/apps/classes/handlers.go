package classes

import (
	"encoding/base64"
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"strconv"
	"strings"

	"github.com/google/uuid"
	qrcode "github.com/skip2/go-qrcode"

	"github.com/troubleman96/kibegi_API/internal/apps/authentication"
	"github.com/troubleman96/kibegi_API/internal/platform/httpx"
)

type App struct {
	Repository Repository
	Auth       *authentication.TokenService
	MediaBase  string
}

type pagination struct {
	Limit  int
	Offset int
	Page   int
}

type paginated struct {
	Count    int    `json:"count"`
	Next     string `json:"next"`
	Previous string `json:"previous"`
	Results  any    `json:"results"`
}

func RequireAuth(tokens *authentication.TokenService, next http.Handler) http.Handler {
	return authentication.RequireAuth(tokens, next)
}

func (a App) ListHandler() http.Handler {
	return RequireAuth(a.Auth, http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodGet {
			w.Header().Set("Allow", http.MethodGet)
			httpx.WriteEnvelope(w, http.StatusMethodNotAllowed, false, "method not allowed", nil, nil)
			return
		}
		userID, ok := authentication.UserIDFromContext(r.Context())
		if !ok {
			httpx.WriteEnvelope(w, http.StatusUnauthorized, false, "Authentication credentials were not provided.", nil, nil)
			return
		}
		page := parsePagination(r)
		items, count, err := a.Repository.ListForUser(r.Context(), userID, "", page.Limit, page.Offset)
		if err != nil {
			httpx.WriteEnvelope(w, http.StatusServiceUnavailable, false, "Classes service unavailable", nil, nil)
			return
		}
		results := make([]map[string]any, 0, len(items))
		for _, item := range items {
			results = append(results, a.listPayload(r, item))
		}
		httpx.WriteJSON(w, http.StatusOK, paginatedResponse(r, page, count, results))
	}))
}

func (a App) CreateHandler() http.Handler {
	return RequireAuth(a.Auth, http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			w.Header().Set("Allow", http.MethodPost)
			httpx.WriteEnvelope(w, http.StatusMethodNotAllowed, false, "method not allowed", nil, nil)
			return
		}
		userID, ok := authentication.UserIDFromContext(r.Context())
		if !ok {
			httpx.WriteEnvelope(w, http.StatusUnauthorized, false, "Authentication credentials were not provided.", nil, nil)
			return
		}
		var input struct {
			Name        string `json:"name"`
			Description string `json:"description"`
			IsPublic    bool   `json:"is_public"`
		}
		if err := json.NewDecoder(r.Body).Decode(&input); err != nil || strings.TrimSpace(input.Name) == "" {
			httpx.WriteEnvelope(w, http.StatusBadRequest, false, "Invalid input", nil, nil)
			return
		}
		user, err := (authentication.UserRepository{DB: a.Repository.DB}).FindByID(r.Context(), userID)
		if err != nil {
			httpx.WriteEnvelope(w, http.StatusServiceUnavailable, false, "Classes service unavailable", nil, nil)
			return
		}
		item, err := a.Repository.Create(r.Context(), userID, user.UserType, input.Name, input.Description, input.IsPublic)
		if err != nil {
			httpx.WriteEnvelope(w, http.StatusServiceUnavailable, false, "Classes service unavailable", nil, nil)
			return
		}
		httpx.WriteEnvelope(w, http.StatusCreated, true, "Class created successfully", a.detailPayload(r, item), nil)
	}))
}

func (a App) SearchHandler() http.Handler {
	return RequireAuth(a.Auth, http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodGet {
			w.Header().Set("Allow", http.MethodGet)
			httpx.WriteEnvelope(w, http.StatusMethodNotAllowed, false, "method not allowed", nil, nil)
			return
		}
		userID, ok := authentication.UserIDFromContext(r.Context())
		if !ok {
			httpx.WriteEnvelope(w, http.StatusUnauthorized, false, "Authentication credentials were not provided.", nil, nil)
			return
		}
		page := parsePagination(r)
		items, count, err := a.Repository.ListForUser(r.Context(), userID, r.URL.Query().Get("q"), page.Limit, page.Offset)
		if err != nil {
			httpx.WriteEnvelope(w, http.StatusServiceUnavailable, false, "Classes service unavailable", nil, nil)
			return
		}
		results := make([]map[string]any, 0, len(items))
		for _, item := range items {
			results = append(results, a.listPayload(r, item))
		}
		httpx.WriteJSON(w, http.StatusOK, paginatedResponse(r, page, count, results))
	}))
}

func (a App) JoinHandler() http.Handler {
	return RequireAuth(a.Auth, http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			w.Header().Set("Allow", http.MethodPost)
			httpx.WriteEnvelope(w, http.StatusMethodNotAllowed, false, "method not allowed", nil, nil)
			return
		}
		userID, ok := authentication.UserIDFromContext(r.Context())
		if !ok {
			httpx.WriteEnvelope(w, http.StatusUnauthorized, false, "Authentication credentials were not provided.", nil, nil)
			return
		}
		var input struct {
			ClassCode string `json:"class_code"`
		}
		if err := json.NewDecoder(r.Body).Decode(&input); err != nil || strings.TrimSpace(input.ClassCode) == "" {
			httpx.WriteEnvelope(w, http.StatusBadRequest, false, "Invalid class code", nil, nil)
			return
		}
		classID, err := a.findByCode(r, strings.ToUpper(strings.TrimSpace(input.ClassCode)))
		if err != nil {
			httpx.WriteEnvelope(w, http.StatusBadRequest, false, "Invalid class code", nil, nil)
			return
		}
		item, err := a.Repository.Join(r.Context(), classID, userID)
		if errors.Is(err, ErrAlreadyMember) {
			httpx.WriteEnvelope(w, http.StatusBadRequest, false, "You are already a member of this class", nil, nil)
			return
		}
		if err != nil {
			httpx.WriteEnvelope(w, http.StatusServiceUnavailable, false, "Classes service unavailable", nil, nil)
			return
		}
		httpx.WriteEnvelope(w, http.StatusOK, true, "Successfully joined class", a.detailPayload(r, item), nil)
	}))
}

func (a App) DetailHandler() http.Handler {
	return RequireAuth(a.Auth, http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		classID, err := pathUUID(r, 3)
		if err != nil {
			httpx.WriteEnvelope(w, http.StatusNotFound, false, "Class not found", nil, nil)
			return
		}
		userID, ok := authentication.UserIDFromContext(r.Context())
		if !ok {
			httpx.WriteEnvelope(w, http.StatusUnauthorized, false, "Authentication credentials were not provided.", nil, nil)
			return
		}
		item, err := a.Repository.FindForUser(r.Context(), classID, userID)
		if errors.Is(err, ErrClassNotFound) {
			httpx.WriteEnvelope(w, http.StatusNotFound, false, "Class not found", nil, nil)
			return
		}
		if err != nil {
			httpx.WriteEnvelope(w, http.StatusServiceUnavailable, false, "Classes service unavailable", nil, nil)
			return
		}
		switch r.Method {
		case http.MethodGet:
			httpx.WriteEnvelope(w, http.StatusOK, true, "Class retrieved successfully", a.detailPayload(r, item), nil)
		case http.MethodPut, http.MethodPatch:
			if item.CreatorID != userID {
				httpx.WriteEnvelope(w, http.StatusForbidden, false, "Only the class creator can update this class", nil, nil)
				return
			}
			var input struct {
				Name        *string `json:"name"`
				Description *string `json:"description"`
				IsPublic    *bool   `json:"is_public"`
			}
			if err := json.NewDecoder(r.Body).Decode(&input); err != nil {
				httpx.WriteEnvelope(w, http.StatusBadRequest, false, "Invalid input", nil, nil)
				return
			}
			updated, err := a.Repository.Update(r.Context(), classID, userID, input.Name, input.Description, input.IsPublic)
			if err != nil {
				httpx.WriteEnvelope(w, http.StatusServiceUnavailable, false, "Classes service unavailable", nil, nil)
				return
			}
			httpx.WriteEnvelope(w, http.StatusOK, true, "Class updated successfully", a.detailPayload(r, updated), nil)
		case http.MethodDelete:
			if item.CreatorID != userID {
				httpx.WriteEnvelope(w, http.StatusForbidden, false, "Only the class creator can delete this class", nil, nil)
				return
			}
			if err := a.Repository.Delete(r.Context(), classID, userID); err != nil {
				httpx.WriteEnvelope(w, http.StatusServiceUnavailable, false, "Classes service unavailable", nil, nil)
				return
			}
			httpx.WriteEnvelope(w, http.StatusOK, true, "Class deleted successfully", nil, nil)
		default:
			w.Header().Set("Allow", "GET, PUT, PATCH, DELETE")
			httpx.WriteEnvelope(w, http.StatusMethodNotAllowed, false, "method not allowed", nil, nil)
		}
	}))
}

func (a App) MembersHandler() http.Handler {
	return RequireAuth(a.Auth, http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		classID, err := pathUUID(r, 3)
		if err != nil {
			httpx.WriteEnvelope(w, http.StatusNotFound, false, "Class not found", nil, nil)
			return
		}
		userID, ok := authentication.UserIDFromContext(r.Context())
		if !ok {
			httpx.WriteEnvelope(w, http.StatusUnauthorized, false, "Authentication credentials were not provided.", nil, nil)
			return
		}
		page := parsePagination(r)
		members, count, err := a.Repository.Members(r.Context(), classID, userID, page.Limit, page.Offset)
		if errors.Is(err, ErrClassNotFound) {
			httpx.WriteEnvelope(w, http.StatusForbidden, false, "You don't have access to this class", nil, nil)
			return
		}
		if err != nil {
			httpx.WriteEnvelope(w, http.StatusServiceUnavailable, false, "Classes service unavailable", nil, nil)
			return
		}
		httpx.WriteJSON(w, http.StatusOK, paginatedResponse(r, page, count, members))
	}))
}

func (a App) LeaveHandler() http.Handler {
	return RequireAuth(a.Auth, http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			w.Header().Set("Allow", http.MethodPost)
			httpx.WriteEnvelope(w, http.StatusMethodNotAllowed, false, "method not allowed", nil, nil)
			return
		}
		classID, err := pathUUID(r, 3)
		if err != nil {
			httpx.WriteEnvelope(w, http.StatusNotFound, false, "Class not found", nil, nil)
			return
		}
		userID, ok := authentication.UserIDFromContext(r.Context())
		if !ok {
			httpx.WriteEnvelope(w, http.StatusUnauthorized, false, "Authentication credentials were not provided.", nil, nil)
			return
		}
		err = a.Repository.Leave(r.Context(), classID, userID)
		switch {
		case errors.Is(err, ErrClassNotFound):
			httpx.WriteEnvelope(w, http.StatusNotFound, false, "Class not found", nil, nil)
		case errors.Is(err, ErrCreatorCannotLeave):
			httpx.WriteEnvelope(w, http.StatusBadRequest, false, "Class creator cannot leave the class", nil, nil)
		case errors.Is(err, ErrNotMember):
			httpx.WriteEnvelope(w, http.StatusBadRequest, false, "You are not a member of this class", nil, nil)
		case err != nil:
			httpx.WriteEnvelope(w, http.StatusServiceUnavailable, false, "Classes service unavailable", nil, nil)
		default:
			httpx.WriteEnvelope(w, http.StatusOK, true, "Successfully left the class", nil, nil)
		}
	}))
}

func (a App) findByCode(r *http.Request, code string) (uuid.UUID, error) {
	if a.Repository.DB == nil {
		return uuid.Nil, errors.New("database is not configured")
	}
	var id uuid.UUID
	err := a.Repository.DB.QueryRowContext(r.Context(), `SELECT id FROM classes_class WHERE class_code = $1`, code).Scan(&id)
	return id, err
}

func (a App) listPayload(r *http.Request, item Class) map[string]any {
	return map[string]any{
		"id": item.ID, "name": item.Name, "class_code": item.ClassCode, "is_public": item.IsPublic,
		"is_verified": item.IsVerified, "creator_name": item.CreatorName, "creator_type": item.CreatorType,
		"creator_profile_image": item.CreatorImage, "creator_profile_image_url": a.mediaURL(r, item.CreatorImage),
		"member_count": item.MemberCount, "file_count": item.FileCount, "created_at": item.CreatedAt,
	}
}

func (a App) detailPayload(r *http.Request, item Class) map[string]any {
	payload := map[string]any{
		"id": item.ID, "name": item.Name, "description": item.Description, "class_code": item.ClassCode,
		"is_public": item.IsPublic, "is_verified": item.IsVerified, "creator": item.CreatorID,
		"creator_name": item.CreatorName, "creator_type": item.CreatorType, "creator_profile_image": item.CreatorImage,
		"creator_profile_image_url": a.mediaURL(r, item.CreatorImage), "member_count": item.MemberCount,
		"is_member": item.IsMember, "user_role": item.UserRole, "join_qr_payload": map[string]any{
			"type": "class_join", "class_code": item.ClassCode, "class_name": item.Name, "join_endpoint": "/api/v1/classes/join/",
		}, "join_qr_value": item.ClassCode, "join_qr_image": qrDataURL(item.ClassCode, item.Name),
		"created_at": item.CreatedAt, "updated_at": item.UpdatedAt,
		"uploads_summary": map[string]any{"total_uploads": item.FileCount, "uploads_by_type": map[string]int{}, "total_size_bytes": 0, "total_size_mb": 0, "lecturers_with_uploads": 0, "active_contributors": 0},
		"recent_uploads":  []any{}, "uploader_stats": []any{},
	}
	return payload
}

func qrDataURL(code, name string) any {
	payload := fmt.Sprintf(`{"type":"class_join","class_code":%q,"class_name":%q,"join_endpoint":"/api/v1/classes/join/"}`, code, name)
	image, err := qrcode.Encode(payload, qrcode.Medium, 256)
	if err != nil {
		return nil
	}
	return "data:image/png;base64," + base64.StdEncoding.EncodeToString(image)
}

func (a App) mediaURL(r *http.Request, image any) any {
	path, ok := image.(string)
	if !ok || path == "" {
		return nil
	}
	if strings.HasPrefix(path, "http://") || strings.HasPrefix(path, "https://") {
		return path
	}
	if a.MediaBase != "" {
		return strings.TrimRight(a.MediaBase, "/") + "/" + strings.TrimLeft(path, "/")
	}
	scheme := "http"
	if r.TLS != nil {
		scheme = "https"
	}
	return scheme + "://" + r.Host + "/media/" + strings.TrimLeft(path, "/")
}

func parsePagination(r *http.Request) pagination {
	page := parsePositive(r.URL.Query().Get("page"), 1)
	limit := parsePositive(r.URL.Query().Get("page_size"), 20)
	if limit > 100 {
		limit = 100
	}
	return pagination{Limit: limit, Offset: (page - 1) * limit, Page: page}
}

func paginatedResponse(r *http.Request, page pagination, count int, results any) paginated {
	next := ""
	previous := ""
	if page.Offset+page.Limit < count {
		next = pageURL(r, page.Page+1)
	}
	if page.Page > 1 {
		previous = pageURL(r, page.Page-1)
	}
	return paginated{Count: count, Next: next, Previous: previous, Results: results}
}

func pageURL(r *http.Request, page int) string {
	query := r.URL.Query()
	query.Set("page", strconv.Itoa(page))
	return r.URL.Path + "?" + query.Encode()
}

func parsePositive(value string, fallback int) int {
	parsed, err := strconv.Atoi(value)
	if err != nil || parsed <= 0 {
		return fallback
	}
	return parsed
}

func pathUUID(r *http.Request, index int) (uuid.UUID, error) {
	parts := strings.Split(strings.Trim(r.URL.Path, "/"), "/")
	if index >= len(parts) {
		return uuid.Nil, errors.New("missing UUID")
	}
	return uuid.Parse(parts[index])
}

func (a App) PathHandler() http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		rest := strings.Trim(strings.TrimPrefix(r.URL.Path, "/api/v1/classes/"), "/")
		if rest == "" {
			if r.Method == http.MethodGet {
				a.ListHandler().ServeHTTP(w, r)
				return
			}
			if r.Method == http.MethodPost {
				a.CreateHandler().ServeHTTP(w, r)
				return
			}
			w.Header().Set("Allow", "GET, POST")
			httpx.WriteEnvelope(w, http.StatusMethodNotAllowed, false, "method not allowed", nil, nil)
			return
		}
		parts := strings.Split(rest, "/")
		if len(parts) == 1 && parts[0] == "search" {
			a.SearchHandler().ServeHTTP(w, r)
			return
		}
		if len(parts) == 1 && parts[0] == "join" {
			a.JoinHandler().ServeHTTP(w, r)
			return
		}
		if len(parts) == 1 {
			a.DetailHandler().ServeHTTP(w, r)
			return
		}
		if len(parts) == 2 {
			switch parts[1] {
			case "members":
				a.MembersHandler().ServeHTTP(w, r)
				return
			case "leave":
				a.LeaveHandler().ServeHTTP(w, r)
				return
			}
		}
		httpx.WriteEnvelope(w, http.StatusNotFound, false, "Not found", nil, nil)
	})
}
