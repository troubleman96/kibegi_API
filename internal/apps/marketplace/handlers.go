package marketplace

import (
	"encoding/json"
	"errors"
	"net/http"
	"strconv"
	"strings"

	"github.com/google/uuid"
	"github.com/troubleman96/kibegi_API/internal/apps/authentication"
	"github.com/troubleman96/kibegi_API/internal/platform/httpx"
)

type App struct {
	Repository Repository
	Auth       *authentication.TokenService
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
			httpx.WriteEnvelope(w, http.StatusUnauthorized, false, "Authentication credentials were not provided.", nil, nil)
			return
		}
		rest := strings.Trim(strings.TrimPrefix(r.URL.Path, "/api/v1/marketplace/"), "/")
		parts := strings.Split(rest, "/")
		switch {
		case rest == "categories":
			a.categories(w, r)
		case len(parts) == 2 && parts[0] == "categories":
			a.categoryDetail(w, r, parts[1])
		case rest == "listings" && r.Method == http.MethodGet:
			a.listings(w, r, userID, "")
		case rest == "listings" && r.Method == http.MethodPost:
			a.createListing(w, r, userID)
		case rest == "listings/search":
			a.listings(w, r, userID, r.URL.Query().Get("q"))
		case rest == "listings/me":
			a.listingsMode(w, r, userID, "me")
		case len(parts) == 2 && parts[0] == "listings" && parts[1] != "search" && parts[1] != "me":
			a.listingDetail(w, r, userID, parts[1])
		case len(parts) == 3 && parts[0] == "listings" && parts[2] == "purchase":
			a.purchase(w, r, userID, parts[1])
		case rest == "orders":
			a.orders(w, r, userID, "")
		case len(parts) == 2 && parts[0] == "orders":
			a.orders(w, r, userID, parts[1])
		default:
			httpx.WriteEnvelope(w, http.StatusNotFound, false, "Not found", nil, nil)
		}
	}))
}

func (a App) categories(w http.ResponseWriter, r *http.Request) {
	items, err := a.Repository.Categories(r.Context(), true)
	if err != nil {
		httpx.WriteEnvelope(w, 503, false, "Marketplace service unavailable", nil, nil)
		return
	}
	httpx.WriteEnvelope(w, 200, true, "Categories retrieved successfully", items, nil)
}
func (a App) categoryDetail(w http.ResponseWriter, r *http.Request, slug string) {
	item, err := a.Repository.FindCategory(r.Context(), slug)
	if errors.Is(err, ErrCategoryNotFound) {
		httpx.WriteEnvelope(w, 404, false, "Category not found", nil, nil)
		return
	}
	if err != nil {
		httpx.WriteEnvelope(w, 503, false, "Marketplace service unavailable", nil, nil)
		return
	}
	httpx.WriteEnvelope(w, 200, true, "Category retrieved successfully", item, nil)
}

func (a App) listings(w http.ResponseWriter, r *http.Request, userID int64, query string) {
	p := parsePagination(r)
	items, count, err := a.Repository.Listings(r.Context(), userID, query, r.URL.Query().Get("category"), "", p.Limit, p.Offset)
	if err != nil {
		httpx.WriteEnvelope(w, 503, false, "Marketplace service unavailable", nil, nil)
		return
	}
	results := make([]Listing, 0, len(items))
	for _, item := range items {
		results = append(results, a.withURLs(r, item))
	}
	httpx.WriteJSON(w, 200, buildPage(r, p, count, results))
}
func (a App) listingsMode(w http.ResponseWriter, r *http.Request, userID int64, mode string) {
	p := parsePagination(r)
	items, count, err := a.Repository.Listings(r.Context(), userID, "", "", mode, p.Limit, p.Offset)
	if err != nil {
		httpx.WriteEnvelope(w, 503, false, "Marketplace service unavailable", nil, nil)
		return
	}
	httpx.WriteJSON(w, 200, buildPage(r, p, count, items))
}

func (a App) createListing(w http.ResponseWriter, r *http.Request, userID int64) {
	var input Listing
	if err := json.NewDecoder(r.Body).Decode(&input); err != nil {
		httpx.WriteEnvelope(w, 400, false, "Invalid listing details", nil, nil)
		return
	}
	item, err := a.Repository.CreateListing(r.Context(), userID, input)
	if err != nil {
		httpx.WriteEnvelope(w, 400, false, err.Error(), nil, nil)
		return
	}
	httpx.WriteEnvelope(w, 201, true, "Listing created successfully", a.withURLs(r, item), nil)
}
func (a App) listingDetail(w http.ResponseWriter, r *http.Request, userID int64, code string) {
	item, err := a.Repository.FindListing(r.Context(), code)
	if errors.Is(err, ErrListingNotFound) {
		httpx.WriteEnvelope(w, 404, false, "Listing not found", nil, nil)
		return
	}
	if err != nil {
		httpx.WriteEnvelope(w, 503, false, "Marketplace service unavailable", nil, nil)
		return
	}
	switch r.Method {
	case http.MethodGet:
		httpx.WriteEnvelope(w, 200, true, "Listing retrieved successfully", a.withURLs(r, item), nil)
	case http.MethodPatch, http.MethodPut:
		if item.Seller.ID != userID {
			httpx.WriteEnvelope(w, 403, false, "You do not have permission to update this listing", nil, nil)
			return
		}
		var input Listing
		if err := json.NewDecoder(r.Body).Decode(&input); err != nil {
			httpx.WriteEnvelope(w, 400, false, "Invalid listing details", nil, nil)
			return
		}
		updated, err := a.Repository.UpdateListing(r.Context(), userID, code, input)
		if err != nil {
			httpx.WriteEnvelope(w, 400, false, err.Error(), nil, nil)
			return
		}
		httpx.WriteEnvelope(w, 200, true, "Listing updated successfully", a.withURLs(r, updated), nil)
	case http.MethodDelete:
		if item.Seller.ID != userID {
			httpx.WriteEnvelope(w, 403, false, "You do not have permission to delete this listing", nil, nil)
			return
		}
		if err := a.Repository.DeleteListing(r.Context(), userID, code); err != nil {
			httpx.WriteEnvelope(w, 503, false, "Marketplace service unavailable", nil, nil)
			return
		}
		httpx.WriteEnvelope(w, 200, true, "Listing deleted successfully", nil, nil)
	default:
		httpx.WriteEnvelope(w, 405, false, "method not allowed", nil, nil)
	}
}
func (a App) purchase(w http.ResponseWriter, r *http.Request, userID int64, code string) {
	if r.Method != http.MethodPost {
		httpx.WriteEnvelope(w, 405, false, "method not allowed", nil, nil)
		return
	}
	var input struct {
		Quantity int `json:"quantity"`
	}
	if err := json.NewDecoder(r.Body).Decode(&input); err != nil {
		input.Quantity = 1
	}
	if input.Quantity == 0 {
		input.Quantity = 1
	}
	order, err := a.Repository.Purchase(r.Context(), userID, code, input.Quantity)
	if errors.Is(err, ErrOutOfStock) {
		httpx.WriteEnvelope(w, 400, false, err.Error(), nil, nil)
		return
	}
	if errors.Is(err, ErrListingNotFound) {
		httpx.WriteEnvelope(w, 404, false, "Listing not found", nil, nil)
		return
	}
	if err != nil {
		httpx.WriteEnvelope(w, 503, false, "Marketplace service unavailable", nil, nil)
		return
	}
	httpx.WriteEnvelope(w, 201, true, "Purchase completed successfully", order, nil)
}
func (a App) orders(w http.ResponseWriter, r *http.Request, userID int64, rawID string) {
	if rawID != "" {
		id, err := uuid.Parse(rawID)
		if err != nil {
			httpx.WriteEnvelope(w, 404, false, "Order not found", nil, nil)
			return
		}
		order, err := a.Repository.FindOrder(r.Context(), id, userID)
		if errors.Is(err, ErrOrderNotFound) {
			httpx.WriteEnvelope(w, 404, false, "Order not found", nil, nil)
			return
		}
		if err != nil {
			httpx.WriteEnvelope(w, 503, false, "Marketplace service unavailable", nil, nil)
			return
		}
		httpx.WriteEnvelope(w, 200, true, "Order retrieved successfully", order, nil)
		return
	}
	p := parsePagination(r)
	items, count, err := a.Repository.Orders(r.Context(), userID, p.Limit, p.Offset)
	if err != nil {
		httpx.WriteEnvelope(w, 503, false, "Marketplace service unavailable", nil, nil)
		return
	}
	httpx.WriteJSON(w, 200, buildPage(r, p, count, items))
}
func (a App) withURLs(r *http.Request, item Listing) Listing {
	if path, ok := item.Image.(string); ok && path != "" {
		if a.MediaBase != "" {
			item.Image = strings.TrimRight(a.MediaBase, "/") + "/" + strings.TrimLeft(path, "/")
		}
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
