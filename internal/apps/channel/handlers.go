package channel

import (
	"database/sql"
	"encoding/json"
	"errors"
	"net/http"
	"strings"

	"github.com/google/uuid"
	"github.com/troubleman96/kibegi_API/internal/apps/authentication"
	"github.com/troubleman96/kibegi_API/internal/platform/httpx"
)

type App struct {
	Repository Repository
	Auth       *authentication.TokenService
}

func (a App) PathHandler() http.Handler {
	return authentication.RequireAuth(a.Auth, http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		userID, ok := authentication.UserIDFromContext(r.Context())
		if !ok {
			httpx.WriteEnvelope(w, 401, false, "Authentication credentials were not provided.", nil, nil)
			return
		}
		rest := strings.Trim(strings.TrimPrefix(r.URL.Path, "/api/v1/channel/"), "/")
		parts := strings.Split(rest, "/")
		switch {
		case rest == "channels" && r.Method == http.MethodGet:
			a.list(w, r, userID)
		case rest == "channels" && r.Method == http.MethodPost:
			a.create(w, r, userID)
		case len(parts) == 2 && parts[0] == "channels" && parts[1] == "join":
			httpx.WriteEnvelope(w, 404, false, "Channel not found", nil, nil)
		case len(parts) == 3 && parts[0] == "channels" && parts[2] == "join":
			a.join(w, r, userID, parts[1])
		case len(parts) == 3 && parts[0] == "channels" && parts[2] == "members":
			a.members(w, r, userID, parts[1])
		case len(parts) == 3 && parts[0] == "channels" && parts[2] == "wallet":
			a.wallet(w, r, userID, parts[1])
		case len(parts) == 3 && parts[0] == "channels" && parts[2] == "broadcasts":
			a.broadcasts(w, r, userID, parts[1])
		case len(parts) == 2 && parts[0] == "channels":
			a.detail(w, r, userID, parts[1])
		case len(parts) == 2 && parts[0] == "members":
			a.removeMember(w, r, userID, parts[1])
		case len(parts) == 2 && parts[0] == "broadcasts" && r.Method == http.MethodGet:
			a.broadcastDetail(w, r, userID, parts[1])
		default:
			httpx.WriteEnvelope(w, 404, false, "Not found", nil, nil)
		}
	}))
}
func (a App) list(w http.ResponseWriter, r *http.Request, userID int64) {
	items, err := a.Repository.List(r.Context(), userID)
	if err != nil {
		httpx.WriteEnvelope(w, 503, false, "Channel service unavailable", nil, nil)
		return
	}
	httpx.WriteEnvelope(w, 200, true, "Channels retrieved successfully", items, nil)
}
func (a App) create(w http.ResponseWriter, r *http.Request, userID int64) {
	var input Channel
	if err := json.NewDecoder(r.Body).Decode(&input); err != nil || strings.TrimSpace(input.Name) == "" {
		httpx.WriteEnvelope(w, 400, false, "Channel name is required.", nil, nil)
		return
	}
	if input.Visibility == "" {
		input.Visibility = "public"
	}
	item, err := a.Repository.Create(r.Context(), userID, input)
	if err != nil {
		httpx.WriteEnvelope(w, 400, false, err.Error(), nil, nil)
		return
	}
	httpx.WriteEnvelope(w, 201, true, "Channel created successfully", item, nil)
}
func (a App) detail(w http.ResponseWriter, r *http.Request, userID int64, raw string) {
	id, err := uuid.Parse(raw)
	if err != nil {
		httpx.WriteEnvelope(w, 404, false, "Channel not found", nil, nil)
		return
	}
	item, err := a.Repository.Find(r.Context(), userID, id)
	if errors.Is(err, ErrChannelNotFound) {
		httpx.WriteEnvelope(w, 404, false, "Channel not found", nil, nil)
		return
	}
	if err != nil {
		httpx.WriteEnvelope(w, 503, false, "Channel service unavailable", nil, nil)
		return
	}
	if r.Method == http.MethodGet {
		httpx.WriteEnvelope(w, 200, true, "Channel retrieved successfully", item, nil)
		return
	}
	if r.Method != http.MethodPatch && r.Method != http.MethodPut {
		httpx.WriteEnvelope(w, 405, false, "method not allowed", nil, nil)
		return
	}
	if item.CreatedBy != userID {
		httpx.WriteEnvelope(w, 403, false, "You do not have permission to update this channel", nil, nil)
		return
	}
	var input Channel
	if err := json.NewDecoder(r.Body).Decode(&input); err != nil {
		httpx.WriteEnvelope(w, 400, false, "Invalid input", nil, nil)
		return
	}
	_, err = a.Repository.DB.ExecContext(r.Context(), `UPDATE channel_channel SET name=$3,description=$4,visibility=$5,updated_at=NOW() WHERE id=$1 AND created_by_id=$2`, id, userID, input.Name, input.Description, input.Visibility)
	if err != nil {
		httpx.WriteEnvelope(w, 503, false, "Channel service unavailable", nil, nil)
		return
	}
	updated, _ := a.Repository.Find(r.Context(), userID, id)
	httpx.WriteEnvelope(w, 200, true, "Channel updated successfully", updated, nil)
}
func (a App) join(w http.ResponseWriter, r *http.Request, userID int64, raw string) {
	id, err := uuid.Parse(raw)
	if err != nil {
		httpx.WriteEnvelope(w, 404, false, "Channel not found", nil, nil)
		return
	}
	member, err := a.Repository.Join(r.Context(), id, userID)
	if err != nil {
		httpx.WriteEnvelope(w, 400, false, err.Error(), nil, nil)
		return
	}
	httpx.WriteEnvelope(w, 200, true, "Joined channel successfully", member, nil)
}
func (a App) members(w http.ResponseWriter, r *http.Request, userID int64, raw string) {
	id, err := uuid.Parse(raw)
	if err != nil {
		httpx.WriteEnvelope(w, 404, false, "Channel not found", nil, nil)
		return
	}
	if _, err := a.Repository.Find(r.Context(), userID, id); err != nil {
		httpx.WriteEnvelope(w, 404, false, "Channel not found", nil, nil)
		return
	}
	if r.Method == http.MethodGet {
		items, err := a.Repository.Members(r.Context(), id)
		if err != nil {
			httpx.WriteEnvelope(w, 503, false, "Channel service unavailable", nil, nil)
			return
		}
		httpx.WriteEnvelope(w, 200, true, "Channel members retrieved successfully", items, nil)
		return
	}
	if r.Method != http.MethodPost {
		httpx.WriteEnvelope(w, 405, false, "method not allowed", nil, nil)
		return
	}
	var input struct {
		Identifier string `json:"identifier"`
		Role       string `json:"role"`
	}
	if err := json.NewDecoder(r.Body).Decode(&input); err != nil {
		httpx.WriteEnvelope(w, 400, false, "Invalid member input", nil, nil)
		return
	}
	target, err := a.Repository.FindUser(r.Context(), input.Identifier)
	if err != nil {
		httpx.WriteEnvelope(w, 404, false, "User not found", nil, nil)
		return
	}
	if input.Role == "" {
		input.Role = "member"
	}
	member, err := a.Repository.UpsertMember(r.Context(), id, target.ID, userID, input.Role)
	if err != nil {
		httpx.WriteEnvelope(w, 400, false, err.Error(), nil, nil)
		return
	}
	httpx.WriteEnvelope(w, 201, true, "Channel member added successfully", member, nil)
}
func (a App) removeMember(w http.ResponseWriter, r *http.Request, userID int64, raw string) {
	if r.Method != http.MethodDelete {
		httpx.WriteEnvelope(w, 405, false, "method not allowed", nil, nil)
		return
	}
	id, err := uuid.Parse(raw)
	if err != nil {
		httpx.WriteEnvelope(w, 404, false, "Channel member not found", nil, nil)
		return
	}
	if err := a.Repository.RemoveMember(r.Context(), id, userID); err != nil {
		httpx.WriteEnvelope(w, 403, false, err.Error(), nil, nil)
		return
	}
	httpx.WriteEnvelope(w, 200, true, "Channel member removed successfully", nil, nil)
}
func (a App) wallet(w http.ResponseWriter, r *http.Request, userID int64, raw string) {
	id, err := uuid.Parse(raw)
	if err != nil {
		httpx.WriteEnvelope(w, 404, false, "Channel not found", nil, nil)
		return
	}
	if _, err := a.Repository.Find(r.Context(), userID, id); err != nil {
		httpx.WriteEnvelope(w, 404, false, "Channel not found", nil, nil)
		return
	}
	wallet, err := a.Repository.Wallet(r.Context(), id)
	if err != nil {
		httpx.WriteEnvelope(w, 503, false, "Channel wallet unavailable", nil, nil)
		return
	}
	httpx.WriteEnvelope(w, 200, true, "Channel wallet retrieved successfully", wallet, nil)
}
func (a App) broadcastDetail(w http.ResponseWriter, r *http.Request, userID int64, raw string) {
	id, err := uuid.Parse(raw)
	if err != nil {
		httpx.WriteEnvelope(w, 404, false, "Channel broadcast not found", nil, nil)
		return
	}
	item, err := a.Repository.FindBroadcast(r.Context(), id)
	if errors.Is(err, sql.ErrNoRows) {
		httpx.WriteEnvelope(w, 404, false, "Channel broadcast not found", nil, nil)
		return
	}
	if err != nil {
		httpx.WriteEnvelope(w, 503, false, "Channel service unavailable", nil, nil)
		return
	}
	if _, err := a.Repository.Find(r.Context(), userID, item.ChannelID); err != nil {
		httpx.WriteEnvelope(w, 403, false, "You do not have permission to view this broadcast", nil, nil)
		return
	}
	httpx.WriteEnvelope(w, 200, true, "Channel broadcast retrieved successfully", item, nil)
}

func (a App) broadcasts(w http.ResponseWriter, r *http.Request, userID int64, raw string) {
	if r.Method != http.MethodPost {
		httpx.WriteEnvelope(w, 405, false, "method not allowed", nil, nil)
		return
	}
	id, err := uuid.Parse(raw)
	if err != nil {
		httpx.WriteEnvelope(w, 404, false, "Channel not found", nil, nil)
		return
	}
	channel, err := a.Repository.Find(r.Context(), userID, id)
	if err != nil || (!channel.IsMember && channel.CreatedBy != userID) {
		httpx.WriteEnvelope(w, 403, false, "You do not have permission to broadcast", nil, nil)
		return
	}
	var input struct {
		Subject string `json:"subject"`
		Message string `json:"message"`
		Venue   string `json:"venue"`
	}
	if err := json.NewDecoder(r.Body).Decode(&input); err != nil || strings.TrimSpace(input.Message) == "" {
		httpx.WriteEnvelope(w, 400, false, "Message is required", nil, nil)
		return
	}
	broadcast, err := a.Repository.CreateBroadcast(r.Context(), id, userID, input.Subject, input.Message, input.Venue)
	if err != nil {
		httpx.WriteEnvelope(w, 503, false, "Channel service unavailable", nil, nil)
		return
	}
	httpx.WriteEnvelope(w, 201, true, "Broadcast created successfully", broadcast, nil)
}
