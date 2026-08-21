package sms

import (
	"context"
	"database/sql"
	"errors"
	"time"

	"github.com/google/uuid"
)

type Account struct {
	ID                 uuid.UUID  `json:"id"`
	OwnerType          string     `json:"owner_type"`
	OwnerID            string     `json:"owner_id"`
	PhoneNumber        string     `json:"phone_number"`
	BalanceCredits     int        `json:"balance_credits"`
	ProviderName       string     `json:"provider_name"`
	SenderID           string     `json:"sender_id"`
	IsActive           bool       `json:"is_active"`
	LastTopupReference string     `json:"last_topup_reference"`
	LastTopupAt        *time.Time `json:"last_topup_at"`
	CreatedAt          time.Time  `json:"created_at"`
	UpdatedAt          time.Time  `json:"updated_at"`
}
type Delivery struct {
	ID                uuid.UUID  `json:"id"`
	RecipientPhone    string     `json:"recipient_phone"`
	ProviderName      string     `json:"provider_name"`
	ProviderMessageID string     `json:"provider_message_id"`
	Status            string     `json:"status"`
	Message           string     `json:"message"`
	CreditsUsed       int        `json:"credits_used"`
	ErrorMessage      string     `json:"error_message"`
	SentAt            *time.Time `json:"sent_at"`
	CreatedAt         time.Time  `json:"created_at"`
}
type Repository struct{ DB *sql.DB }

func (r Repository) Account(ctx context.Context, ownerType, ownerID string) (Account, error) {
	var x Account
	err := r.DB.QueryRowContext(ctx, `SELECT a.id,ct.model,a.owner_object_id,a.phone_number,a.balance_credits,a.provider_name,a.sender_id,a.is_active,a.last_topup_reference,a.last_topup_at,a.created_at,a.updated_at FROM sms_smsaccount a JOIN django_content_type ct ON ct.id=a.owner_content_type_id WHERE ct.model=$1 AND a.owner_object_id=$2`, ownerType, ownerID).Scan(&x.ID, &x.OwnerType, &x.OwnerID, &x.PhoneNumber, &x.BalanceCredits, &x.ProviderName, &x.SenderID, &x.IsActive, &x.LastTopupReference, &x.LastTopupAt, &x.CreatedAt, &x.UpdatedAt)
	return x, err
}
func (r Repository) Topup(ctx context.Context, ownerType, ownerID string, amount int) (Account, error) {
	if amount <= 0 {
		return Account{}, errors.New("Top-up amount must be positive")
	}
	_, err := r.DB.ExecContext(ctx, `UPDATE sms_smsaccount a SET balance_credits=balance_credits+$3,last_topup_at=NOW(),updated_at=NOW() FROM django_content_type ct WHERE a.owner_content_type_id=ct.id AND ct.model=$1 AND a.owner_object_id=$2`, ownerType, ownerID, amount)
	if err != nil {
		return Account{}, err
	}
	return r.Account(ctx, ownerType, ownerID)
}
func (r Repository) Deliveries(ctx context.Context, limit int) ([]Delivery, error) {
	rows, err := r.DB.QueryContext(ctx, `SELECT id,recipient_phone,provider_name,provider_message_id,status,message,credits_used,error_message,sent_at,created_at FROM sms_smsdelivery ORDER BY created_at DESC LIMIT $1`, limit)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := make([]Delivery, 0)
	for rows.Next() {
		var x Delivery
		if err := rows.Scan(&x.ID, &x.RecipientPhone, &x.ProviderName, &x.ProviderMessageID, &x.Status, &x.Message, &x.CreditsUsed, &x.ErrorMessage, &x.SentAt, &x.CreatedAt); err != nil {
			return nil, err
		}
		out = append(out, x)
	}
	return out, rows.Err()
}
