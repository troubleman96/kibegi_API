package sharing

import (
	"encoding/json"
	"errors"
	"io"
	"mime"
	"net/http"
	"path/filepath"
	"strconv"
	"strings"

	"github.com/google/uuid"

	"github.com/troubleman96/kibegi_API/internal/apps/authentication"
	"github.com/troubleman96/kibegi_API/internal/platform/httpx"
	"github.com/troubleman96/kibegi_API/internal/platform/storage"
)

type App struct {
	Repository Repository
	Auth       *authentication.TokenService
	Storage    *storage.ObjectStorage
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

func (a App) PathHandler() http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		rest := strings.Trim(strings.TrimPrefix(r.URL.Path, "/api/v1/sharing/"), "/")
		if rest == "" {
			if r.Method == http.MethodPost {
				a.create(w, r)
				return
			}
			httpx.WriteEnvelope(w, http.StatusMethodNotAllowed, false, "method not allowed", nil, nil)
			return
		}
		parts := strings.Split(rest, "/")
		switch {
		case len(parts) == 1 && parts[0] == "bulk":
			a.bulk(w, r)
		case len(parts) == 1 && parts[0] == "requests":
			a.list(w, r, "requests")
		case len(parts) == 1 && parts[0] == "shared-with-me":
			a.list(w, r, "received")
		case len(parts) == 1 && parts[0] == "my-shares":
			a.list(w, r, "sent")
		case len(parts) == 2 && parts[1] == "accept":
			a.transition(w, r, parts[0], "accepted")
		case len(parts) == 2 && parts[1] == "reject":
			a.transition(w, r, parts[0], "rejected")
		case len(parts) == 2 && parts[1] == "download":
			a.download(w, r, parts[0])
		case len(parts) == 1:
			a.detail(w, r, parts[0])
		default:
			httpx.WriteEnvelope(w, http.StatusNotFound, false, "Not found", nil, nil)
		}
	})
}

func (a App) create(w http.ResponseWriter, r *http.Request) {
	userID, ok := authentication.UserIDFromContext(r.Context())
	if !ok {
		httpx.WriteEnvelope(w, http.StatusUnauthorized, false, "Authentication credentials were not provided.", nil, nil)
		return
	}
	var input struct {
		FileCode     string `json:"file_code"`
		SharedWithID int64  `json:"shared_with_id"`
		Message      string `json:"message"`
	}
	if err := json.NewDecoder(r.Body).Decode(&input); err != nil {
		httpx.WriteEnvelope(w, http.StatusBadRequest, false, "Invalid input", nil, nil)
		return
	}
	share, err := a.Repository.Create(r.Context(), input.FileCode, userID, input.SharedWithID, input.Message)
	if errors.Is(err, ErrShareNotFound) {
		httpx.WriteEnvelope(w, http.StatusBadRequest, false, "File not found or has been deleted", nil, nil)
		return
	}
	if errors.Is(err, ErrDuplicate) {
		httpx.WriteEnvelope(w, http.StatusBadRequest, false, "File already shared with this user", nil, nil)
		return
	}
	if errors.Is(err, ErrShareDenied) {
		httpx.WriteEnvelope(w, http.StatusBadRequest, false, "You don't have permission to share this file", nil, nil)
		return
	}
	if err != nil {
		httpx.WriteEnvelope(w, http.StatusServiceUnavailable, false, "Sharing service unavailable", nil, nil)
		return
	}
	httpx.WriteEnvelope(w, http.StatusCreated, true, "File shared successfully. Recipient will be notified.", a.detailPayload(r, share), nil)
}

func (a App) bulk(w http.ResponseWriter, r *http.Request) {
	userID, ok := authentication.UserIDFromContext(r.Context())
	if !ok {
		httpx.WriteEnvelope(w, http.StatusUnauthorized, false, "Authentication credentials were not provided.", nil, nil)
		return
	}
	var input struct {
		FileCode string  `json:"file_code"`
		UserIDs  []int64 `json:"user_ids"`
		Message  string  `json:"message"`
	}
	if err := json.NewDecoder(r.Body).Decode(&input); err != nil || len(input.UserIDs) == 0 || len(input.UserIDs) > 50 {
		httpx.WriteEnvelope(w, http.StatusBadRequest, false, "Invalid bulk share request", nil, nil)
		return
	}
	for _, recipient := range input.UserIDs {
		_, _ = a.Repository.Create(r.Context(), input.FileCode, userID, recipient, input.Message)
	}
	httpx.WriteEnvelope(w, http.StatusAccepted, true, "Bulk sharing started", map[string]any{"status": "processing", "user_count": len(input.UserIDs), "file_code": strings.ToUpper(input.FileCode)}, nil)
}

func (a App) list(w http.ResponseWriter, r *http.Request, mode string) {
	userID, ok := authentication.UserIDFromContext(r.Context())
	if !ok {
		httpx.WriteEnvelope(w, http.StatusUnauthorized, false, "Authentication credentials were not provided.", nil, nil)
		return
	}
	page := parsePagination(r)
	items, count, err := a.Repository.List(r.Context(), userID, mode, r.URL.Query().Get("status"), page.Limit, page.Offset)
	if err != nil {
		httpx.WriteEnvelope(w, http.StatusServiceUnavailable, false, "Sharing service unavailable", nil, nil)
		return
	}
	results := make([]map[string]any, 0, len(items))
	for _, item := range items {
		results = append(results, a.listPayload(r, item))
	}
	httpx.WriteJSON(w, http.StatusOK, buildPage(r, page, count, results))
}

func (a App) transition(w http.ResponseWriter, r *http.Request, rawID, status string) {
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
	id, err := uuid.Parse(rawID)
	if err != nil {
		httpx.WriteEnvelope(w, http.StatusNotFound, false, "Share not found", nil, nil)
		return
	}
	share, err := a.Repository.Transition(r.Context(), id, userID, status)
	if errors.Is(err, ErrShareNotFound) {
		httpx.WriteEnvelope(w, http.StatusNotFound, false, "Share not found", nil, nil)
		return
	}
	if err != nil {
		httpx.WriteEnvelope(w, http.StatusServiceUnavailable, false, "Sharing service unavailable", nil, nil)
		return
	}
	message := "Share accepted successfully"
	if status == "rejected" {
		message = "Share rejected successfully"
	}
	httpx.WriteEnvelope(w, http.StatusOK, true, message, a.detailPayload(r, share), nil)
}

func (a App) detail(w http.ResponseWriter, r *http.Request, rawID string) {
	userID, ok := authentication.UserIDFromContext(r.Context())
	if !ok {
		httpx.WriteEnvelope(w, http.StatusUnauthorized, false, "Authentication credentials were not provided.", nil, nil)
		return
	}
	id, err := uuid.Parse(rawID)
	if err != nil {
		httpx.WriteEnvelope(w, http.StatusNotFound, false, "Share not found", nil, nil)
		return
	}
	share, err := a.Repository.Find(r.Context(), id, userID)
	if errors.Is(err, ErrShareNotFound) {
		httpx.WriteEnvelope(w, http.StatusNotFound, false, "Share not found", nil, nil)
		return
	}
	if err != nil {
		httpx.WriteEnvelope(w, http.StatusServiceUnavailable, false, "Sharing service unavailable", nil, nil)
		return
	}
	httpx.WriteEnvelope(w, http.StatusOK, true, "Share retrieved successfully", a.detailPayload(r, share), nil)
}

func (a App) download(w http.ResponseWriter, r *http.Request, rawID string) {
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
	id, err := uuid.Parse(rawID)
	if err != nil {
		httpx.WriteEnvelope(w, http.StatusNotFound, false, "Share not found", nil, nil)
		return
	}
	share, err := a.Repository.Find(r.Context(), id, userID)
	if errors.Is(err, ErrShareNotFound) || share.SharedWith != userID || share.Status != "accepted" || share.IsDeleted {
		httpx.WriteEnvelope(w, http.StatusForbidden, false, "You don't have permission to download this file", nil, nil)
		return
	}
	if err != nil {
		httpx.WriteEnvelope(w, http.StatusServiceUnavailable, false, "Sharing service unavailable", nil, nil)
		return
	}
	if a.Storage == nil || !a.Storage.Configured() {
		httpx.WriteEnvelope(w, http.StatusServiceUnavailable, false, "File storage is not configured", nil, nil)
		return
	}
	object, err := a.Storage.Open(r.Context(), share.ObjectName)
	if err != nil {
		httpx.WriteEnvelope(w, http.StatusNotFound, false, "File not found in storage", nil, nil)
		return
	}
	defer object.Close()
	contentType := mime.TypeByExtension(filepath.Ext(share.FileName))
	if contentType == "" {
		contentType = "application/octet-stream"
	}
	w.Header().Set("Content-Type", contentType)
	w.Header().Set("Content-Disposition", `attachment; filename="`+strings.ReplaceAll(share.FileName, `"`, "")+`"`)
	w.Header().Set("X-Content-Type-Options", "nosniff")
	w.Header().Set("Cache-Control", "private, max-age=3600")
	_, _ = io.Copy(w, object)
}

func (a App) listPayload(r *http.Request, item Share) map[string]any {
	return map[string]any{
		"id": item.ID, "file_name": item.FileName, "file_type": item.FileType, "file_code": item.FileCode,
		"shared_by_name": item.SharedByName, "shared_by_profile_image": item.SharedByImage, "shared_by_profile_image_url": a.profileURL(r, item.SharedByImage),
		"shared_with_name": item.SharedWithName, "shared_with_profile_image": item.SharedWithImage, "shared_with_profile_image_url": a.profileURL(r, item.SharedWithImage),
		"status": item.Status, "message": item.Message, "shared_at": item.SharedAt,
	}
}

func (a App) detailPayload(r *http.Request, item Share) map[string]any {
	payload := a.listPayload(r, item)
	payload["upload"] = map[string]any{"id": item.UploadID, "file_name": item.FileName, "file_type": item.FileType, "file_code": item.FileCode, "file": item.ObjectName, "file_url": a.mediaURL(r, item.ObjectName), "is_deleted": item.IsDeleted}
	payload["shared_by"] = item.SharedBy
	payload["shared_by_email"] = item.SharedByEmail
	payload["shared_with"] = item.SharedWith
	payload["shared_with_email"] = item.SharedWithEmail
	payload["accepted_at"] = item.AcceptedAt
	payload["rejected_at"] = item.RejectedAt
	payload["can_access"] = item.Status == "accepted" && !item.IsDeleted && item.SharedWith != 0
	return payload
}

func (a App) profileURL(r *http.Request, value any) any {
	path, ok := value.(string)
	if !ok || path == "" {
		return nil
	}
	return a.mediaURL(r, path)
}

func (a App) mediaURL(r *http.Request, objectName string) string {
	if a.MediaBase != "" {
		return strings.TrimRight(a.MediaBase, "/") + "/" + strings.TrimLeft(objectName, "/")
	}
	scheme := "http"
	if r.TLS != nil {
		scheme = "https"
	}
	return scheme + "://" + r.Host + "/media/" + strings.TrimLeft(objectName, "/")
}

func (a App) buildPage(r *http.Request, page pagination, count int, results any) paginated {
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

func buildPage(r *http.Request, page pagination, count int, results any) paginated {
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

func parsePagination(r *http.Request) pagination {
	page := positive(r.URL.Query().Get("page"), 1)
	limit := positive(r.URL.Query().Get("page_size"), 20)
	if limit > 100 {
		limit = 100
	}
	return pagination{Limit: limit, Offset: (page - 1) * limit, Page: page}
}

func pageURL(r *http.Request, page int) string {
	query := r.URL.Query()
	query.Set("page", strconv.Itoa(page))
	return r.URL.Path + "?" + query.Encode()
}

func positive(value string, fallback int) int {
	parsed, err := strconv.Atoi(value)
	if err != nil || parsed <= 0 {
		return fallback
	}
	return parsed
}
