package search

import (
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
		uid, ok := authentication.UserIDFromContext(r.Context())
		if !ok {
			httpx.WriteEnvelope(w, 401, false, "Authentication credentials were not provided.", nil, nil)
			return
		}
		rest := strings.Trim(strings.TrimPrefix(r.URL.Path, "/api/v1/search/"), "/")
		switch {
		case rest == "" && r.Method == http.MethodGet:
			a.search(w, r, uid)
		case rest == "suggestions" && r.Method == http.MethodGet:
			a.suggestions(w, r)
		case rest == "history" && r.Method == http.MethodGet:
			a.history(w, r, uid)
		case rest == "history" && r.Method == http.MethodDelete:
			a.clearHistory(w, r, uid)
		default:
			httpx.WriteEnvelope(w, 404, false, "Not found", nil, nil)
		}
	}))
}
func (a App) search(w http.ResponseWriter, r *http.Request, uid int64) {
	q := strings.TrimSpace(r.URL.Query().Get("q"))
	if q == "" {
		httpx.WriteEnvelope(w, 400, false, "Search query is required", map[string]any{"q": []string{"This field is required."}}, nil)
		return
	}
	if len([]rune(q)) < 2 {
		httpx.WriteEnvelope(w, 400, false, "Search query must be at least 2 characters", map[string]any{"q": []string{"Ensure this field has at least 2 characters."}}, nil)
		return
	}
	limit, _ := strconv.Atoi(r.URL.Query().Get("limit"))
	if limit < 1 {
		limit = 10
	}
	if limit > 50 {
		limit = 50
	}
	var cats []string
	if raw := r.URL.Query().Get("categories"); raw != "" {
		for _, v := range strings.Split(raw, ",") {
			v = strings.ToLower(strings.TrimSpace(v))
			if v == "users" || v == "classes" || v == "files" || v == "friends" || v == "library" {
				cats = append(cats, v)
			}
		}
	}
	data, err := a.Repository.Search(r.Context(), uid, q, limit, cats)
	if err != nil {
		httpx.WriteEnvelope(w, 500, false, "An error occurred while searching", nil, nil)
		return
	}
	httpx.WriteEnvelope(w, 200, true, "Found "+strconv.Itoa(data["total_results"].(int))+" result(s) for '"+q+"'", data, nil)
}
func (a App) suggestions(w http.ResponseWriter, r *http.Request) {
	q := strings.TrimSpace(r.URL.Query().Get("q"))
	if q == "" {
		httpx.WriteEnvelope(w, 400, false, "Query is required", nil, nil)
		return
	}
	limit, _ := strconv.Atoi(r.URL.Query().Get("limit"))
	if limit < 1 {
		limit = 5
	}
	if limit > 10 {
		limit = 10
	}
	items, err := a.Repository.Suggestions(r.Context(), q, limit)
	if err != nil {
		httpx.WriteEnvelope(w, 503, false, "Search service unavailable", nil, nil)
		return
	}
	httpx.WriteEnvelope(w, 200, true, strconv.Itoa(len(items))+" suggestion(s)", items, nil)
}
func (a App) history(w http.ResponseWriter, r *http.Request, uid int64) {
	items, err := a.Repository.History(r.Context(), uid)
	if err != nil {
		httpx.WriteEnvelope(w, 503, false, "Search history unavailable", nil, nil)
		return
	}
	httpx.WriteEnvelope(w, 200, true, strconv.Itoa(len(items))+" recent search(es)", items, nil)
}
func (a App) clearHistory(w http.ResponseWriter, r *http.Request, uid int64) {
	if err := a.Repository.ClearHistory(r.Context(), uid); err != nil {
		httpx.WriteEnvelope(w, 503, false, "Search history unavailable", nil, nil)
		return
	}
	httpx.WriteEnvelope(w, 200, true, "Cleared search history", nil, nil)
}
