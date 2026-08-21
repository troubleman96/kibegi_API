package authentication

import (
	"context"
	"database/sql"
	"errors"
	"time"
)

type OTPRecord struct {
	ID        int64
	Email     string
	Code      string
	Purpose   string
	CreatedAt time.Time
	ExpiresAt time.Time
	IsUsed    bool
}

type OTPRepository struct {
	DB *sql.DB
}

func (r OTPRepository) Invalidate(ctx context.Context, email, purpose string) error {
	if r.DB == nil {
		return errors.New("database is not configured")
	}
	_, err := r.DB.ExecContext(ctx, `UPDATE authentication_passwordresetotp SET is_used = true WHERE email = $1 AND purpose = $2 AND is_used = false`, email, purpose)
	return err
}

func (r OTPRepository) CountRecent(ctx context.Context, email, purpose string, since time.Time) (int, error) {
	if r.DB == nil {
		return 0, errors.New("database is not configured")
	}
	var count int
	err := r.DB.QueryRowContext(ctx, `SELECT COUNT(*) FROM authentication_passwordresetotp WHERE email = $1 AND purpose = $2 AND created_at >= $3`, email, purpose, since).Scan(&count)
	return count, err
}

func (r OTPRepository) Create(ctx context.Context, email, code, purpose string, expiresAt time.Time) (OTPRecord, error) {
	if r.DB == nil {
		return OTPRecord{}, errors.New("database is not configured")
	}
	var record OTPRecord
	err := r.DB.QueryRowContext(ctx, `
INSERT INTO authentication_passwordresetotp (email, code, purpose, reset_token, created_at, expires_at, is_used)
VALUES ($1, $2, $3, NULL, NOW(), $4, false)
RETURNING id, email, code, purpose, created_at, expires_at, is_used`, email, code, purpose, expiresAt).Scan(
		&record.ID, &record.Email, &record.Code, &record.Purpose, &record.CreatedAt, &record.ExpiresAt, &record.IsUsed)
	return record, err
}

func (r OTPRepository) LatestPending(ctx context.Context, email, code, purpose string) (OTPRecord, error) {
	if r.DB == nil {
		return OTPRecord{}, errors.New("database is not configured")
	}
	var record OTPRecord
	err := r.DB.QueryRowContext(ctx, `
SELECT id, email, code, purpose, created_at, expires_at, is_used
FROM authentication_passwordresetotp
WHERE email = $1 AND code = $2 AND purpose = $3 AND is_used = false
ORDER BY created_at DESC LIMIT 1`, email, code, purpose).Scan(
		&record.ID, &record.Email, &record.Code, &record.Purpose, &record.CreatedAt, &record.ExpiresAt, &record.IsUsed)
	return record, err
}

func (r OTPRepository) MarkUsed(ctx context.Context, id int64) error {
	if r.DB == nil {
		return errors.New("database is not configured")
	}
	_, err := r.DB.ExecContext(ctx, `UPDATE authentication_passwordresetotp SET is_used = true WHERE id = $1`, id)
	return err
}
