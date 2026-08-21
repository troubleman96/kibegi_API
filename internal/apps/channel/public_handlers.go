package channel

import (
	"database/sql"
	"errors"
	"net/http"
	"strings"

	"github.com/google/uuid"
	"github.com/troubleman96/kibegi_API/internal/apps/authentication"
	"github.com/troubleman96/kibegi_API/internal/platform/httpx"
)

func (a App) PublicHandler() http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		parts := strings.Split(strings.Trim(strings.TrimPrefix(r.URL.Path, "/api/v1/public/channel/"), "/"), "/")
		if len(parts) != 2 {
			httpx.WriteEnvelope(w, http.StatusNotFound, false, "Channel not found", nil, nil)
			return
		}
		if parts[1] == "info" && r.Method == http.MethodGet {
			a.publicInfo(w, r, parts[0])
			return
		}
		if parts[1] == "join" && r.Method == http.MethodPost {
			a.publicJoin(w, r, parts[0])
			return
		}
		httpx.WriteEnvelope(w, http.StatusNotFound, false, "Not found", nil, nil)
	})
}

func (a App) publicInfo(w http.ResponseWriter, r *http.Request, token string) {
	var item Channel
	err := a.Repository.DB.QueryRowContext(r.Context(), `SELECT c.id,c.name,COALESCE(c.description,''),c.visibility,c.invite_token,c.is_active,c.created_by,c.created_at,c.updated_at,(SELECT COUNT(*) FROM channel_channelmember m WHERE m.channel_id=c.id AND m.is_active),(SELECT COUNT(*) FROM channel_channelbroadcast b WHERE b.channel_id=c.id AND b.is_active) FROM channel_channel c WHERE c.invite_token=$1 AND c.is_active=true`, token).Scan(&item.ID, &item.Name, &item.Description, &item.Visibility, &item.InviteToken, &item.IsActive, &item.CreatedBy, &item.CreatedAt, &item.UpdatedAt, &item.MemberCount, &item.BroadcastCount)
	if errors.Is(err, sql.ErrNoRows) {
		httpx.WriteEnvelope(w, http.StatusNotFound, false, "Channel not found", nil, nil)
		return
	}
	if err != nil {
		httpx.WriteEnvelope(w, http.StatusServiceUnavailable, false, "Channel service unavailable", nil, nil)
		return
	}
	data := map[string]any{"id": item.ID, "name": item.Name, "description": item.Description, "visibility": item.Visibility, "invite_token": item.InviteToken, "is_active": item.IsActive, "created_by": item.CreatedBy, "member_count": item.MemberCount, "broadcast_count": item.BroadcastCount, "join_hint": "Create a Kibegi account, then join this channel to receive campaign messages."}
	httpx.WriteEnvelope(w, http.StatusOK, true, "Channel info retrieved successfully", data, nil)
}

func (a App) publicJoin(w http.ResponseWriter, r *http.Request, token string) {
	wrapped := authentication.RequireAuth(a.Auth, http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		userID, ok := authentication.UserIDFromContext(r.Context())
		if !ok {
			httpx.WriteEnvelope(w, 401, false, "Authentication credentials were not provided.", nil, nil)
			return
		}
		var id uuid.UUID
		if err := a.Repository.DB.QueryRowContext(r.Context(), `SELECT id FROM channel_channel WHERE invite_token=$1 AND is_active=true`, token).Scan(&id); err != nil {
			httpx.WriteEnvelope(w, 404, false, "Channel not found", nil, nil)
			return
		}
		member, err := a.Repository.Join(r.Context(), id, userID)
		if err != nil {
			httpx.WriteEnvelope(w, 400, false, err.Error(), nil, nil)
			return
		}
		httpx.WriteEnvelope(w, 201, true, "Channel joined successfully", member, nil)
	}))
	wrapped.ServeHTTP(w, r)
}
