package authentication

import (
	"context"
	"database/sql"
	"errors"
	"strings"
	"time"
)

var ErrUserNotFound = errors.New("user not found")

// User mirrors the fields required by the existing profile and login payloads.
type User struct {
	ID            int64     `json:"id"`
	Email         string    `json:"email"`
	Password      string    `json:"-"`
	FullName      string    `json:"-"`
	UserType      string    `json:"user_type"`
	IsActive      bool      `json:"-"`
	IsApproved    bool      `json:"is_approved"`
	University    string    `json:"university"`
	PhoneNumber   string    `json:"phone_number"`
	PhoneVerified bool      `json:"phone_verified"`
	ProfileImage  string    `json:"profile_image"`
	DateJoined    time.Time `json:"date_joined"`
}

type UserRepository struct {
	DB *sql.DB
}

func (r UserRepository) FindByEmail(ctx context.Context, email string) (User, error) {
	return r.find(ctx, `
SELECT id, email, password, full_name, user_type, is_active, is_approved,
       COALESCE(university, ''), COALESCE(phone_number, ''), phone_verified,
       COALESCE(profile_image, ''), date_joined
FROM authentication_user
WHERE lower(email) = lower($1)
LIMIT 1`, strings.TrimSpace(email))
}

func (r UserRepository) FindByID(ctx context.Context, userID int64) (User, error) {
	return r.find(ctx, `
SELECT id, email, password, full_name, user_type, is_active, is_approved,
       COALESCE(university, ''), COALESCE(phone_number, ''), phone_verified,
       COALESCE(profile_image, ''), date_joined
FROM authentication_user
WHERE id = $1
LIMIT 1`, userID)
}

func (r UserRepository) UpdatePassword(ctx context.Context, userID int64, encodedPassword string) error {
	if r.DB == nil {
		return errors.New("database is not configured")
	}
	_, err := r.DB.ExecContext(ctx, `
UPDATE authentication_user
SET password = $2
WHERE id = $1`, userID, encodedPassword)
	return err
}

func (r UserRepository) UpdateProfile(ctx context.Context, userID int64, fullName, university, phoneNumber string) (User, error) {
	_, err := r.DB.ExecContext(ctx, `
UPDATE authentication_user
SET full_name = $2, university = $3, phone_number = $4
WHERE id = $1`, userID, fullName, university, phoneNumber)
	if err != nil {
		return User{}, err
	}
	return r.FindByID(ctx, userID)
}

func (r UserRepository) find(ctx context.Context, query string, args ...any) (User, error) {
	if r.DB == nil {
		return User{}, errors.New("database is not configured")
	}

	var user User
	err := r.DB.QueryRowContext(ctx, query, args...).Scan(
		&user.ID,
		&user.Email,
		&user.Password,
		&user.FullName,
		&user.UserType,
		&user.IsActive,
		&user.IsApproved,
		&user.University,
		&user.PhoneNumber,
		&user.PhoneVerified,
		&user.ProfileImage,
		&user.DateJoined,
	)
	if errors.Is(err, sql.ErrNoRows) {
		return User{}, ErrUserNotFound
	}
	if err != nil {
		return User{}, err
	}
	return user, nil
}

func (r UserRepository) CreatePending(ctx context.Context, email, fullName, userType, encodedPassword string) (User, error) {
	if r.DB == nil {
		return User{}, errors.New("database is not configured")
	}
	var user User
	err := r.DB.QueryRowContext(ctx, `
INSERT INTO authentication_user (password, last_login, is_superuser, email, full_name, user_type, is_active, is_staff, is_approved, date_joined, university, phone_number, phone_verified)
VALUES ($1, NULL, false, $2, $3, $4, false, false, $5, NOW(), '', '', false)
RETURNING id, email, password, full_name, user_type, is_active, is_approved, university, phone_number, phone_verified, profile_image, date_joined`, encodedPassword, email, fullName, userType, userType != "lecturer").Scan(
		&user.ID, &user.Email, &user.Password, &user.FullName, &user.UserType, &user.IsActive, &user.IsApproved, &user.University, &user.PhoneNumber, &user.PhoneVerified, &user.ProfileImage, &user.DateJoined)
	return user, err
}

func (r UserRepository) SetVerifiedProfile(ctx context.Context, userID int64, userType, university, phoneNumber string, approved bool) error {
	if r.DB == nil {
		return errors.New("database is not configured")
	}
	_, err := r.DB.ExecContext(ctx, `
UPDATE authentication_user
SET user_type = $2, university = $3, phone_number = $4, is_active = true, is_approved = $5
WHERE id = $1`, userID, userType, university, phoneNumber, approved)
	return err
}

func (r UserRepository) UpdatePendingRegistration(ctx context.Context, userID int64, fullName, userType, encodedPassword string) error {
	if r.DB == nil {
		return errors.New("database is not configured")
	}
	_, err := r.DB.ExecContext(ctx, `
UPDATE authentication_user
SET full_name = $2, user_type = $3, password = $4, is_active = false, is_approved = $5
WHERE id = $1`, userID, fullName, userType, encodedPassword, userType != "lecturer")
	return err
}
