package sms

import (
	"database/sql"
	"encoding/json"
	"errors"
	"net/http"
	"strconv"
	"strings"

	"github.com/troubleman96/kibegi_API/internal/apps/authentication"
	"github.com/troubleman96/kibegi_API/internal/platform/httpx"
)

type App struct {
	Repository Repository
	Auth       *authentication.TokenService
}

func (a App) PathHandler() http.Handler {
	return authentication.RequireAuth(a.Auth, http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if _, ok := authentication.UserIDFromContext(r.Context()); !ok {
			httpx.WriteEnvelope(w, http.StatusUnauthorized, false, "Authentication credentials were not provided.", nil, nil)
			return
		}
		rest := strings.Trim(strings.TrimPrefix(r.URL.Path, "/api/v1/sms/"), "/")
		parts := strings.Split(rest, "/")
		switch {
		case len(parts) == 4 && parts[0] == "accounts" && parts[3] == "topup" && r.Method == http.MethodPost:
			a.topup(w, r, parts[1], parts[2])
		case len(parts) == 3 && parts[0] == "accounts" && r.Method == http.MethodGet:
			a.account(w, r, parts[1], parts[2])
		case rest == "deliveries" && r.Method == http.MethodGet:
			a.deliveries(w, r)
		default:
			httpx.WriteEnvelope(w, http.StatusNotFound, false, "Not found", nil, nil)
		}
	}))
}

func (a App) account(w http.ResponseWriter, r *http.Request, ownerType, ownerID string) {
	item, err := a.Repository.Account(r.Context(), ownerType, ownerID)
	if errors.Is(err, sql.ErrNoRows) {
		httpx.WriteEnvelope(w, http.StatusNotFound, false, "SMS account not found", nil, nil)
		return
	}
	if err != nil {
		httpx.WriteEnvelope(w, http.StatusServiceUnavailable, false, "SMS service unavailable", nil, nil)
		return
	}
	httpx.WriteEnvelope(w, http.StatusOK, true, "SMS account retrieved successfully", item, nil)
}

func (a App) topup(w http.ResponseWriter, r *http.Request, ownerType, ownerID string) {
	var input struct {
		Amount int `json:"amount"`
	}
	if err := json.NewDecoder(r.Body).Decode(&input); err != nil {
		httpx.WriteEnvelope(w, http.StatusBadRequest, false, "Invalid top-up details", nil, nil)
		return
	}
	item, err := a.Repository.Topup(r.Context(), ownerType, ownerID, input.Amount)
	if errors.Is(err, sql.ErrNoRows) {
		httpx.WriteEnvelope(w, http.StatusNotFound, false, "SMS account not found", nil, nil)
		return
	}
	if err != nil {
		status := http.StatusServiceUnavailable
		if input.Amount <= 0 {
			status = http.StatusBadRequest
		}
		httpx.WriteEnvelope(w, status, false, err.Error(), nil, nil)
		return
	}
	httpx.WriteEnvelope(w, http.StatusOK, true, "SMS account topped up successfully", item, nil)
}

func (a App) deliveries(w http.ResponseWriter, r *http.Request) {
	limit, _ := strconv.Atoi(r.URL.Query().Get("limit"))
	if limit < 1 {
		limit = 20
	}
	if limit > 100 {
		limit = 100
	}
	items, err := a.Repository.Deliveries(r.Context(), limit)
	if err != nil {
		httpx.WriteEnvelope(w, http.StatusServiceUnavailable, false, "SMS delivery history unavailable", nil, nil)
		return
	}
	httpx.WriteEnvelope(w, http.StatusOK, true, "SMS deliveries retrieved successfully", items, nil)
}
