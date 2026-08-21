package library

import (
	"encoding/json"
	"errors"
	"fmt"
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
type pagination struct{ Limit, Offset, Page int }
type pageResponse struct {
	Count    int    `json:"count"`
	Next     string `json:"next"`
	Previous string `json:"previous"`
	Results  any    `json:"results"`
}

func (a App) PathHandler() http.Handler {
	return authentication.RequireAuth(a.Auth, http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		userID, ok := authentication.UserIDFromContext(r.Context())
		if !ok {
			httpx.WriteEnvelope(w, 401, false, "Authentication credentials were not provided.", nil, nil)
			return
		}
		rest := strings.Trim(strings.TrimPrefix(r.URL.Path, "/api/v1/library/"), "/")
		parts := strings.Split(rest, "/")
		switch {
		case rest == "categories" && r.Method == http.MethodGet:
			a.categories(w, r)
		case rest == "items" && r.Method == http.MethodGet:
			a.items(w, r, userID, "")
		case rest == "items" && r.Method == http.MethodPost:
			a.create(w, r, userID)
		case rest == "items/search":
			a.items(w, r, userID, r.URL.Query().Get("q"))
		case rest == "items/me":
			a.itemsMode(w, r, userID)
		case len(parts) == 3 && parts[0] == "items" && parts[2] == "download":
			a.download(w, r, parts[1])
		case len(parts) == 2 && parts[0] == "items":
			a.detail(w, r, userID, parts[1])
		default:
			httpx.WriteEnvelope(w, 404, false, "Not found", nil, nil)
		}
	}))
}
func (a App) categories(w http.ResponseWriter, r *http.Request) {
	items, err := a.Repository.Categories(r.Context())
	if err != nil {
		httpx.WriteEnvelope(w, 503, false, "Library service unavailable", nil, nil)
		return
	}
	httpx.WriteEnvelope(w, 200, true, "Library categories retrieved successfully", items, nil)
}
func (a App) items(w http.ResponseWriter, r *http.Request, userID int64, query string) {
	p := parsePagination(r)
	items, count, err := a.Repository.Items(r.Context(), query, r.URL.Query().Get("category"), "", userID, p.Limit, p.Offset)
	if err != nil {
		httpx.WriteEnvelope(w, 503, false, "Library service unavailable", nil, nil)
		return
	}
	for i := range items {
		items[i] = a.withURL(r, items[i])
	}
	httpx.WriteJSON(w, 200, buildPage(r, p, count, items))
}
func (a App) itemsMode(w http.ResponseWriter, r *http.Request, userID int64) {
	p := parsePagination(r)
	items, count, err := a.Repository.Items(r.Context(), "", "", "me", userID, p.Limit, p.Offset)
	if err != nil {
		httpx.WriteEnvelope(w, 503, false, "Library service unavailable", nil, nil)
		return
	}
	for i := range items {
		items[i] = a.withURL(r, items[i])
	}
	httpx.WriteJSON(w, 200, buildPage(r, p, count, items))
}
func (a App) create(w http.ResponseWriter, r *http.Request, userID int64) {
	if err := r.ParseMultipartForm(64 << 20); err != nil && r.Header.Get("Content-Type") == "" {
		httpx.WriteEnvelope(w, 400, false, "Invalid upload", nil, nil)
		return
	}
	item := Item{Title: r.FormValue("title"), Description: r.FormValue("description"), FileType: r.FormValue("file_type"), Subject: r.FormValue("subject"), CourseCode: r.FormValue("course_code"), AuthorName: r.FormValue("author_name"), Status: r.FormValue("status")}
	if item.Title == "" {
		var body Item
		if err := json.NewDecoder(r.Body).Decode(&body); err == nil {
			item = body
		}
	}
	file, header, err := r.FormFile("file")
	if err != nil {
		httpx.WriteEnvelope(w, 400, false, "A file is required", nil, nil)
		return
	}
	defer file.Close()
	name := "library/items/" + uuid.NewString() + "/" + filepath.Base(header.Filename)
	if a.Storage == nil || !a.Storage.Configured() {
		httpx.WriteEnvelope(w, 503, false, "File storage is not configured", nil, nil)
		return
	}
	if _, err := a.Storage.Put(r.Context(), name, file, header.Size, header.Header.Get("Content-Type")); err != nil {
		httpx.WriteEnvelope(w, 503, false, "Unable to store library file", nil, nil)
		return
	}
	item.ObjectName = name
	created, err := a.Repository.Create(r.Context(), userID, item)
	if err != nil {
		httpx.WriteEnvelope(w, 400, false, err.Error(), nil, nil)
		return
	}
	httpx.WriteEnvelope(w, 201, true, "Library item created successfully", a.withURL(r, created), nil)
}
func (a App) detail(w http.ResponseWriter, r *http.Request, userID int64, code string) {
	item, err := a.Repository.Find(r.Context(), code)
	if errors.Is(err, ErrItemNotFound) {
		httpx.WriteEnvelope(w, 404, false, "Library item not found", nil, nil)
		return
	}
	if err != nil {
		httpx.WriteEnvelope(w, 503, false, "Library service unavailable", nil, nil)
		return
	}
	if r.Method == http.MethodGet {
		a.Repository.Increment(r.Context(), code, false)
		item.ViewCount++
		httpx.WriteEnvelope(w, 200, true, "Library item retrieved successfully", a.withURL(r, item), nil)
		return
	}
	switch r.Method {
	case http.MethodPatch, http.MethodPut:
		if item.UploadedBy.ID != userID {
			httpx.WriteEnvelope(w, 403, false, "You do not have permission to update this item", nil, nil)
			return
		}
		var input Item
		if err := json.NewDecoder(r.Body).Decode(&input); err != nil {
			httpx.WriteEnvelope(w, 400, false, "Invalid input", nil, nil)
			return
		}
		updated, err := a.Repository.Update(r.Context(), userID, code, input)
		if err != nil {
			httpx.WriteEnvelope(w, 400, false, err.Error(), nil, nil)
			return
		}
		httpx.WriteEnvelope(w, 200, true, "Library item updated successfully", a.withURL(r, updated), nil)
	case http.MethodDelete:
		if item.UploadedBy.ID != userID {
			httpx.WriteEnvelope(w, 403, false, "You do not have permission to delete this item", nil, nil)
			return
		}
		if err := a.Repository.Delete(r.Context(), userID, code); err != nil {
			httpx.WriteEnvelope(w, 503, false, "Library service unavailable", nil, nil)
			return
		}
		httpx.WriteEnvelope(w, 200, true, "Library item deleted successfully", nil, nil)
	default:
		httpx.WriteEnvelope(w, 405, false, "method not allowed", nil, nil)
	}
}
func (a App) download(w http.ResponseWriter, r *http.Request, code string) {
	item, err := a.Repository.Find(r.Context(), code)
	if errors.Is(err, ErrItemNotFound) {
		httpx.WriteEnvelope(w, 404, false, "Library item not found", nil, nil)
		return
	}
	if err != nil {
		httpx.WriteEnvelope(w, 503, false, "Library service unavailable", nil, nil)
		return
	}
	if a.Storage == nil || !a.Storage.Configured() {
		httpx.WriteEnvelope(w, 503, false, "File storage is not configured", nil, nil)
		return
	}
	object, err := a.Storage.Open(r.Context(), item.ObjectName)
	if err != nil {
		httpx.WriteEnvelope(w, 404, false, "File not found in storage", nil, nil)
		return
	}
	defer object.Close()
	a.Repository.Increment(r.Context(), code, true)
	contentType := mime.TypeByExtension(filepath.Ext(item.FileName))
	if contentType == "" {
		contentType = "application/octet-stream"
	}
	w.Header().Set("Content-Type", contentType)
	w.Header().Set("Content-Disposition", fmt.Sprintf(`attachment; filename="%s"`, strings.ReplaceAll(item.FileName, `"`, "")))
	w.Header().Set("X-Content-Type-Options", "nosniff")
	_, _ = io.Copy(w, object)
}
func (a App) withURL(r *http.Request, item Item) Item {
	if item.ObjectName == "" {
		return item
	}
	if a.MediaBase != "" {
		item.ObjectName = strings.TrimRight(a.MediaBase, "/") + "/" + strings.TrimLeft(item.ObjectName, "/")
	} else {
		scheme := "http"
		if r.TLS != nil {
			scheme = "https"
		}
		item.ObjectName = scheme + "://" + r.Host + "/media/" + strings.TrimLeft(item.ObjectName, "/")
	}
	return item
}
func parsePagination(r *http.Request) pagination {
	page := positive(r.URL.Query().Get("page"), 1)
	limit := positive(r.URL.Query().Get("page_size"), 20)
	if limit > 100 {
		limit = 100
	}
	return pagination{Limit: limit, Offset: (page - 1) * limit, Page: page}
}
func buildPage(r *http.Request, p pagination, count int, results any) pageResponse {
	next, prev := "", ""
	if p.Offset+p.Limit < count {
		next = pageURL(r, p.Page+1)
	}
	if p.Page > 1 {
		prev = pageURL(r, p.Page-1)
	}
	return pageResponse{Count: count, Next: next, Previous: prev, Results: results}
}
func pageURL(r *http.Request, page int) string {
	q := r.URL.Query()
	q.Set("page", strconv.Itoa(page))
	return r.URL.Path + "?" + q.Encode()
}
func positive(value string, fallback int) int {
	v, err := strconv.Atoi(value)
	if err != nil || v <= 0 {
		return fallback
	}
	return v
}
