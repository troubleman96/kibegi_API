package notifications

import (
	"errors"
	"net/http"
	"strconv"
	"strings"
	"time"

	"github.com/troubleman96/kibegi_API/internal/apps/authentication"
	"github.com/troubleman96/kibegi_API/internal/platform/cache"
	"github.com/troubleman96/kibegi_API/internal/platform/httpx"
)

type App struct {
	Repository Repository
	Auth       *authentication.TokenService
	Cache      *cache.Redis
}

type pagination struct {
	Limit  int
	Offset int
	Page   int
}

type listData struct {
	Count       int            `json:"count"`
	Next        string         `json:"next"`
	Previous    string         `json:"previous"`
	Results     []Notification `json:"results"`
	UnreadCount int            `json:"unread_count"`
}

func (a App) PathHandler() http.Handler {
	return authentication.RequireAuth(a.Auth, http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		userID, ok := authentication.UserIDFromContext(r.Context())
		if !ok {
			httpx.WriteEnvelope(w, http.StatusUnauthorized, false, "Authentication credentials were not provided.", nil, nil)
			return
		}
		rest := strings.Trim(strings.TrimPrefix(r.URL.Path, "/api/v1/notifications/"), "/")
		switch {
		case rest == "" && r.Method == http.MethodGet:
			a.list(w, r, userID)
		case rest == "unread-count" && r.Method == http.MethodGet:
			a.unreadCount(w, r, userID)
		case rest == "read-all" && r.Method == http.MethodPost:
			a.markAllRead(w, r, userID)
		case strings.HasSuffix(rest, "/read") && r.Method == http.MethodPost:
			a.markRead(w, r, userID, strings.TrimSuffix(rest, "/read"))
		case rest != "" && r.Method == http.MethodDelete:
			a.delete(w, r, userID, rest)
		default:
			httpx.WriteEnvelope(w, http.StatusMethodNotAllowed, false, "method not allowed", nil, nil)
		}
	}))
}

func (a App) list(w http.ResponseWriter, r *http.Request, userID int64) {
	page := parsePagination(r)
	var readFilter *bool
	switch strings.ToLower(r.URL.Query().Get("is_read")) {
	case "true":
		value := true
		readFilter = &value
	case "false":
		value := false
		readFilter = &value
	}
	items, total, unread, err := a.Repository.List(r.Context(), userID, readFilter, r.URL.Query().Get("type"), page.Limit, page.Offset)
	if err != nil {
		httpx.WriteEnvelope(w, http.StatusServiceUnavailable, false, "Notifications service unavailable", nil, nil)
		return
	}
	data := listData{Count: total, Results: items, UnreadCount: unread}
	if page.Offset+page.Limit < total {
		data.Next = pageURL(r, page.Page+1)
	}
	if page.Page > 1 {
		data.Previous = pageURL(r, page.Page-1)
	}
	httpx.WriteEnvelope(w, http.StatusOK, true, "Retrieved "+strconv.Itoa(total)+" notifications", data, nil)
}

func (a App) unreadCount(w http.ResponseWriter, r *http.Request, userID int64) {
	key := "api-cache:notifications:unread:" + strconv.FormatInt(userID, 10)
	if a.Cache != nil && a.Cache.Configured() {
		var cached int
		if err := a.Cache.Get(r.Context(), key, &cached); err == nil {
			httpx.WriteEnvelope(w, http.StatusOK, true, "", map[string]int{"unread_count": cached}, nil)
			return
		}
	}
	count, err := a.Repository.UnreadCount(r.Context(), userID)
	if err != nil {
		httpx.WriteEnvelope(w, http.StatusServiceUnavailable, false, "Notifications service unavailable", nil, nil)
		return
	}
	if a.Cache != nil && a.Cache.Configured() {
		_ = a.Cache.Set(r.Context(), key, count, 10*time.Second)
	}
	httpx.WriteEnvelope(w, http.StatusOK, true, "", map[string]int{"unread_count": count}, nil)
}

func (a App) markRead(w http.ResponseWriter, r *http.Request, userID int64, rawID string) {
	id, err := strconv.ParseInt(rawID, 10, 64)
	if err != nil {
		httpx.WriteEnvelope(w, http.StatusNotFound, false, "Notification not found", nil, nil)
		return
	}
	item, err := a.Repository.MarkRead(r.Context(), id, userID)
	if errors.Is(err, ErrNotificationNotFound) {
		httpx.WriteEnvelope(w, http.StatusNotFound, false, "Notification not found", nil, nil)
		return
	}
	if errors.Is(err, ErrNotificationAlreadyRead) {
		httpx.WriteEnvelope(w, http.StatusBadRequest, false, err.Error(), nil, nil)
		return
	}
	if err != nil {
		httpx.WriteEnvelope(w, http.StatusServiceUnavailable, false, "Notifications service unavailable", nil, nil)
		return
	}
	a.invalidateUnread(r, userID)
	httpx.WriteEnvelope(w, http.StatusOK, true, "Notification marked as read", item, nil)
}

func (a App) markAllRead(w http.ResponseWriter, r *http.Request, userID int64) {
	count, err := a.Repository.MarkAllRead(r.Context(), userID)
	if err != nil {
		httpx.WriteEnvelope(w, http.StatusServiceUnavailable, false, "Notifications service unavailable", nil, nil)
		return
	}
	a.invalidateUnread(r, userID)
	httpx.WriteEnvelope(w, http.StatusOK, true, "Marked "+strconv.FormatInt(count, 10)+" notifications as read", map[string]int64{"marked_read": count}, nil)
}

func (a App) delete(w http.ResponseWriter, r *http.Request, userID int64, rawID string) {
	id, err := strconv.ParseInt(rawID, 10, 64)
	if err != nil {
		httpx.WriteEnvelope(w, http.StatusNotFound, false, "Notification not found", nil, nil)
		return
	}
	if err := a.Repository.Delete(r.Context(), id, userID); errors.Is(err, ErrNotificationNotFound) {
		httpx.WriteEnvelope(w, http.StatusNotFound, false, "Notification not found", nil, nil)
		return
	} else if err != nil {
		httpx.WriteEnvelope(w, http.StatusServiceUnavailable, false, "Notifications service unavailable", nil, nil)
		return
	}
	a.invalidateUnread(r, userID)
	httpx.WriteEnvelope(w, http.StatusOK, true, "Notification deleted successfully", nil, nil)
}

func (a App) invalidateUnread(r *http.Request, userID int64) {
	if a.Cache != nil && a.Cache.Configured() {
		_ = a.Cache.Delete(r.Context(), "api-cache:notifications:unread:"+strconv.FormatInt(userID, 10))
	}
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
