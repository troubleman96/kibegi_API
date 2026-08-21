package uploads

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"mime"
	"net/http"
	"path/filepath"
	"strconv"
	"strings"
	"time"

	"github.com/google/uuid"

	"github.com/troubleman96/kibegi_API/internal/apps/authentication"
	"github.com/troubleman96/kibegi_API/internal/platform/cache"
	"github.com/troubleman96/kibegi_API/internal/platform/httpx"
	"github.com/troubleman96/kibegi_API/internal/platform/storage"
)

const maxUploadSize = 50 * 1024 * 1024

type App struct {
	Repository   Repository
	Auth         *authentication.TokenService
	Cache        *cache.Redis
	Storage      *storage.ObjectStorage
	MediaBase    string
	IndexerURL   string
	IndexerToken string
}

type pageOptions struct {
	Limit  int
	Offset int
	Page   int
}

type pageResponse struct {
	Count    int    `json:"count"`
	Next     string `json:"next"`
	Previous string `json:"previous"`
	Results  any    `json:"results"`
}

func (a App) PathHandler() http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		rest := strings.Trim(strings.TrimPrefix(r.URL.Path, "/api/v1/uploads/"), "/")
		if rest == "" {
			if r.Method == http.MethodGet {
				a.list(w, r, "")
			} else if r.Method == http.MethodPost {
				a.create(w, r)
			} else {
				w.Header().Set("Allow", "GET, POST")
				httpx.WriteEnvelope(w, http.StatusMethodNotAllowed, false, "method not allowed", nil, nil)
			}
			return
		}
		parts := strings.Split(rest, "/")
		switch {
		case len(parts) == 1 && parts[0] == "search":
			a.list(w, r, r.URL.Query().Get("q"))
		case len(parts) == 1 && parts[0] == "trash":
			a.listMode(w, r, "trash")
		case len(parts) == 1 && parts[0] == "recent":
			a.listMode(w, r, "recent")
		case len(parts) == 2 && parts[1] == "download":
			a.download(w, r, parts[0])
		case len(parts) == 2 && parts[1] == "restore":
			a.restore(w, r, parts[0])
		case len(parts) == 2 && parts[1] == "permanent-delete":
			a.permanentDelete(w, r, parts[0])
		case len(parts) == 1:
			a.detail(w, r, parts[0])
		default:
			httpx.WriteEnvelope(w, http.StatusNotFound, false, "Not found", nil, nil)
		}
	})
}

func (a App) list(w http.ResponseWriter, r *http.Request, query string) {
	userID, ok := authentication.UserIDFromContext(r.Context())
	if !ok {
		httpx.WriteEnvelope(w, http.StatusUnauthorized, false, "Authentication credentials were not provided.", nil, nil)
		return
	}
	page := parsePage(r)
	user, err := (authentication.UserRepository{DB: a.Repository.DB}).FindByID(r.Context(), userID)
	if err != nil {
		httpx.WriteEnvelope(w, http.StatusServiceUnavailable, false, "Uploads service unavailable", nil, nil)
		return
	}
	cacheKey := "api-cache:uploads:v1:" + strconv.FormatInt(userID, 10) + ":" + query + ":" + strconv.Itoa(page.Page)
	if r.Method == http.MethodGet && a.Cache != nil && a.Cache.Configured() {
		var cached pageResponse
		if err := a.Cache.Get(r.Context(), cacheKey, &cached); err == nil {
			httpx.WriteJSON(w, http.StatusOK, cached)
			return
		}
	}
	items, count, err := a.Repository.List(r.Context(), userID, user.UserType, r.URL.Query().Get("class_id"), query, "", page.Limit, page.Offset)
	if err != nil {
		httpx.WriteEnvelope(w, http.StatusServiceUnavailable, false, "Uploads service unavailable", nil, nil)
		return
	}
	results := make([]map[string]any, 0, len(items))
	for _, item := range items {
		results = append(results, a.listPayload(r, item))
	}
	response := buildPage(r, page, count, results)
	if a.Cache != nil && a.Cache.Configured() {
		_ = a.Cache.Set(r.Context(), cacheKey, response, 90*time.Second)
	}
	httpx.WriteJSON(w, http.StatusOK, response)
}

func (a App) listMode(w http.ResponseWriter, r *http.Request, mode string) {
	userID, ok := authentication.UserIDFromContext(r.Context())
	if !ok {
		httpx.WriteEnvelope(w, http.StatusUnauthorized, false, "Authentication credentials were not provided.", nil, nil)
		return
	}
	page := parsePage(r)
	user, err := (authentication.UserRepository{DB: a.Repository.DB}).FindByID(r.Context(), userID)
	if err != nil {
		httpx.WriteEnvelope(w, http.StatusServiceUnavailable, false, "Uploads service unavailable", nil, nil)
		return
	}
	items, count, err := a.Repository.List(r.Context(), userID, user.UserType, "", "", mode, page.Limit, page.Offset)
	if err != nil {
		httpx.WriteEnvelope(w, http.StatusServiceUnavailable, false, "Uploads service unavailable", nil, nil)
		return
	}
	results := make([]map[string]any, 0, len(items))
	for _, item := range items {
		results = append(results, a.listPayload(r, item))
	}
	httpx.WriteJSON(w, http.StatusOK, buildPage(r, page, count, results))
}

func (a App) create(w http.ResponseWriter, r *http.Request) {
	userID, ok := authentication.UserIDFromContext(r.Context())
	if !ok {
		httpx.WriteEnvelope(w, http.StatusUnauthorized, false, "Authentication credentials were not provided.", nil, nil)
		return
	}
	if err := r.ParseMultipartForm(maxUploadSize); err != nil {
		httpx.WriteEnvelope(w, http.StatusBadRequest, false, "Invalid multipart upload", nil, nil)
		return
	}
	file, header, err := r.FormFile("file")
	if err != nil {
		httpx.WriteEnvelope(w, http.StatusBadRequest, false, "File is required", nil, nil)
		return
	}
	defer file.Close()
	if header.Size > maxUploadSize {
		httpx.WriteEnvelope(w, http.StatusBadRequest, false, "File too large. Maximum size is 50MB.", nil, nil)
		return
	}
	fileName := header.Filename
	if custom := strings.TrimSpace(r.FormValue("file_name")); custom != "" {
		fileName = custom
	}
	fileType := detectFileType(fileName)
	classID, err := uuid.Parse(r.FormValue("class_obj"))
	if err != nil {
		httpx.WriteEnvelope(w, http.StatusBadRequest, false, "Invalid class", nil, nil)
		return
	}
	objectName := fmt.Sprintf("uploads/%d/%s", userID, filepath.Base(fileName))
	if a.Storage == nil || !a.Storage.Configured() {
		httpx.WriteEnvelope(w, http.StatusServiceUnavailable, false, "File storage is not configured", nil, nil)
		return
	}
	if _, err := a.Storage.Put(r.Context(), objectName, file, header.Size, mime.TypeByExtension(filepath.Ext(fileName))); err != nil {
		httpx.WriteEnvelope(w, http.StatusBadGateway, false, "File storage unavailable", nil, nil)
		return
	}
	item, err := a.Repository.Create(r.Context(), userID, classID, fileName, fileType, objectName, header.Size)
	if err != nil {
		_ = a.Storage.Remove(r.Context(), objectName)
		if errors.Is(err, ErrUploadDenied) {
			httpx.WriteEnvelope(w, http.StatusForbidden, false, "You don't have permission to upload to this class", nil, nil)
			return
		}
		httpx.WriteEnvelope(w, http.StatusServiceUnavailable, false, "Uploads service unavailable", nil, nil)
		return
	}
	a.enqueueIndex(item.ID)
	httpx.WriteEnvelope(w, http.StatusCreated, true, "File uploaded successfully", a.fullPayload(r, item), nil)
}

func (a App) enqueueIndex(uploadID uuid.UUID) {
	if strings.TrimSpace(a.IndexerURL) == "" {
		return
	}
	go func() {
		ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()
		body, _ := json.Marshal(map[string]bool{"force": false})
		req, err := http.NewRequestWithContext(ctx, http.MethodPost, strings.TrimRight(a.IndexerURL, "/")+"/v1/index/uploads/"+uploadID.String(), bytes.NewReader(body))
		if err != nil {
			return
		}
		req.Header.Set("Content-Type", "application/json")
		if a.IndexerToken != "" {
			req.Header.Set("Authorization", "Bearer "+a.IndexerToken)
		}
		resp, err := http.DefaultClient.Do(req)
		if err == nil && resp.Body != nil {
			_ = resp.Body.Close()
		}
	}()
}

func (a App) detail(w http.ResponseWriter, r *http.Request, code string) {
	userID, ok := authentication.UserIDFromContext(r.Context())
	if !ok {
		httpx.WriteEnvelope(w, http.StatusUnauthorized, false, "Authentication credentials were not provided.", nil, nil)
		return
	}
	item, err := a.Repository.FindByCode(r.Context(), userID, code, false)
	if errors.Is(err, ErrUploadNotFound) {
		httpx.WriteEnvelope(w, http.StatusNotFound, false, "Upload not found", nil, nil)
		return
	}
	if err != nil {
		httpx.WriteEnvelope(w, http.StatusServiceUnavailable, false, "Uploads service unavailable", nil, nil)
		return
	}
	switch r.Method {
	case http.MethodGet:
		httpx.WriteEnvelope(w, http.StatusOK, true, "Upload retrieved successfully", a.fullPayload(r, item), nil)
	case http.MethodDelete:
		if item.UploaderID != userID {
			httpx.WriteEnvelope(w, http.StatusForbidden, false, "You don't have permission to delete this file", nil, nil)
			return
		}
		if err := a.Repository.SoftDelete(r.Context(), userID, code); err != nil {
			httpx.WriteEnvelope(w, http.StatusServiceUnavailable, false, "Uploads service unavailable", nil, nil)
			return
		}
		httpx.WriteEnvelope(w, http.StatusOK, true, "Upload moved to trash", nil, nil)
	default:
		w.Header().Set("Allow", "GET, DELETE")
		httpx.WriteEnvelope(w, http.StatusMethodNotAllowed, false, "method not allowed", nil, nil)
	}
}

func (a App) restore(w http.ResponseWriter, r *http.Request, id string) {
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
	parsed, err := uuid.Parse(id)
	if err != nil {
		httpx.WriteEnvelope(w, http.StatusNotFound, false, "Upload not found in trash", nil, nil)
		return
	}
	item, err := a.Repository.Restore(r.Context(), userID, parsed)
	if errors.Is(err, ErrUploadNotFound) {
		httpx.WriteEnvelope(w, http.StatusNotFound, false, "Upload not found in trash", nil, nil)
		return
	}
	if err != nil {
		httpx.WriteEnvelope(w, http.StatusServiceUnavailable, false, "Uploads service unavailable", nil, nil)
		return
	}
	httpx.WriteEnvelope(w, http.StatusOK, true, "Upload restored successfully", a.fullPayload(r, item), nil)
}

func (a App) permanentDelete(w http.ResponseWriter, r *http.Request, id string) {
	if r.Method != http.MethodDelete {
		w.Header().Set("Allow", http.MethodDelete)
		httpx.WriteEnvelope(w, http.StatusMethodNotAllowed, false, "method not allowed", nil, nil)
		return
	}
	userID, ok := authentication.UserIDFromContext(r.Context())
	if !ok {
		httpx.WriteEnvelope(w, http.StatusUnauthorized, false, "Authentication credentials were not provided.", nil, nil)
		return
	}
	parsed, err := uuid.Parse(id)
	if err != nil {
		httpx.WriteEnvelope(w, http.StatusNotFound, false, "File not found in trash", nil, nil)
		return
	}
	fileName, objectName, err := a.Repository.PermanentDelete(r.Context(), userID, parsed)
	if errors.Is(err, ErrUploadNotFound) {
		httpx.WriteEnvelope(w, http.StatusNotFound, false, "File not found in trash", nil, nil)
		return
	}
	if err != nil {
		httpx.WriteEnvelope(w, http.StatusServiceUnavailable, false, "Uploads service unavailable", nil, nil)
		return
	}
	if a.Storage != nil && a.Storage.Configured() {
		_ = a.Storage.Remove(r.Context(), objectName)
	}
	httpx.WriteEnvelope(w, http.StatusOK, true, "'"+fileName+"' permanently deleted", nil, nil)
}

func (a App) download(w http.ResponseWriter, r *http.Request, code string) {
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
	item, err := a.Repository.FindByCode(r.Context(), userID, code, false)
	if errors.Is(err, ErrUploadNotFound) {
		httpx.WriteEnvelope(w, http.StatusNotFound, false, "File not found or has been deleted", nil, nil)
		return
	}
	if err != nil {
		httpx.WriteEnvelope(w, http.StatusServiceUnavailable, false, "Uploads service unavailable", nil, nil)
		return
	}
	if a.Storage == nil || !a.Storage.Configured() {
		httpx.WriteEnvelope(w, http.StatusServiceUnavailable, false, "File storage is not configured", nil, nil)
		return
	}
	object, err := a.Storage.Open(r.Context(), item.ObjectName)
	if err != nil {
		httpx.WriteEnvelope(w, http.StatusNotFound, false, "File not found in storage", nil, nil)
		return
	}
	defer object.Close()
	contentType := mime.TypeByExtension(filepath.Ext(item.FileName))
	if contentType == "" {
		contentType = "application/octet-stream"
	}
	w.Header().Set("Content-Type", contentType)
	w.Header().Set("Content-Length", strconv.FormatInt(item.FileSize, 10))
	w.Header().Set("Content-Disposition", `attachment; filename="`+strings.ReplaceAll(item.FileName, `"`, "")+`"`)
	w.Header().Set("X-Content-Type-Options", "nosniff")
	w.Header().Set("Cache-Control", "private, max-age=3600")
	_, _ = io.Copy(w, object)
}

func (a App) listPayload(r *http.Request, item Upload) map[string]any {
	return map[string]any{
		"id": item.ID, "file_name": item.FileName, "file_type": item.FileType, "file_size": item.FileSize,
		"file_code": item.FileCode, "uploader_name": item.UploaderName, "uploader_profile_image": item.UploaderImage,
		"uploader_profile_image_url": a.optionalMediaURL(r, item.UploaderImage), "class_name": item.ClassName, "created_at": item.CreatedAt,
	}
}

func (a App) fullPayload(r *http.Request, item Upload) map[string]any {
	payload := a.listPayload(r, item)
	payload["file"] = item.ObjectName
	payload["uploader"] = item.UploaderID
	payload["class_obj"] = item.ClassID
	payload["is_deleted"] = item.IsDeleted
	payload["deleted_at"] = item.DeletedAt
	payload["updated_at"] = item.UpdatedAt
	payload["file_url"] = a.mediaURL(r, item.ObjectName)
	return payload
}

func (a App) optionalMediaURL(r *http.Request, value any) any {
	objectName, ok := value.(string)
	if !ok || objectName == "" {
		return nil
	}
	return a.mediaURL(r, objectName)
}

func (a App) mediaURL(r *http.Request, objectName string) any {
	if objectName == "" {
		return nil
	}
	if a.Storage != nil {
		if value := a.Storage.PublicURL(objectName); value != "" {
			return value
		}
	}
	if a.MediaBase != "" {
		return strings.TrimRight(a.MediaBase, "/") + "/" + strings.TrimLeft(objectName, "/")
	}
	scheme := "http"
	if r.TLS != nil {
		scheme = "https"
	}
	return scheme + "://" + r.Host + "/media/" + strings.TrimLeft(objectName, "/")
}

func parsePage(r *http.Request) pageOptions {
	page := positive(r.URL.Query().Get("page"), 1)
	limit := positive(r.URL.Query().Get("page_size"), 20)
	if limit > 100 {
		limit = 100
	}
	return pageOptions{Limit: limit, Offset: (page - 1) * limit, Page: page}
}

func buildPage(r *http.Request, page pageOptions, count int, results any) pageResponse {
	next := ""
	previous := ""
	if page.Offset+page.Limit < count {
		next = pageURL(r, page.Page+1)
	}
	if page.Page > 1 {
		previous = pageURL(r, page.Page-1)
	}
	return pageResponse{Count: count, Next: next, Previous: previous, Results: results}
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

func detectFileType(name string) string {
	ext := strings.ToLower(filepath.Ext(name))
	switch ext {
	case ".pdf", ".doc", ".docx", ".txt", ".rtf", ".odt":
		return "document"
	case ".xls", ".xlsx", ".csv", ".ods":
		return "spreadsheet"
	case ".ppt", ".pptx", ".odp", ".key":
		return "presentation"
	case ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg", ".webp", ".ico":
		return "image"
	case ".mp4", ".avi", ".mov", ".wmv", ".flv", ".mkv", ".webm", ".m4v":
		return "video"
	case ".mp3", ".wav", ".ogg", ".flac", ".m4a", ".aac", ".wma":
		return "audio"
	case ".zip", ".rar", ".tar", ".gz", ".7z", ".bz2", ".xz":
		return "archive"
	default:
		return "other"
	}
}
