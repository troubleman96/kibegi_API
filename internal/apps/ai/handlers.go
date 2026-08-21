package ai

import (
	"context"
	"database/sql"
	"encoding/json"
	"errors"
	"net/http"
	"strings"

	"github.com/google/uuid"
	"github.com/troubleman96/kibegi_API/internal/apps/authentication"
	"github.com/troubleman96/kibegi_API/internal/platform/httpx"
)

type ChatProvider interface {
	Chat(ctx context.Context, userID int64, message string, conversationID *uuid.UUID, classID *uuid.UUID) (map[string]any, error)
}
type App struct {
	Repository   Repository
	Auth         *authentication.TokenService
	DefaultModel string
	Provider     ChatProvider
}

func (a App) PathHandler() http.Handler {
	return authentication.RequireAuth(a.Auth, http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		userID, ok := authentication.UserIDFromContext(r.Context())
		if !ok {
			httpx.WriteEnvelope(w, 401, false, "Authentication credentials were not provided.", nil, nil)
			return
		}
		rest := strings.Trim(strings.TrimPrefix(r.URL.Path, "/api/v1/ai/"), "/")
		parts := strings.Split(rest, "/")
		switch {
		case rest == "settings":
			a.settings(w, r, userID)
		case rest == "usage" && r.Method == http.MethodGet:
			a.usage(w, r, userID)
		case rest == "conversations" && r.Method == http.MethodGet:
			a.conversations(w, r, userID)
		case len(parts) == 2 && parts[0] == "conversations":
			a.conversation(w, r, userID, parts[1])
		case rest == "chat" && r.Method == http.MethodPost:
			a.chat(w, r, userID)
		case len(parts) == 2 && parts[0] == "status":
			a.status(w, r, userID, parts[1])
		default:
			httpx.WriteEnvelope(w, 404, false, "Not found", nil, nil)
		}
	}))
}
func (a App) settings(w http.ResponseWriter, r *http.Request, userID int64) {
	model := a.DefaultModel
	if model == "" {
		model = "ngamia-default"
	}
	switch r.Method {
	case http.MethodGet:
		p, err := a.Repository.Profile(r.Context(), userID, model)
		if err != nil {
			httpx.WriteEnvelope(w, 503, false, "AI settings unavailable", nil, nil)
			return
		}
		httpx.WriteEnvelope(w, 200, true, "AI settings retrieved", p, nil)
	case http.MethodPost:
		var input struct {
			APIKey    string `json:"api_key"`
			ChatModel string `json:"chat_model"`
		}
		if err := json.NewDecoder(r.Body).Decode(&input); err != nil || strings.TrimSpace(input.APIKey) == "" {
			httpx.WriteEnvelope(w, 400, false, "api_key is required", nil, nil)
			return
		}
		if len(input.APIKey) > 300 {
			httpx.WriteEnvelope(w, 400, false, "API key is too long", nil, nil)
			return
		}
		if input.ChatModel == "" {
			input.ChatModel = model
		}
		p, err := a.Repository.SaveProfile(r.Context(), userID, strings.TrimSpace(input.APIKey), input.ChatModel)
		if err != nil {
			httpx.WriteEnvelope(w, 503, false, "AI settings unavailable", nil, nil)
			return
		}
		httpx.WriteEnvelope(w, 200, true, "AI settings saved", p, nil)
	case http.MethodDelete:
		if err := a.Repository.ClearProfile(r.Context(), userID); err != nil {
			httpx.WriteEnvelope(w, 503, false, "AI settings unavailable", nil, nil)
			return
		}
		httpx.WriteEnvelope(w, 200, true, "AI settings cleared", nil, nil)
	default:
		httpx.WriteEnvelope(w, 405, false, "method not allowed", nil, nil)
	}
}
func (a App) usage(w http.ResponseWriter, r *http.Request, userID int64) {
	u, err := a.Repository.GetUsage(r.Context(), userID)
	if err != nil {
		httpx.WriteEnvelope(w, 503, false, "AI usage unavailable", nil, nil)
		return
	}
	httpx.WriteEnvelope(w, 200, true, "AI usage retrieved", u, nil)
}
func (a App) conversations(w http.ResponseWriter, r *http.Request, userID int64) {
	items, err := a.Repository.Conversations(r.Context(), userID, r.URL.Query().Get("class_id"))
	if err != nil {
		httpx.WriteEnvelope(w, 503, false, "AI conversations unavailable", nil, nil)
		return
	}
	httpx.WriteEnvelope(w, 200, true, "Conversations retrieved", items, nil)
}
func (a App) conversation(w http.ResponseWriter, r *http.Request, userID int64, raw string) {
	id, err := uuid.Parse(raw)
	if err != nil {
		httpx.WriteEnvelope(w, 404, false, "Conversation not found", nil, nil)
		return
	}
	if r.Method == http.MethodDelete {
		if err := a.Repository.DeleteConversation(r.Context(), userID, id); errors.Is(err, ErrConversationNotFound) {
			httpx.WriteEnvelope(w, 404, false, "Conversation not found", nil, nil)
			return
		} else if err != nil {
			httpx.WriteEnvelope(w, 503, false, "AI conversations unavailable", nil, nil)
			return
		}
		httpx.WriteEnvelope(w, 200, true, "Conversation deleted", nil, nil)
		return
	}
	conv, messages, err := a.Repository.Conversation(r.Context(), userID, id)
	if errors.Is(err, ErrConversationNotFound) {
		httpx.WriteEnvelope(w, 404, false, "Conversation not found", nil, nil)
		return
	}
	if err != nil {
		httpx.WriteEnvelope(w, 503, false, "AI conversations unavailable", nil, nil)
		return
	}
	httpx.WriteEnvelope(w, 200, true, "Conversation retrieved", map[string]any{"id": conv.ID, "title": conv.Title, "class_name": conv.ClassName, "class_id": conv.ClassID, "messages": messages}, nil)
}
func (a App) chat(w http.ResponseWriter, r *http.Request, userID int64) {
	var input struct {
		Message        string `json:"message"`
		ConversationID string `json:"conversation_id"`
		ClassID        string `json:"class_id"`
	}
	if err := json.NewDecoder(r.Body).Decode(&input); err != nil || strings.TrimSpace(input.Message) == "" {
		httpx.WriteEnvelope(w, 400, false, "message is required", nil, nil)
		return
	}
	if len([]rune(input.Message)) > 2000 {
		httpx.WriteEnvelope(w, 400, false, "Message too long (max 2000 characters)", nil, nil)
		return
	}
	if a.Provider == nil {
		httpx.WriteEnvelope(w, 503, false, "AI provider is not configured", nil, nil)
		return
	}
	var conversationID, classID *uuid.UUID
	if input.ConversationID != "" {
		v, err := uuid.Parse(input.ConversationID)
		if err != nil {
			httpx.WriteEnvelope(w, 400, false, "Invalid conversation_id", nil, nil)
			return
		}
		conversationID = &v
	}
	if input.ClassID != "" {
		v, err := uuid.Parse(input.ClassID)
		if err != nil {
			httpx.WriteEnvelope(w, 400, false, "Invalid class_id", nil, nil)
			return
		}
		classID = &v
	}
	data, err := a.Provider.Chat(r.Context(), userID, input.Message, conversationID, classID)
	if err != nil {
		httpx.WriteEnvelope(w, 503, false, "AI provider request failed", nil, nil)
		return
	}
	httpx.WriteEnvelope(w, 200, true, "AI response generated", data, nil)
}
func (a App) status(w http.ResponseWriter, r *http.Request, userID int64, raw string) {
	uploadID, err := uuid.Parse(raw)
	if err != nil {
		httpx.WriteEnvelope(w, 404, false, "Upload not found", nil, nil)
		return
	}
	var x ProcessingStatus
	err = a.Repository.DB.QueryRowContext(r.Context(), `SELECT j.upload_id,u.file,j.status,j.chunks_created,NULLIF(j.error_message,''),j.updated_at FROM ai_aiprocessingjob j JOIN uploads_upload u ON u.id=j.upload_id WHERE j.upload_id=$1 AND u.is_deleted=false`, uploadID).Scan(&x.UploadID, &x.FileName, &x.Status, &x.ChunksCreated, &x.ErrorMessage, &x.UpdatedAt)
	if errors.Is(err, sql.ErrNoRows) {
		x = ProcessingStatus{UploadID: uploadID, Status: "not_started", ChunksCreated: 0}
		httpx.WriteEnvelope(w, 200, true, "Processing status", x, nil)
		return
	}
	if err != nil {
		httpx.WriteEnvelope(w, 503, false, "AI processing status unavailable", nil, nil)
		return
	}
	httpx.WriteEnvelope(w, 200, true, "Processing status", x, nil)
}
