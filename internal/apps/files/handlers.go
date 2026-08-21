package files

import (
	"errors"
	"net/http"
	"strings"

	"github.com/google/uuid"
	"github.com/troubleman96/kibegi_API/internal/apps/authentication"
	"github.com/troubleman96/kibegi_API/internal/apps/uploads"
	"github.com/troubleman96/kibegi_API/internal/platform/cache"
	"github.com/troubleman96/kibegi_API/internal/platform/httpx"
	"github.com/troubleman96/kibegi_API/internal/platform/storage"
)

type App struct {
	Uploads   uploads.Repository
	Auth      *authentication.TokenService
	Cache     *cache.Redis
	Storage   *storage.ObjectStorage
	MediaBase string
}

func (a App) PathHandler() http.Handler {
	return authentication.RequireAuth(a.Auth, http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		uid, ok := authentication.UserIDFromContext(r.Context())
		if !ok {
			httpx.WriteEnvelope(w, 401, false, "Authentication credentials were not provided.", nil, nil)
			return
		}
		rest := strings.Trim(strings.TrimPrefix(r.URL.Path, "/api/v1/files/"), "/")
		parts := strings.Split(rest, "/")
		switch {
		case rest == "all" && r.Method == http.MethodGet:
			a.list(w, r, uid, "all")
		case rest == "my-uploads" && r.Method == http.MethodGet:
			a.list(w, r, uid, "own")
		case rest == "shared-with-me" && r.Method == http.MethodGet:
			a.list(w, r, uid, "shared")
		case rest == "deleted" && r.Method == http.MethodGet:
			a.list(w, r, uid, "trash")
		case len(parts) == 2 && parts[1] == "restore" && r.Method == http.MethodPost:
			a.restore(w, r, uid, parts[0])
		case len(parts) == 2 && parts[1] == "permanent-delete" && r.Method == http.MethodDelete:
			a.permanentDelete(w, r, uid, parts[0])
		case len(parts) == 1 && parts[0] != "" && r.Method == http.MethodGet:
			a.detail(w, r, uid, parts[0])
		case len(parts) == 1 && parts[0] != "" && r.Method == http.MethodGet:
			a.detail(w, r, uid, parts[0])
		default:
			httpx.WriteEnvelope(w, 404, false, "Not found", nil, nil)
		}
	}))
}
func (a App) list(w http.ResponseWriter, r *http.Request, uid int64, mode string) {
	user, err := (authentication.UserRepository{DB: a.Uploads.DB}).FindByID(r.Context(), uid)
	if err != nil {
		httpx.WriteEnvelope(w, 503, false, "Files service unavailable", nil, nil)
		return
	}
	items, _, err := a.Uploads.List(r.Context(), uid, user.UserType, "", "", mode, 100, 0)
	if err != nil {
		httpx.WriteEnvelope(w, 503, false, "Files service unavailable", nil, nil)
		return
	}
	out := make([]map[string]any, 0, len(items))
	for _, x := range items {
		out = append(out, a.payload(r, x, mode == "shared"))
	}
	httpx.WriteEnvelope(w, 200, true, "Retrieved "+itoa(len(out))+" files", out, nil)
}
func (a App) detail(w http.ResponseWriter, r *http.Request, uid int64, code string) {
	x, err := a.Uploads.FindByCode(r.Context(), uid, code, false)
	if errors.Is(err, uploads.ErrUploadNotFound) {
		httpx.WriteEnvelope(w, 404, false, "File not found", nil, nil)
		return
	}
	if err != nil {
		httpx.WriteEnvelope(w, 503, false, "Files service unavailable", nil, nil)
		return
	}
	httpx.WriteEnvelope(w, 200, true, "File retrieved successfully", a.payload(r, x, false), nil)
}
func (a App) restore(w http.ResponseWriter, r *http.Request, uid int64, raw string) {
	id, err := uuid.Parse(raw)
	if err != nil {
		httpx.WriteEnvelope(w, 404, false, "File not found", nil, nil)
		return
	}
	x, err := a.Uploads.Restore(r.Context(), uid, id)
	if errors.Is(err, uploads.ErrUploadNotFound) {
		httpx.WriteEnvelope(w, 404, false, "File not found", nil, nil)
		return
	}
	if err != nil {
		httpx.WriteEnvelope(w, 503, false, "Files service unavailable", nil, nil)
		return
	}
	httpx.WriteEnvelope(w, 200, true, "File restored successfully", a.payload(r, x, false), nil)
}
func (a App) permanentDelete(w http.ResponseWriter, r *http.Request, uid int64, raw string) {
	id, err := uuid.Parse(raw)
	if err != nil {
		httpx.WriteEnvelope(w, 404, false, "File not found", nil, nil)
		return
	}
	name, obj, err := a.Uploads.PermanentDelete(r.Context(), uid, id)
	if errors.Is(err, uploads.ErrUploadNotFound) {
		httpx.WriteEnvelope(w, 404, false, "File not found", nil, nil)
		return
	}
	if err != nil {
		httpx.WriteEnvelope(w, 503, false, "Files service unavailable", nil, nil)
		return
	}
	if a.Storage != nil && a.Storage.Configured() {
		_ = a.Storage.Remove(r.Context(), obj)
	}
	httpx.WriteEnvelope(w, 200, true, "File permanently deleted successfully", map[string]any{"file_name": name}, nil)
}
func (a App) payload(r *http.Request, x uploads.Upload, shared bool) map[string]any {
	url := x.ObjectName
	if a.MediaBase != "" {
		url = strings.TrimRight(a.MediaBase, "/") + "/" + strings.TrimLeft(x.ObjectName, "/")
	}
	return map[string]any{"id": x.ID, "file_code": x.FileCode, "file_name": x.FileName, "file_size": x.FileSize, "file_type": x.FileType, "file_url": url, "source": map[bool]string{true: "shared", false: "upload"}[shared], "owner": map[string]any{"id": x.UploaderID, "full_name": x.UploaderName}, "uploaded_at": x.CreatedAt, "is_deleted": x.IsDeleted, "deleted_at": x.DeletedAt, "shared_by": nil, "shared_at": nil, "accepted": map[bool]any{true: true, false: nil}[shared]}
}
func itoa(n int) string {
	if n == 0 {
		return "0"
	}
	digits := ""
	for n > 0 {
		digits = string(rune('0'+n%10)) + digits
		n /= 10
	}
	return digits
}
