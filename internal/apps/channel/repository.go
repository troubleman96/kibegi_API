package channel

import (
	"context"
	"database/sql"
	"errors"
	"fmt"
	"time"

	"github.com/google/uuid"
)

var (
	ErrChannelNotFound = errors.New("Channel not found")
	ErrMemberNotFound  = errors.New("Channel member not found")
	ErrAlreadyMember   = errors.New("User is already a channel member")
	ErrPermission      = errors.New("You do not have permission to perform this action")
)

type User struct {
	ID          int64  `json:"id"`
	Email       string `json:"email"`
	FullName    string `json:"full_name"`
	PhoneNumber string `json:"phone_number"`
}
type Channel struct {
	ID             uuid.UUID `json:"id"`
	Name           string    `json:"name"`
	Description    string    `json:"description"`
	Visibility     string    `json:"visibility"`
	InviteToken    string    `json:"invite_token"`
	IsActive       bool      `json:"is_active"`
	CreatedBy      int64     `json:"created_by"`
	CreatedByUser  User      `json:"-"`
	MemberCount    int       `json:"member_count"`
	BroadcastCount int       `json:"broadcast_count"`
	IsMember       bool      `json:"is_member"`
	MyRole         string    `json:"my_role"`
	CreatedAt      time.Time `json:"created_at"`
	UpdatedAt      time.Time `json:"updated_at"`
}
type Member struct {
	ID          uuid.UUID  `json:"id"`
	ChannelID   uuid.UUID  `json:"channel"`
	UserID      int64      `json:"user"`
	User        User       `json:"-"`
	Role        string     `json:"role"`
	DisplayName string     `json:"display_name"`
	Email       string     `json:"email"`
	PhoneNumber string     `json:"phone_number"`
	IsActive    bool       `json:"is_active"`
	JoinedAt    time.Time  `json:"joined_at"`
	LeftAt      *time.Time `json:"left_at"`
	InvitedBy   *int64     `json:"invited_by"`
}
type Wallet struct {
	ID                 int64      `json:"id"`
	ChannelID          uuid.UUID  `json:"channel"`
	ChannelName        string     `json:"channel_name"`
	APIKey             string     `json:"api_key"`
	BalanceCredits     int        `json:"balance_credits"`
	ProviderName       string     `json:"provider_name"`
	SenderID           string     `json:"sender_id"`
	IsActive           bool       `json:"is_active"`
	MemberCount        int        `json:"member_count"`
	BroadcastCount     int        `json:"broadcast_count"`
	LastTopupReference string     `json:"last_topup_reference"`
	LastTopupAt        *time.Time `json:"last_topup_at"`
}
type Broadcast struct {
	ID             uuid.UUID  `json:"id"`
	ChannelID      uuid.UUID  `json:"channel"`
	Subject        string     `json:"subject"`
	Message        string     `json:"message"`
	Venue          string     `json:"venue"`
	Status         string     `json:"status"`
	RecipientCount int        `json:"recipient_count"`
	SentCount      int        `json:"sent_count"`
	FailedCount    int        `json:"failed_count"`
	SkippedCount   int        `json:"skipped_count"`
	CreditsUsed    int        `json:"credits_used"`
	CreatedAt      time.Time  `json:"created_at"`
	SentAt         *time.Time `json:"sent_at"`
}
type Repository struct{ DB *sql.DB }

func (r Repository) List(ctx context.Context, userID int64) ([]Channel, error) {
	rows, err := r.DB.QueryContext(ctx, `SELECT c.id,c.name,c.description,c.visibility,c.invite_token,c.is_active,c.created_by,COALESCE(u.email,''),COALESCE(u.full_name,''),COUNT(DISTINCT m.id) FILTER (WHERE m.is_active),COUNT(DISTINCT b.id),EXISTS(SELECT 1 FROM channel_channelmember me WHERE me.channel_id=c.id AND me.user_id=$1 AND me.is_active),COALESCE((SELECT me.role FROM channel_channelmember me WHERE me.channel_id=c.id AND me.user_id=$1 AND me.is_active LIMIT 1),''),c.created_at,c.updated_at FROM channel_channel c LEFT JOIN authentication_user u ON u.id=c.created_by LEFT JOIN channel_channelmember m ON m.channel_id=c.id LEFT JOIN channel_channelbroadcast b ON b.channel_id=c.id WHERE c.is_active=true AND (c.visibility='public' OR c.created_by=$1 OR EXISTS(SELECT 1 FROM channel_channelmember x WHERE x.channel_id=c.id AND x.user_id=$1 AND x.is_active)) GROUP BY c.id,u.id ORDER BY c.name`, userID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := make([]Channel, 0)
	for rows.Next() {
		var x Channel
		if err := rows.Scan(&x.ID, &x.Name, &x.Description, &x.Visibility, &x.InviteToken, &x.IsActive, &x.CreatedBy, &x.CreatedByUser.Email, &x.CreatedByUser.FullName, &x.MemberCount, &x.BroadcastCount, &x.IsMember, &x.MyRole, &x.CreatedAt, &x.UpdatedAt); err != nil {
			return nil, err
		}
		out = append(out, x)
	}
	return out, rows.Err()
}
func (r Repository) Create(ctx context.Context, userID int64, x Channel) (Channel, error) {
	id := uuid.New()
	token := uuid.NewString()
	tx, err := r.DB.BeginTx(ctx, nil)
	if err != nil {
		return Channel{}, err
	}
	defer tx.Rollback()
	if _, err = tx.ExecContext(ctx, `INSERT INTO channel_channel (id,name,description,visibility,invite_token,is_active,created_at,updated_at,created_by_id) VALUES ($1,$2,$3,$4,$5,true,NOW(),NOW(),$6)`, id, x.Name, x.Description, x.Visibility, token, userID); err != nil {
		return Channel{}, err
	}
	if _, err = tx.ExecContext(ctx, `INSERT INTO channel_channelmember (id,role,display_name,email,phone_number,is_active,joined_at,created_at,updated_at,channel_id,user_id,invited_by_id) SELECT $1,'owner',u.full_name,u.email,COALESCE(u.phone_number,''),true,NOW(),NOW(),NOW(),$2,u.id,u.id FROM authentication_user u WHERE u.id=$3`, uuid.New(), id, userID); err != nil {
		return Channel{}, err
	}
	if err := tx.Commit(); err != nil {
		return Channel{}, err
	}
	return r.Find(ctx, userID, id)
}
func (r Repository) Find(ctx context.Context, userID int64, id uuid.UUID) (Channel, error) {
	var x Channel
	err := r.DB.QueryRowContext(ctx, `SELECT c.id,c.name,c.description,c.visibility,c.invite_token,c.is_active,c.created_by,COALESCE(u.email,''),COALESCE(u.full_name,''), (SELECT COUNT(*) FROM channel_channelmember m WHERE m.channel_id=c.id AND m.is_active), (SELECT COUNT(*) FROM channel_channelbroadcast b WHERE b.channel_id=c.id), EXISTS(SELECT 1 FROM channel_channelmember me WHERE me.channel_id=c.id AND me.user_id=$1 AND me.is_active), COALESCE((SELECT me.role FROM channel_channelmember me WHERE me.channel_id=c.id AND me.user_id=$1 AND me.is_active LIMIT 1),''), c.created_at,c.updated_at FROM channel_channel c LEFT JOIN authentication_user u ON u.id=c.created_by WHERE c.id=$2 AND c.is_active=true AND (c.visibility='public' OR c.created_by=$1 OR EXISTS(SELECT 1 FROM channel_channelmember m WHERE m.channel_id=c.id AND m.user_id=$1 AND m.is_active))`, userID, id).Scan(&x.ID, &x.Name, &x.Description, &x.Visibility, &x.InviteToken, &x.IsActive, &x.CreatedBy, &x.CreatedByUser.Email, &x.CreatedByUser.FullName, &x.MemberCount, &x.BroadcastCount, &x.IsMember, &x.MyRole, &x.CreatedAt, &x.UpdatedAt)
	if errors.Is(err, sql.ErrNoRows) {
		return Channel{}, ErrChannelNotFound
	}
	return x, err
}
func (r Repository) Members(ctx context.Context, id uuid.UUID) ([]Member, error) {
	rows, err := r.DB.QueryContext(ctx, `SELECT m.id,m.channel_id,m.user_id,u.email,u.full_name,COALESCE(u.phone_number,''),m.role,m.display_name,m.email,m.phone_number,m.is_active,m.joined_at,m.left_at,m.invited_by_id FROM channel_channelmember m JOIN authentication_user u ON u.id=m.user_id WHERE m.channel_id=$1 ORDER BY m.role,m.display_name`, id)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := make([]Member, 0)
	for rows.Next() {
		var x Member
		if err := rows.Scan(&x.ID, &x.ChannelID, &x.UserID, &x.User.Email, &x.User.FullName, &x.User.PhoneNumber, &x.Role, &x.DisplayName, &x.Email, &x.PhoneNumber, &x.IsActive, &x.JoinedAt, &x.LeftAt, &x.InvitedBy); err != nil {
			return nil, err
		}
		out = append(out, x)
	}
	return out, rows.Err()
}
func (r Repository) FindUser(ctx context.Context, identifier string) (User, error) {
	var u User
	err := r.DB.QueryRowContext(ctx, `SELECT id,email,full_name,COALESCE(phone_number,'') FROM authentication_user WHERE (email ILIKE $1 OR id::text=$1) AND is_active=true`, identifier).Scan(&u.ID, &u.Email, &u.FullName, &u.PhoneNumber)
	return u, err
}
func (r Repository) UpsertMember(ctx context.Context, channelID uuid.UUID, userID, invitedBy int64, role string) (Member, error) {
	user, err := r.FindUser(ctx, fmt.Sprint(userID))
	if err != nil {
		return Member{}, ErrMemberNotFound
	}
	var x Member
	err = r.DB.QueryRowContext(ctx, `INSERT INTO channel_channelmember (id,role,display_name,email,phone_number,is_active,joined_at,created_at,updated_at,channel_id,user_id,invited_by_id) VALUES ($1,$2,$3,$4,$5,true,NOW(),NOW(),NOW(),$6,$7,$8) ON CONFLICT (channel_id,user_id) DO UPDATE SET is_active=true,left_at=NULL,role=EXCLUDED.role,updated_at=NOW() RETURNING id,channel_id,user_id,role,display_name,email,phone_number,is_active,joined_at,left_at,invited_by_id`, uuid.New(), role, user.FullName, user.Email, user.PhoneNumber, channelID, userID, invitedBy).Scan(&x.ID, &x.ChannelID, &x.UserID, &x.Role, &x.DisplayName, &x.Email, &x.PhoneNumber, &x.IsActive, &x.JoinedAt, &x.LeftAt, &x.InvitedBy)
	return x, err
}
func (r Repository) Join(ctx context.Context, channelID uuid.UUID, userID int64) (Member, error) {
	return r.UpsertMember(ctx, channelID, userID, userID, "member")
}
func (r Repository) RemoveMember(ctx context.Context, memberID uuid.UUID, userID int64) error {
	result, err := r.DB.ExecContext(ctx, `DELETE FROM channel_channelmember m USING channel_channel c WHERE m.id=$1 AND (c.created_by_id=$2 OR EXISTS(SELECT 1 FROM channel_channelmember a WHERE a.channel_id=c.id AND a.user_id=$2 AND a.role IN ('owner','admin')))`, memberID, userID)
	if err != nil {
		return err
	}
	n, _ := result.RowsAffected()
	if n == 0 {
		return ErrPermission
	}
	return nil
}
func (r Repository) Wallet(ctx context.Context, id uuid.UUID) (Wallet, error) {
	var x Wallet
	err := r.DB.QueryRowContext(ctx, `INSERT INTO channel_channelwallet (api_key,balance_credits,provider_name,sender_id,is_active,last_topup_reference,last_topup_at,created_at,updated_at,channel_id) VALUES ('',0,'sendafrica','',true,'',NULL,NOW(),NOW(),$1) ON CONFLICT(channel_id) DO UPDATE SET channel_id=EXCLUDED.channel_id RETURNING id,channel_id,api_key,balance_credits,provider_name,sender_id,is_active,last_topup_reference,last_topup_at`, id).Scan(&x.ID, &x.ChannelID, &x.APIKey, &x.BalanceCredits, &x.ProviderName, &x.SenderID, &x.IsActive, &x.LastTopupReference, &x.LastTopupAt)
	return x, err
}
func (r Repository) CreateBroadcast(ctx context.Context, channelID uuid.UUID, senderID int64, subject, message, venue string) (Broadcast, error) {
	var x Broadcast
	err := r.DB.QueryRowContext(ctx, `INSERT INTO channel_channelbroadcast (id,subject,message,venue,status,recipient_count,sent_count,failed_count,skipped_count,credits_used,created_at,updated_at,channel_id,sender_id) VALUES ($1,$2,$3,$4,'draft',0,0,0,0,0,NOW(),NOW(),$5,$6) RETURNING id,channel_id,subject,message,venue,status,recipient_count,sent_count,failed_count,skipped_count,credits_used,created_at,sent_at`, uuid.New(), subject, message, venue, channelID, senderID).Scan(&x.ID, &x.ChannelID, &x.Subject, &x.Message, &x.Venue, &x.Status, &x.RecipientCount, &x.SentCount, &x.FailedCount, &x.SkippedCount, &x.CreditsUsed, &x.CreatedAt, &x.SentAt)
	return x, err
}
