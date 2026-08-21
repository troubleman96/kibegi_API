package friends

import (
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
	MediaBase  string
}

type pagination struct {
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
	return authentication.RequireAuth(a.Auth, http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		userID, ok := authentication.UserIDFromContext(r.Context())
		if !ok {
			httpx.WriteEnvelope(w, http.StatusUnauthorized, false, "Authentication credentials were not provided.", nil, nil)
			return
		}
		rest := strings.Trim(strings.TrimPrefix(r.URL.Path, "/api/v1/friends/"), "/")
		parts := strings.Split(rest, "/")
		switch {
		case rest == "" && r.Method == http.MethodGet:
			a.list(w, r, userID, "")
		case rest == "search":
			a.search(w, r, userID)
		case rest == "add":
			a.add(w, r, userID)
		case rest == "requests/incoming":
			a.directional(w, r, userID, "incoming")
		case rest == "requests/sent":
			a.directional(w, r, userID, "sent")
		case len(parts) == 2 && parts[1] == "accept":
			a.transition(w, r, userID, parts[0], "accept")
		case len(parts) == 2 && parts[1] == "decline":
			a.transition(w, r, userID, parts[0], "decline")
		case len(parts) == 2 && parts[1] == "cancel":
			a.transition(w, r, userID, parts[0], "cancel")
		case len(parts) == 2 && parts[1] == "nickname":
			a.nickname(w, r, userID, parts[0])
		case len(parts) == 1 && parts[0] != "":
			a.remove(w, r, userID, parts[0])
		default:
			httpx.WriteEnvelope(w, http.StatusMethodNotAllowed, false, "method not allowed", nil, nil)
		}
	}))
}

func (a App) list(w http.ResponseWriter, r *http.Request, userID int64, status string) {
	page := parsePagination(r)
	items, count, err := a.Repository.List(r.Context(), userID, status, page.Limit, page.Offset)
	if err != nil {
		httpx.WriteEnvelope(w, http.StatusServiceUnavailable, false, "Friends service unavailable", nil, nil)
		return
	}
	results := make([]map[string]any, 0, len(items))
	for _, item := range items {
		results = append(results, a.listPayload(r, userID, item))
	}
	httpx.WriteJSON(w, http.StatusOK, buildPage(r, page, count, results))
}

func (a App) directional(w http.ResponseWriter, r *http.Request, userID int64, direction string) {
	page := parsePagination(r)
	var items []Friendship
	var count int
	var err error
	if direction == "incoming" {
		items, count, err = a.Repository.Incoming(r.Context(), userID, page.Limit, page.Offset)
	} else {
		items, count, err = a.Repository.Sent(r.Context(), userID, page.Limit, page.Offset)
	}
	if err != nil {
		httpx.WriteEnvelope(w, http.StatusServiceUnavailable, false, "Friends service unavailable", nil, nil)
		return
	}
	results := make([]map[string]any, 0, len(items))
	for _, item := range items {
		results = append(results, a.requestPayload(r, item))
	}
	httpx.WriteJSON(w, http.StatusOK, buildPage(r, page, count, results))
}

func (a App) search(w http.ResponseWriter, r *http.Request, userID int64) {
	users, err := a.Repository.SearchUsers(r.Context(), userID, r.URL.Query().Get("q"), 20)
	if err != nil {
		httpx.WriteEnvelope(w, http.StatusServiceUnavailable, false, "Friends service unavailable", nil, nil)
		return
	}
	results := make([]map[string]any, 0, len(users))
	for _, user := range users {
		results = append(results, a.userPayload(r, user))
	}
	httpx.WriteEnvelope(w, http.StatusOK, true, "Users found successfully", results, nil)
}

func (a App) add(w http.ResponseWriter, r *http.Request, userID int64) {
	if r.Method != http.MethodPost {
		w.Header().Set("Allow", http.MethodPost)
		httpx.WriteEnvelope(w, http.StatusMethodNotAllowed, false, "method not allowed", nil, nil)
		return
	}
	var input struct {
		UserID *int64 `json:"user_id"`
		Email  string `json:"email"`
	}
	if err := json.NewDecoder(r.Body).Decode(&input); err != nil || (input.UserID == nil && strings.TrimSpace(input.Email) == "") {
		httpx.WriteEnvelope(w, http.StatusBadRequest, false, "Either user_id or email must be provided", nil, nil)
		return
	}
	target, err := a.Repository.FindUser(r.Context(), input.UserID, strings.TrimSpace(input.Email))
	if errors.Is(err, ErrFriendNotFound) {
		httpx.WriteEnvelope(w, http.StatusBadRequest, false, "User not found", nil, nil)
		return
	}
	if err != nil {
		httpx.WriteEnvelope(w, http.StatusServiceUnavailable, false, "Friends service unavailable", nil, nil)
		return
	}
	item, err := a.Repository.Add(r.Context(), userID, target.ID)
	if errors.Is(err, ErrSelfFriend) || errors.Is(err, ErrFriendExists) {
		httpx.WriteEnvelope(w, http.StatusBadRequest, false, err.Error(), nil, nil)
		return
	}
	if err != nil {
		httpx.WriteEnvelope(w, http.StatusServiceUnavailable, false, "Friends service unavailable", nil, nil)
		return
	}
	httpx.WriteEnvelope(w, http.StatusCreated, true, "Friend request sent successfully", a.detailPayload(r, item), nil)
}

func (a App) transition(w http.ResponseWriter, r *http.Request, userID int64, rawID, action string) {
	if r.Method != http.MethodPost {
		w.Header().Set("Allow", http.MethodPost)
		httpx.WriteEnvelope(w, http.StatusMethodNotAllowed, false, "method not allowed", nil, nil)
		return
	}
	id, err := strconv.ParseInt(rawID, 10, 64)
	if err != nil {
		httpx.WriteEnvelope(w, http.StatusNotFound, false, "Friendship not found", nil, nil)
		return
	}
	item, err := a.Repository.Transition(r.Context(), id, userID, action)
	if errors.Is(err, ErrFriendNotFound) {
		httpx.WriteEnvelope(w, http.StatusNotFound, false, "Friendship not found", nil, nil)
		return
	}
	if err != nil {
		httpx.WriteEnvelope(w, http.StatusServiceUnavailable, false, "Friends service unavailable", nil, nil)
		return
	}
	if action != "accept" {
		httpx.WriteEnvelope(w, http.StatusOK, true, "Friend request "+action+"ed successfully", nil, nil)
		return
	}
	httpx.WriteEnvelope(w, http.StatusOK, true, "Friend request accepted successfully", a.detailPayload(r, item), nil)
}

func (a App) nickname(w http.ResponseWriter, r *http.Request, userID int64, rawID string) {
	if r.Method != http.MethodPatch && r.Method != http.MethodPut {
		w.Header().Set("Allow", "PATCH, PUT")
		httpx.WriteEnvelope(w, http.StatusMethodNotAllowed, false, "method not allowed", nil, nil)
		return
	}
	id, err := strconv.ParseInt(rawID, 10, 64)
	if err != nil {
		httpx.WriteEnvelope(w, http.StatusNotFound, false, "Friendship not found", nil, nil)
		return
	}
	var input struct {
		Nickname string `json:"nickname"`
	}
	if err := json.NewDecoder(r.Body).Decode(&input); err != nil || len([]rune(input.Nickname)) > 100 {
		httpx.WriteEnvelope(w, http.StatusBadRequest, false, "Invalid nickname", nil, nil)
		return
	}
	if err := a.Repository.UpdateNickname(r.Context(), id, userID, input.Nickname); errors.Is(err, ErrFriendNotFound) {
		httpx.WriteEnvelope(w, http.StatusNotFound, false, "Friendship not found", nil, nil)
		return
	} else if err != nil {
		httpx.WriteEnvelope(w, http.StatusServiceUnavailable, false, "Friends service unavailable", nil, nil)
		return
	}
	httpx.WriteEnvelope(w, http.StatusOK, true, "Nickname updated successfully", nil, nil)
}

func (a App) remove(w http.ResponseWriter, r *http.Request, userID int64, rawID string) {
	if r.Method != http.MethodDelete {
		w.Header().Set("Allow", http.MethodDelete)
		httpx.WriteEnvelope(w, http.StatusMethodNotAllowed, false, "method not allowed", nil, nil)
		return
	}
	id, err := strconv.ParseInt(rawID, 10, 64)
	if err != nil {
		httpx.WriteEnvelope(w, http.StatusNotFound, false, "Friendship not found", nil, nil)
		return
	}
	if err := a.Repository.Remove(r.Context(), id, userID); errors.Is(err, ErrFriendNotFound) {
		httpx.WriteEnvelope(w, http.StatusNotFound, false, "Friendship not found", nil, nil)
		return
	} else if err != nil {
		httpx.WriteEnvelope(w, http.StatusServiceUnavailable, false, "Friends service unavailable", nil, nil)
		return
	}
	httpx.WriteEnvelope(w, http.StatusOK, true, "Friend removed successfully", nil, nil)
}

func (a App) userPayload(r *http.Request, user User) map[string]any {
	return map[string]any{"id": user.ID, "email": user.Email, "full_name": user.FullName, "user_type": user.UserType, "profile_image": user.ProfileImage, "profile_image_url": a.mediaURL(r, user.ProfileImage)}
}

func (a App) listPayload(r *http.Request, currentID int64, item Friendship) map[string]any {
	other := item.User
	nickname := ""
	if item.UserID == currentID {
		other = item.Friend
		nickname = item.Nickname
	}
	displayName := other.FullName
	if nickname != "" {
		displayName = nickname
	}
	return map[string]any{"id": item.ID, "friend_info": a.userPayload(r, other), "nickname": nickname, "display_name": displayName, "status": item.Status, "created_at": item.CreatedAt}
}

func (a App) requestPayload(r *http.Request, item Friendship) map[string]any {
	return map[string]any{"id": item.ID, "sender_id": item.User.ID, "sender_email": item.User.Email, "sender_name": item.User.FullName, "sender_type": item.User.UserType, "sender_profile_image": item.User.ProfileImage, "sender_profile_image_url": a.mediaURL(r, item.User.ProfileImage), "recipient_id": item.Friend.ID, "recipient_email": item.Friend.Email, "recipient_name": item.Friend.FullName, "recipient_type": item.Friend.UserType, "recipient_profile_image": item.Friend.ProfileImage, "recipient_profile_image_url": a.mediaURL(r, item.Friend.ProfileImage), "status": item.Status, "created_at": item.CreatedAt}
}

func (a App) detailPayload(r *http.Request, item Friendship) map[string]any {
	return map[string]any{"id": item.ID, "user": item.UserID, "user_email": item.User.Email, "user_name": item.User.FullName, "user_profile_image": item.User.ProfileImage, "user_profile_image_url": a.mediaURL(r, item.User.ProfileImage), "friend": item.FriendID, "friend_email": item.Friend.Email, "friend_name": item.Friend.FullName, "friend_profile_image": item.Friend.ProfileImage, "friend_profile_image_url": a.mediaURL(r, item.Friend.ProfileImage), "nickname": item.Nickname, "display_name": item.Friend.FullName, "status": item.Status, "created_at": item.CreatedAt, "accepted_at": item.AcceptedAt}
}

func (a App) mediaURL(r *http.Request, value any) any {
	path, ok := value.(string)
	if !ok || path == "" {
		return nil
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
	page := positive(r.URL.Query().Get("page"), 1)
	limit := positive(r.URL.Query().Get("page_size"), 20)
	if limit > 100 {
		limit = 100
	}
	return pagination{Limit: limit, Offset: (page - 1) * limit, Page: page}
}

func buildPage(r *http.Request, page pagination, count int, results any) pageResponse {
	next, previous := "", ""
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
