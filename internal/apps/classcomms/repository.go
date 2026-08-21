package classcomms

import (
	"context"
	"database/sql"
	"errors"
	"strings"
	"time"

	"github.com/google/uuid"
)

var ErrNotFound = errors.New("Class communications resource not found")

type Profile struct {
	ID                        int64     `json:"id"`
	ClassID                   uuid.UUID `json:"class_obj"`
	ClassName                 string    `json:"class_name"`
	ClassCode                 string    `json:"class_code"`
	PublicToken               string    `json:"public_token"`
	PublicRegistrationEnabled bool      `json:"public_registration_enabled"`
	DefaultSenderName         string    `json:"default_sender_name"`
	RegistrationHint          string    `json:"registration_hint"`
	ContactCount              int       `json:"contact_count"`
	BroadcastCount            int       `json:"broadcast_count"`
	CreatedAt                 time.Time `json:"created_at"`
	UpdatedAt                 time.Time `json:"updated_at"`
}
type Wallet struct {
	ID                 int64      `json:"id"`
	ClassID            uuid.UUID  `json:"class_obj"`
	ClassName          string     `json:"class_name"`
	BalanceCredits     int        `json:"balance_credits"`
	ProviderName       string     `json:"provider_name"`
	SenderID           string     `json:"sender_id"`
	IsActive           bool       `json:"is_active"`
	LastTopupReference string     `json:"last_topup_reference"`
	LastTopupAt        *time.Time `json:"last_topup_at"`
}
type Contact struct {
	ID             uuid.UUID `json:"id"`
	ClassID        uuid.UUID `json:"class_obj"`
	FullName       string    `json:"full_name"`
	PhoneNumber    string    `json:"phone_number"`
	ConsentGranted bool      `json:"consent_granted"`
	ConsentSource  string    `json:"consent_source"`
	Notes          string    `json:"notes"`
	IsActive       bool      `json:"is_active"`
	MemberID       *int64    `json:"member"`
	CreatedAt      time.Time `json:"created_at"`
	UpdatedAt      time.Time `json:"updated_at"`
}
type Broadcast struct {
	ID             uuid.UUID  `json:"id"`
	ClassID        uuid.UUID  `json:"class_obj"`
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

func (r Repository) Profile(ctx context.Context, classID uuid.UUID) (Profile, error) {
	var x Profile
	err := r.DB.QueryRowContext(ctx, `INSERT INTO classcomms_classcommsprofile (public_token,public_registration_enabled,default_sender_name,registration_hint,created_at,updated_at,class_obj_id) VALUES (md5(random()::text||clock_timestamp()::text),true,'','Register your name and phone number to receive class updates.',NOW(),NOW(),$1) ON CONFLICT(class_obj_id) DO UPDATE SET class_obj_id=EXCLUDED.class_obj_id RETURNING id,class_obj_id,public_token,public_registration_enabled,default_sender_name,registration_hint,created_at,updated_at`, classID).Scan(&x.ID, &x.ClassID, &x.PublicToken, &x.PublicRegistrationEnabled, &x.DefaultSenderName, &x.RegistrationHint, &x.CreatedAt, &x.UpdatedAt)
	if err != nil {
		return x, err
	}
	_ = r.DB.QueryRowContext(ctx, `SELECT name,class_code FROM classes_class WHERE id=$1`, classID).Scan(&x.ClassName, &x.ClassCode)
	_ = r.DB.QueryRowContext(ctx, `SELECT COUNT(*) FROM classcomms_classcontact WHERE class_obj_id=$1 AND is_active`, classID).Scan(&x.ContactCount)
	_ = r.DB.QueryRowContext(ctx, `SELECT COUNT(*) FROM classcomms_classbroadcast WHERE class_obj_id=$1`, classID).Scan(&x.BroadcastCount)
	return x, nil
}
func (r Repository) Wallet(ctx context.Context, classID uuid.UUID) (Wallet, error) {
	var x Wallet
	err := r.DB.QueryRowContext(ctx, `INSERT INTO classcomms_classcommswallet (balance_credits,provider_name,sender_id,is_active,last_topup_reference,last_topup_at,created_at,updated_at,class_obj_id) VALUES (0,'sendafrica','',true,'',NULL,NOW(),NOW(),$1) ON CONFLICT(class_obj_id) DO UPDATE SET class_obj_id=EXCLUDED.class_obj_id RETURNING id,class_obj_id,balance_credits,provider_name,sender_id,is_active,last_topup_reference,last_topup_at`, classID).Scan(&x.ID, &x.ClassID, &x.BalanceCredits, &x.ProviderName, &x.SenderID, &x.IsActive, &x.LastTopupReference, &x.LastTopupAt)
	if err != nil {
		return x, err
	}
	_ = r.DB.QueryRowContext(ctx, `SELECT name FROM classes_class WHERE id=$1`, classID).Scan(&x.ClassName)
	return x, nil
}
func (r Repository) Contacts(ctx context.Context, classID uuid.UUID) ([]Contact, error) {
	rows, err := r.DB.QueryContext(ctx, `SELECT id,class_obj_id,full_name,phone_number,consent_granted,consent_source,notes,is_active,member_id,created_at,updated_at FROM classcomms_classcontact WHERE class_obj_id=$1 AND is_active ORDER BY full_name`, classID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := make([]Contact, 0)
	for rows.Next() {
		var x Contact
		if err := rows.Scan(&x.ID, &x.ClassID, &x.FullName, &x.PhoneNumber, &x.ConsentGranted, &x.ConsentSource, &x.Notes, &x.IsActive, &x.MemberID, &x.CreatedAt, &x.UpdatedAt); err != nil {
			return nil, err
		}
		out = append(out, x)
	}
	return out, rows.Err()
}
func (r Repository) UpsertContact(ctx context.Context, classID uuid.UUID, createdBy int64, x Contact) (Contact, error) {
	var out Contact
	err := r.DB.QueryRowContext(ctx, `INSERT INTO classcomms_classcontact (id,full_name,phone_number,consent_granted,consent_source,notes,is_active,verified_at,created_at,updated_at,class_obj_id,created_by_id) VALUES ($1,$2,$3,$4,'manual',$5,true,NOW(),NOW(),NOW(),$6,$7) ON CONFLICT(class_obj_id,phone_number) DO UPDATE SET full_name=EXCLUDED.full_name,consent_granted=EXCLUDED.consent_granted,notes=EXCLUDED.notes,is_active=true,updated_at=NOW() RETURNING id,class_obj_id,full_name,phone_number,consent_granted,consent_source,notes,is_active,member_id,created_at,updated_at`, uuid.New(), strings.TrimSpace(x.FullName), strings.TrimSpace(x.PhoneNumber), x.ConsentGranted, x.Notes, classID, createdBy).Scan(&out.ID, &out.ClassID, &out.FullName, &out.PhoneNumber, &out.ConsentGranted, &out.ConsentSource, &out.Notes, &out.IsActive, &out.MemberID, &out.CreatedAt, &out.UpdatedAt)
	return out, err
}
func (r Repository) DeleteContact(ctx context.Context, id uuid.UUID) error {
	res, err := r.DB.ExecContext(ctx, `UPDATE classcomms_classcontact SET is_active=false,updated_at=NOW() WHERE id=$1`, id)
	if err != nil {
		return err
	}
	n, _ := res.RowsAffected()
	if n == 0 {
		return ErrNotFound
	}
	return nil
}
func (r Repository) CreateBroadcast(ctx context.Context, classID uuid.UUID, senderID int64, subject, message, venue string) (Broadcast, error) {
	var x Broadcast
	err := r.DB.QueryRowContext(ctx, `INSERT INTO classcomms_classbroadcast (id,subject,message,venue,status,recipient_count,sent_count,failed_count,skipped_count,credits_used,created_at,updated_at,class_obj_id,sender_id) VALUES ($1,$2,$3,$4,'draft',0,0,0,0,0,NOW(),NOW(),$5,$6) RETURNING id,class_obj_id,subject,message,venue,status,recipient_count,sent_count,failed_count,skipped_count,credits_used,created_at,sent_at`, uuid.New(), subject, message, venue, classID, senderID).Scan(&x.ID, &x.ClassID, &x.Subject, &x.Message, &x.Venue, &x.Status, &x.RecipientCount, &x.SentCount, &x.FailedCount, &x.SkippedCount, &x.CreditsUsed, &x.CreatedAt, &x.SentAt)
	return x, err
}

func (r Repository) FindBroadcast(ctx context.Context, id uuid.UUID) (Broadcast, error) {
	var x Broadcast
	err := r.DB.QueryRowContext(ctx, `SELECT id,class_obj_id,subject,message,venue,status,recipient_count,sent_count,failed_count,skipped_count,credits_used,created_at,sent_at FROM classcomms_classbroadcast WHERE id=$1`, id).Scan(&x.ID, &x.ClassID, &x.Subject, &x.Message, &x.Venue, &x.Status, &x.RecipientCount, &x.SentCount, &x.FailedCount, &x.SkippedCount, &x.CreditsUsed, &x.CreatedAt, &x.SentAt)
	return x, err
}
func (r Repository) SetRepresentative(ctx context.Context, classID uuid.UUID, userID int64, role string) (map[string]any, error) {
	var membershipID int64
	if err := r.DB.QueryRowContext(ctx, `UPDATE classes_membership SET role=$3 WHERE class_obj_id=$1 AND user_id=$2 RETURNING id`, classID, userID, role).Scan(&membershipID); err != nil {
		return nil, err
	}
	return map[string]any{"membership_id": membershipID, "user_id": userID, "role": role}, nil
}
