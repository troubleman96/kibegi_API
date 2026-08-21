package ai

import (
	"context"
	"database/sql"
	"errors"
	"strings"
	"time"

	"github.com/google/uuid"
)

var ErrConversationNotFound = errors.New("Conversation not found")

type Profile struct {
	HasKey    bool   `json:"has_key"`
	MaskedKey string `json:"masked_key"`
	ChatModel string `json:"chat_model"`
}
type Usage struct {
	TokensToday    int     `json:"tokens_today"`
	TokensTotal    int64   `json:"tokens_total"`
	DailyLimit     int     `json:"daily_limit"`
	RemainingToday int     `json:"remaining_today"`
	PercentageUsed float64 `json:"percentage_used"`
}
type Conversation struct {
	ID           uuid.UUID  `json:"id"`
	ClassID      *uuid.UUID `json:"class_id"`
	ClassName    string     `json:"class_name"`
	Title        string     `json:"title"`
	UpdatedAt    time.Time  `json:"updated_at"`
	MessageCount int        `json:"message_count"`
}
type Message struct {
	ID         uuid.UUID `json:"id"`
	Role       string    `json:"role"`
	Content    string    `json:"content"`
	Sources    any       `json:"sources"`
	TokensUsed int       `json:"tokens_used"`
	CreatedAt  time.Time `json:"created_at"`
}
type ProcessingStatus struct {
	UploadID      uuid.UUID  `json:"upload_id"`
	FileName      string     `json:"file_name"`
	Status        string     `json:"status"`
	ChunksCreated int        `json:"chunks_created"`
	ErrorMessage  *string    `json:"error_message"`
	UpdatedAt     *time.Time `json:"updated_at"`
}
type Repository struct{ DB *sql.DB }

func (r Repository) Profile(ctx context.Context, userID int64, defaultModel string) (Profile, error) {
	var key, model string
	err := r.DB.QueryRowContext(ctx, `INSERT INTO ai_useraiprofile (api_key,chat_model,created_at,updated_at,user_id) VALUES ('',$2,NOW(),NOW(),$1) ON CONFLICT(user_id) DO UPDATE SET user_id=EXCLUDED.user_id RETURNING api_key,chat_model`, userID, defaultModel).Scan(&key, &model)
	if err != nil {
		return Profile{}, err
	}
	masked := ""
	if len(key) > 8 {
		masked = key[:4] + "••••" + key[len(key)-4:]
	} else if key != "" {
		masked = strings.Repeat("*", len(key))
	}
	return Profile{HasKey: key != "", MaskedKey: masked, ChatModel: model}, nil
}
func (r Repository) SaveProfile(ctx context.Context, userID int64, key, model string) (Profile, error) {
	_, err := r.DB.ExecContext(ctx, `INSERT INTO ai_useraiprofile (api_key,chat_model,created_at,updated_at,user_id) VALUES ($2,$3,NOW(),NOW(),$1) ON CONFLICT(user_id) DO UPDATE SET api_key=EXCLUDED.api_key,chat_model=EXCLUDED.chat_model,updated_at=NOW()`, userID, key, model)
	if err != nil {
		return Profile{}, err
	}
	return r.Profile(ctx, userID, model)
}
func (r Repository) ClearProfile(ctx context.Context, userID int64) error {
	_, err := r.DB.ExecContext(ctx, `DELETE FROM ai_useraiprofile WHERE user_id=$1`, userID)
	return err
}
func (r Repository) GetUsage(ctx context.Context, userID int64) (Usage, error) {
	var x Usage
	var last time.Time
	err := r.DB.QueryRowContext(ctx, `INSERT INTO ai_aiusage (tokens_used_today,tokens_used_total,daily_limit,last_reset,created_at,updated_at,user_id) VALUES (0,0,50000,CURRENT_DATE,NOW(),NOW(),$1) ON CONFLICT(user_id) DO UPDATE SET tokens_used_today=CASE WHEN last_reset<CURRENT_DATE THEN 0 ELSE ai_aiusage.tokens_used_today END,last_reset=CURRENT_DATE,updated_at=NOW() RETURNING tokens_used_today,tokens_used_total,daily_limit,last_reset`, userID).Scan(&x.TokensToday, &x.TokensTotal, &x.DailyLimit, &last)
	if err != nil {
		return x, err
	}
	x.RemainingToday = x.DailyLimit - x.TokensToday
	if x.RemainingToday < 0 {
		x.RemainingToday = 0
	}
	if x.DailyLimit > 0 {
		x.PercentageUsed = float64(x.TokensToday) / float64(x.DailyLimit) * 100
	}
	return x, nil
}
func (r Repository) Conversations(ctx context.Context, userID int64, classID string) ([]Conversation, error) {
	args := []any{userID}
	where := "c.user_id=$1"
	if classID != "" {
		where += " AND c.class_obj_id=$2"
		args = append(args, classID)
	}
	rows, err := r.DB.QueryContext(ctx, `SELECT c.id,c.class_obj_id,COALESCE(cl.name,'General'),c.title,c.updated_at,COUNT(m.id) FROM ai_aiconversation c LEFT JOIN classes_class cl ON cl.id=c.class_obj_id LEFT JOIN ai_aimessage m ON m.conversation_id=c.id WHERE `+where+` GROUP BY c.id,cl.name ORDER BY c.updated_at DESC LIMIT 20`, args...)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := make([]Conversation, 0)
	for rows.Next() {
		var x Conversation
		var classID sql.NullString
		if err := rows.Scan(&x.ID, &classID, &x.ClassName, &x.Title, &x.UpdatedAt, &x.MessageCount); err != nil {
			return nil, err
		}
		if classID.Valid {
			parsed, _ := uuid.Parse(classID.String)
			x.ClassID = &parsed
		}
		out = append(out, x)
	}
	return out, rows.Err()
}
func (r Repository) Conversation(ctx context.Context, userID int64, id uuid.UUID) (Conversation, []Message, error) {
	var c Conversation
	err := r.DB.QueryRowContext(ctx, `SELECT c.id,c.class_obj_id,COALESCE(cl.name,'General'),c.title,c.updated_at FROM ai_aiconversation c LEFT JOIN classes_class cl ON cl.id=c.class_obj_id WHERE c.id=$1 AND c.user_id=$2`, id, userID).Scan(&c.ID, &c.ClassID, &c.ClassName, &c.Title, &c.UpdatedAt)
	if errors.Is(err, sql.ErrNoRows) {
		return c, nil, ErrConversationNotFound
	}
	if err != nil {
		return c, nil, err
	}
	rows, err := r.DB.QueryContext(ctx, `SELECT id,role,content,sources,tokens_used,created_at FROM ai_aimessage WHERE conversation_id=$1 ORDER BY created_at`, id)
	if err != nil {
		return c, nil, err
	}
	defer rows.Close()
	messages := make([]Message, 0)
	for rows.Next() {
		var m Message
		if err := rows.Scan(&m.ID, &m.Role, &m.Content, &m.Sources, &m.TokensUsed, &m.CreatedAt); err != nil {
			return c, nil, err
		}
		messages = append(messages, m)
	}
	return c, messages, rows.Err()
}
func (r Repository) DeleteConversation(ctx context.Context, userID int64, id uuid.UUID) error {
	res, err := r.DB.ExecContext(ctx, `DELETE FROM ai_aiconversation WHERE id=$1 AND user_id=$2`, id, userID)
	if err != nil {
		return err
	}
	n, _ := res.RowsAffected()
	if n == 0 {
		return ErrConversationNotFound
	}
	return nil
}
