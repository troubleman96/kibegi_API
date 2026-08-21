package storage

import (
	"database/sql"
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

func (a App) PathHandler() http.Handler {
	return authentication.RequireAuth(a.Auth, http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		userID, ok := authentication.UserIDFromContext(r.Context())
		if !ok {
			httpx.WriteEnvelope(w, http.StatusUnauthorized, false, "Authentication credentials were not provided.", nil, nil)
			return
		}
		rest := strings.Trim(strings.TrimPrefix(r.URL.Path, "/api/v1/storage/"), "/")
		switch {
		case rest == "" && r.Method == http.MethodGet:
			a.list(w, r, userID)
		case rest == "info" && r.Method == http.MethodGet:
			a.info(w, r, userID)
		case rest == "recalculate" && r.Method == http.MethodPost:
			a.recalculate(w, r, userID)
		case rest == "history" && r.Method == http.MethodGet:
			a.history(w, r, userID)
		default:
			httpx.WriteEnvelope(w, http.StatusNotFound, false, "Not found", nil, nil)
		}
	}))
}

func (a App) list(w http.ResponseWriter, r *http.Request, userID int64) {
	key := "storage:v1:" + strconv.FormatInt(userID, 10) + ":list"
	var cached UserStorage
	if a.Cache != nil && a.Cache.Get(r.Context(), key, &cached) == nil {
		httpx.WriteEnvelope(w, http.StatusOK, true, "Storage information retrieved successfully", cached, nil)
		return
	}
	item, err := a.Repository.Current(r.Context(), userID, false)
	if errors.Is(err, sql.ErrNoRows) {
		httpx.WriteEnvelope(w, http.StatusNotFound, false, "User not found", nil, nil)
		return
	}
	if err != nil {
		httpx.WriteEnvelope(w, http.StatusInternalServerError, false, "Failed to retrieve storage information", map[string]any{"detail": err.Error()}, nil)
		return
	}
	if a.Cache != nil {
		_ = a.Cache.Set(r.Context(), key, item, time.Minute)
	}
	httpx.WriteEnvelope(w, http.StatusOK, true, "Storage information retrieved successfully", item, nil)
}

func (a App) info(w http.ResponseWriter, r *http.Request, userID int64) {
	key := "storage:v1:" + strconv.FormatInt(userID, 10) + ":info"
	var cached StorageInfo
	if a.Cache != nil && a.Cache.Get(r.Context(), key, &cached) == nil {
		httpx.WriteEnvelope(w, http.StatusOK, true, "Storage information retrieved successfully", cached, nil)
		return
	}
	item, err := a.Repository.Info(r.Context(), userID)
	if err != nil {
		httpx.WriteEnvelope(w, http.StatusInternalServerError, false, "Failed to retrieve storage information", map[string]any{"detail": err.Error()}, nil)
		return
	}
	if a.Cache != nil {
		_ = a.Cache.Set(r.Context(), key, item, time.Minute)
	}
	httpx.WriteEnvelope(w, http.StatusOK, true, "Storage information retrieved successfully", item, nil)
}

func (a App) recalculate(w http.ResponseWriter, r *http.Request, userID int64) {
	item, err := a.Repository.Info(r.Context(), userID)
	if err != nil {
		httpx.WriteEnvelope(w, http.StatusInternalServerError, false, "Failed to recalculate storage", map[string]any{"detail": err.Error()}, nil)
		return
	}
	a.invalidate(r, userID)
	httpx.WriteEnvelope(w, http.StatusOK, true, "Storage recalculated successfully", item, nil)
}

func (a App) history(w http.ResponseWriter, r *http.Request, userID int64) {
	limit, _ := strconv.Atoi(r.URL.Query().Get("limit"))
	if limit < 1 {
		limit = 30
	}
	if limit > 100 {
		limit = 100
	}
	key := "storage:v1:" + strconv.FormatInt(userID, 10) + ":history:" + strconv.Itoa(limit)
	var cached []UsageHistory
	if a.Cache != nil && a.Cache.Get(r.Context(), key, &cached) == nil {
		httpx.WriteEnvelope(w, http.StatusOK, true, "Storage history retrieved successfully", cached, nil)
		return
	}
	items, err := a.Repository.History(r.Context(), userID, limit)
	if err != nil {
		httpx.WriteEnvelope(w, http.StatusInternalServerError, false, "Failed to retrieve storage history", map[string]any{"detail": err.Error()}, nil)
		return
	}
	if a.Cache != nil {
		_ = a.Cache.Set(r.Context(), key, items, time.Minute)
	}
	httpx.WriteEnvelope(w, http.StatusOK, true, "Storage history retrieved successfully", items, nil)
}

func (a App) invalidate(r *http.Request, userID int64) {
	if a.Cache == nil {
		return
	}
	_ = a.Cache.Delete(r.Context(), "storage:v1:"+strconv.FormatInt(userID, 10)+":list", "storage:v1:"+strconv.FormatInt(userID, 10)+":info")
}
