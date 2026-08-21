package classes

import (
	"context"
	"crypto/rand"
	"database/sql"
	"errors"
	"fmt"
	"strings"
	"time"

	"github.com/google/uuid"
)

var (
	ErrClassNotFound      = errors.New("class not found")
	ErrAlreadyMember      = errors.New("already a member")
	ErrNotMember          = errors.New("not a member")
	ErrCreatorCannotLeave = errors.New("class creator cannot leave")
)

type Class struct {
	ID              uuid.UUID `json:"id"`
	Name            string    `json:"name"`
	Description     string    `json:"description"`
	ClassCode       string    `json:"class_code"`
	IsPublic        bool      `json:"is_public"`
	IsVerified      bool      `json:"is_verified"`
	CreatorID       int64     `json:"creator"`
	CreatorName     string    `json:"creator_name"`
	CreatorType     string    `json:"creator_type"`
	MemberCount     int       `json:"member_count"`
	FileCount       int       `json:"file_count"`
	CreatedAt       time.Time `json:"created_at"`
	UpdatedAt       time.Time `json:"updated_at"`
	IsMember        bool      `json:"is_member"`
	UserRole        *string   `json:"user_role"`
	CreatorImage    any       `json:"creator_profile_image"`
	CreatorImageURL any       `json:"creator_profile_image_url"`
}

type Member struct {
	ID              int64     `json:"id"`
	FullName        string    `json:"full_name"`
	Email           string    `json:"email"`
	UserType        string    `json:"user_type"`
	ProfileImage    any       `json:"profile_image"`
	ProfileImageURL any       `json:"profile_image_url"`
	Role            string    `json:"role"`
	JoinedAt        time.Time `json:"joined_at"`
}

type Repository struct {
	DB *sql.DB
}

func (r Repository) ListForUser(ctx context.Context, userID int64, query string, limit, offset int) ([]Class, int, error) {
	if r.DB == nil {
		return nil, 0, errors.New("database is not configured")
	}
	query = strings.TrimSpace(query)
	filter := "m.user_id = $1"
	args := []any{userID}
	if query != "" {
		filter += " AND (c.name ILIKE $2 OR c.class_code ILIKE $2)"
		args = append(args, "%"+query+"%")
	}

	var total int
	countQuery := `SELECT COUNT(DISTINCT c.id) FROM classes_class c JOIN classes_membership m ON m.class_obj_id = c.id WHERE ` + filter
	if err := r.DB.QueryRowContext(ctx, countQuery, args...).Scan(&total); err != nil {
		return nil, 0, err
	}

	args = append(args, limit, offset)
	rows, err := r.DB.QueryContext(ctx, `
SELECT c.id, c.name, c.description, c.class_code, c.is_public, c.is_verified,
       c.creator_id, creator.full_name, creator.user_type,
       COUNT(DISTINCT members.id), COUNT(DISTINCT uploads.id), c.created_at, c.updated_at,
       true, creator.profile_image
FROM classes_class c
JOIN classes_membership m ON m.class_obj_id = c.id AND m.user_id = $1
JOIN authentication_user creator ON creator.id = c.creator_id
LEFT JOIN classes_membership all_members ON all_members.class_obj_id = c.id
LEFT JOIN authentication_user members ON members.id = all_members.user_id
LEFT JOIN uploads_upload uploads ON uploads.class_obj_id = c.id AND uploads.is_deleted = false
WHERE `+filter+`
GROUP BY c.id, creator.id
ORDER BY c.created_at DESC
LIMIT $`+fmt.Sprint(len(args)-1)+` OFFSET $`+fmt.Sprint(len(args)), args...)
	if err != nil {
		return nil, 0, err
	}
	defer rows.Close()
	classes := make([]Class, 0)
	for rows.Next() {
		var item Class
		if err := rows.Scan(&item.ID, &item.Name, &item.Description, &item.ClassCode, &item.IsPublic, &item.IsVerified, &item.CreatorID, &item.CreatorName, &item.CreatorType, &item.MemberCount, &item.FileCount, &item.CreatedAt, &item.UpdatedAt, &item.IsMember, &item.CreatorImage); err != nil {
			return nil, 0, err
		}
		classes = append(classes, item)
	}
	return classes, total, rows.Err()
}

func (r Repository) FindForUser(ctx context.Context, classID uuid.UUID, userID int64) (Class, error) {
	if r.DB == nil {
		return Class{}, errors.New("database is not configured")
	}
	var item Class
	var role sql.NullString
	var creatorImage sql.NullString
	err := r.DB.QueryRowContext(ctx, `
SELECT c.id, c.name, c.description, c.class_code, c.is_public, c.is_verified,
       c.creator_id, creator.full_name, creator.user_type,
       (SELECT COUNT(*) FROM classes_membership WHERE class_obj_id = c.id),
       (SELECT COUNT(*) FROM uploads_upload WHERE class_obj_id = c.id AND is_deleted = false),
       c.created_at, c.updated_at,
       EXISTS(SELECT 1 FROM classes_membership WHERE class_obj_id = c.id AND user_id = $2),
       (SELECT role FROM classes_membership WHERE class_obj_id = c.id AND user_id = $2 LIMIT 1),
       creator.profile_image
FROM classes_class c
JOIN authentication_user creator ON creator.id = c.creator_id
WHERE c.id = $1
  AND (c.is_public = true OR EXISTS(SELECT 1 FROM classes_membership WHERE class_obj_id = c.id AND user_id = $2))`, classID, userID).Scan(
		&item.ID, &item.Name, &item.Description, &item.ClassCode, &item.IsPublic, &item.IsVerified, &item.CreatorID, &item.CreatorName, &item.CreatorType, &item.MemberCount, &item.FileCount, &item.CreatedAt, &item.UpdatedAt, &item.IsMember, &role, &creatorImage)
	if errors.Is(err, sql.ErrNoRows) {
		return Class{}, ErrClassNotFound
	}
	if err != nil {
		return Class{}, err
	}
	if role.Valid {
		item.UserRole = &role.String
	}
	if creatorImage.Valid && creatorImage.String != "" {
		item.CreatorImage = creatorImage.String
	}
	return item, nil
}

func (r Repository) Create(ctx context.Context, userID int64, userType, name, description string, isPublic bool) (Class, error) {
	if r.DB == nil {
		return Class{}, errors.New("database is not configured")
	}
	name = strings.TrimSpace(name)
	if name == "" {
		return Class{}, errors.New("class name is required")
	}
	isVerified := userType == "lecturer"
	role := "student"
	if isVerified {
		role = "lecturer"
	}
	for attempt := 0; attempt < 10; attempt++ {
		classID := uuid.New()
		classCode := generateClassCode()
		tx, err := r.DB.BeginTx(ctx, nil)
		if err != nil {
			return Class{}, err
		}
		var creatorName string
		err = tx.QueryRowContext(ctx, `SELECT full_name FROM authentication_user WHERE id = $1`, userID).Scan(&creatorName)
		if err == nil {
			_, err = tx.ExecContext(ctx, `
INSERT INTO classes_class (id, name, description, class_code, is_public, is_verified, creator_id, created_at, updated_at)
VALUES ($1, $2, $3, $4, $5, $6, $7, NOW(), NOW())`, classID, name, description, classCode, isPublic, isVerified, userID)
		}
		if err == nil {
			_, err = tx.ExecContext(ctx, `
INSERT INTO classes_membership (role, joined_at, class_obj_id, user_id)
VALUES ($1, NOW(), $2, $3)`, role, classID, userID)
		}
		if err == nil {
			err = tx.Commit()
		} else {
			_ = tx.Rollback()
		}
		if err == nil {
			return Class{ID: classID, Name: name, Description: description, ClassCode: classCode, IsPublic: isPublic, IsVerified: isVerified, CreatorID: userID, CreatorName: creatorName, CreatorType: userType, MemberCount: 1, CreatedAt: time.Now().UTC(), UpdatedAt: time.Now().UTC(), IsMember: true, UserRole: &role}, nil
		}
		if !strings.Contains(strings.ToLower(err.Error()), "duplicate") {
			return Class{}, err
		}
	}
	return Class{}, errors.New("could not generate a unique class code")
}

func (r Repository) Join(ctx context.Context, classID uuid.UUID, userID int64) (Class, error) {
	if r.DB == nil {
		return Class{}, errors.New("database is not configured")
	}
	var creatorID int64
	var isPublic bool
	if err := r.DB.QueryRowContext(ctx, `SELECT creator_id, is_public FROM classes_class WHERE id = $1`, classID).Scan(&creatorID, &isPublic); errors.Is(err, sql.ErrNoRows) {
		return Class{}, ErrClassNotFound
	} else if err != nil {
		return Class{}, err
	}
	var exists bool
	if err := r.DB.QueryRowContext(ctx, `SELECT EXISTS(SELECT 1 FROM classes_membership WHERE class_obj_id = $1 AND user_id = $2)`, classID, userID).Scan(&exists); err != nil {
		return Class{}, err
	}
	if exists {
		return Class{}, ErrAlreadyMember
	}
	if _, err := r.DB.ExecContext(ctx, `INSERT INTO classes_membership (role, joined_at, class_obj_id, user_id) VALUES ('student', NOW(), $1, $2)`, classID, userID); err != nil {
		return Class{}, err
	}
	return r.FindForUser(ctx, classID, userID)
}

func (r Repository) Leave(ctx context.Context, classID uuid.UUID, userID int64) error {
	if r.DB == nil {
		return errors.New("database is not configured")
	}
	var creatorID int64
	if err := r.DB.QueryRowContext(ctx, `SELECT creator_id FROM classes_class WHERE id = $1`, classID).Scan(&creatorID); errors.Is(err, sql.ErrNoRows) {
		return ErrClassNotFound
	} else if err != nil {
		return err
	}
	if creatorID == userID {
		return ErrCreatorCannotLeave
	}
	result, err := r.DB.ExecContext(ctx, `DELETE FROM classes_membership WHERE class_obj_id = $1 AND user_id = $2`, classID, userID)
	if err != nil {
		return err
	}
	count, err := result.RowsAffected()
	if err != nil {
		return err
	}
	if count == 0 {
		return ErrNotMember
	}
	return nil
}

func (r Repository) Members(ctx context.Context, classID uuid.UUID, userID int64, limit, offset int) ([]Member, int, error) {
	if r.DB == nil {
		return nil, 0, errors.New("database is not configured")
	}
	var allowed bool
	if err := r.DB.QueryRowContext(ctx, `SELECT EXISTS(SELECT 1 FROM classes_class c WHERE c.id = $1 AND (c.is_public = true OR EXISTS(SELECT 1 FROM classes_membership m WHERE m.class_obj_id = c.id AND m.user_id = $2)))`, classID, userID).Scan(&allowed); err != nil {
		return nil, 0, err
	}
	if !allowed {
		return nil, 0, ErrClassNotFound
	}
	var total int
	if err := r.DB.QueryRowContext(ctx, `SELECT COUNT(*) FROM classes_membership WHERE class_obj_id = $1`, classID).Scan(&total); err != nil {
		return nil, 0, err
	}
	rows, err := r.DB.QueryContext(ctx, `
SELECT u.id, u.full_name, u.email, u.user_type, NULLIF(u.profile_image, ''), m.role, m.joined_at
FROM classes_membership m
JOIN authentication_user u ON u.id = m.user_id
WHERE m.class_obj_id = $1
ORDER BY u.id
LIMIT $2 OFFSET $3`, classID, limit, offset)
	if err != nil {
		return nil, 0, err
	}
	defer rows.Close()
	members := make([]Member, 0)
	for rows.Next() {
		var member Member
		var image sql.NullString
		if err := rows.Scan(&member.ID, &member.FullName, &member.Email, &member.UserType, &image, &member.Role, &member.JoinedAt); err != nil {
			return nil, 0, err
		}
		if image.Valid {
			member.ProfileImage = image.String
		}
		members = append(members, member)
	}
	return members, total, rows.Err()
}

func generateClassCode() string {
	const alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
	var raw [6]byte
	if _, err := rand.Read(raw[:]); err != nil {
		return strings.ToUpper(uuid.NewString()[:6])
	}
	for index := range raw {
		raw[index] = alphabet[int(raw[index])%len(alphabet)]
	}
	return string(raw[:])
}

func (r Repository) Update(ctx context.Context, classID uuid.UUID, userID int64, name, description *string, isPublic *bool) (Class, error) {
	if r.DB == nil {
		return Class{}, errors.New("database is not configured")
	}
	var creatorID int64
	if err := r.DB.QueryRowContext(ctx, `SELECT creator_id FROM classes_class WHERE id = $1`, classID).Scan(&creatorID); errors.Is(err, sql.ErrNoRows) {
		return Class{}, ErrClassNotFound
	} else if err != nil {
		return Class{}, err
	}
	if creatorID != userID {
		return Class{}, errors.New("only the class creator can update this class")
	}
	_, err := r.DB.ExecContext(ctx, `
UPDATE classes_class
SET name = COALESCE($2, name), description = COALESCE($3, description), is_public = COALESCE($4, is_public), updated_at = NOW()
WHERE id = $1`, classID, name, description, isPublic)
	if err != nil {
		return Class{}, err
	}
	return r.FindForUser(ctx, classID, userID)
}

func (r Repository) Delete(ctx context.Context, classID uuid.UUID, userID int64) error {
	if r.DB == nil {
		return errors.New("database is not configured")
	}
	var creatorID int64
	if err := r.DB.QueryRowContext(ctx, `SELECT creator_id FROM classes_class WHERE id = $1`, classID).Scan(&creatorID); errors.Is(err, sql.ErrNoRows) {
		return ErrClassNotFound
	} else if err != nil {
		return err
	}
	if creatorID != userID {
		return errors.New("only the class creator can delete this class")
	}
	_, err := r.DB.ExecContext(ctx, `DELETE FROM classes_class WHERE id = $1`, classID)
	return err
}
