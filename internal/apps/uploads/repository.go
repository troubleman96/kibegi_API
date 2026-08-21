package uploads

import (
	"context"
	"database/sql"
	"errors"
	"fmt"
	"strings"
	"time"

	"github.com/google/uuid"
)

var (
	ErrUploadNotFound = errors.New("upload not found")
	ErrUploadDenied   = errors.New("upload access denied")
)

type Upload struct {
	ID            uuid.UUID  `json:"id"`
	ObjectName    string     `json:"-"`
	FileName      string     `json:"file_name"`
	FileType      string     `json:"file_type"`
	FileSize      int64      `json:"file_size"`
	FileCode      string     `json:"file_code"`
	UploaderID    int64      `json:"uploader"`
	UploaderName  string     `json:"uploader_name"`
	UploaderType  string     `json:"-"`
	UploaderImage any        `json:"uploader_profile_image"`
	ClassID       uuid.UUID  `json:"class_obj"`
	ClassName     string     `json:"class_name"`
	IsDeleted     bool       `json:"is_deleted"`
	DeletedAt     *time.Time `json:"deleted_at"`
	CreatedAt     time.Time  `json:"created_at"`
	UpdatedAt     time.Time  `json:"updated_at"`
}

type Repository struct {
	DB *sql.DB
}

func (r Repository) Create(ctx context.Context, userID int64, classID uuid.UUID, fileName, fileType, objectName string, size int64) (Upload, error) {
	if r.DB == nil {
		return Upload{}, errors.New("database is not configured")
	}
	var member bool
	if err := r.DB.QueryRowContext(ctx, `SELECT EXISTS(SELECT 1 FROM classes_membership WHERE class_obj_id = $1 AND user_id = $2)`, classID, userID).Scan(&member); err != nil {
		return Upload{}, err
	}
	if !member {
		return Upload{}, ErrUploadDenied
	}
	for attempt := 0; attempt < 10; attempt++ {
		id := uuid.New()
		code := generateFileCode()
		var item Upload
		err := r.DB.QueryRowContext(ctx, `
INSERT INTO uploads_upload (id, file, file_name, file_type, file_size, file_code, is_deleted, deleted_at, created_at, updated_at, class_obj_id, uploader_id)
SELECT $1, $2, $3, $4, $5, $6, false, NULL, NOW(), NOW(), c.id, $7
FROM classes_class c
WHERE c.id = $8
RETURNING id, file, file_name, file_type, file_size, file_code, uploader_id, class_obj_id, is_deleted, deleted_at, created_at, updated_at`, id, objectName, fileName, fileType, size, code, userID, classID).Scan(
			&item.ID, &item.ObjectName, &item.FileName, &item.FileType, &item.FileSize, &item.FileCode, &item.UploaderID, &item.ClassID, &item.IsDeleted, &item.DeletedAt, &item.CreatedAt, &item.UpdatedAt)
		if err == nil {
			return r.enrich(ctx, item)
		}
		if !strings.Contains(strings.ToLower(err.Error()), "duplicate") {
			return Upload{}, err
		}
	}
	return Upload{}, errors.New("could not generate a unique file code")
}

func (r Repository) List(ctx context.Context, userID int64, userType, classID, query, mode string, limit, offset int) ([]Upload, int, error) {
	if r.DB == nil {
		return nil, 0, errors.New("database is not configured")
	}
	filters := []string{"u.is_deleted = false"}
	args := []any{}
	if mode == "trash" {
		filters = []string{"u.is_deleted = true", "u.uploader_id = $1"}
		args = append(args, userID)
	} else if mode == "own" {
		filters = []string{"u.is_deleted = false", "u.uploader_id = $1"}
		args = append(args, userID)
	} else if mode == "shared" {
		filters = []string{"u.is_deleted = false", "EXISTS(SELECT 1 FROM sharing_sharedfile sf WHERE sf.upload_id = u.id AND sf.shared_with_id = $1 AND sf.status = 'accepted')"}
		args = append(args, userID)
	} else if userType == "lecturer" {
		filters = append(filters, fmt.Sprintf("u.uploader_id = $%d", len(args)+1))
		args = append(args, userID)
	} else {
		filters = append(filters, fmt.Sprintf("EXISTS(SELECT 1 FROM classes_membership cm WHERE cm.class_obj_id = u.class_obj_id AND cm.user_id = $%d)", len(args)+1))
		args = append(args, userID)
	}
	if classID != "" {
		parsed, err := uuid.Parse(classID)
		if err != nil {
			return nil, 0, err
		}
		filters = append(filters, fmt.Sprintf("u.class_obj_id = $%d", len(args)+1))
		args = append(args, parsed)
	}
	if query != "" {
		filters = append(filters, fmt.Sprintf("(u.file_name ILIKE $%d OR u.file_code ILIKE $%d)", len(args)+1, len(args)+1))
		args = append(args, "%"+query+"%")
	}
	if mode == "recent" {
		filters = append(filters, "u.created_at >= NOW() - INTERVAL '7 days'")
	}
	where := strings.Join(filters, " AND ")
	var total int
	countArgs := append([]any(nil), args...)
	if err := r.DB.QueryRowContext(ctx, `SELECT COUNT(*) FROM uploads_upload u WHERE `+where, countArgs...).Scan(&total); err != nil {
		return nil, 0, err
	}
	args = append(args, limit, offset)
	rows, err := r.DB.QueryContext(ctx, `
SELECT u.id, u.file, u.file_name, u.file_type, u.file_size, u.file_code, u.uploader_id, u.class_obj_id,
       u.is_deleted, u.deleted_at, u.created_at, u.updated_at
FROM uploads_upload u
WHERE `+where+`
ORDER BY u.created_at DESC
LIMIT $`+fmt.Sprint(len(args)-1)+` OFFSET $`+fmt.Sprint(len(args)), args...)
	if err != nil {
		return nil, 0, err
	}
	defer rows.Close()
	items := make([]Upload, 0)
	for rows.Next() {
		var item Upload
		if err := rows.Scan(&item.ID, &item.ObjectName, &item.FileName, &item.FileType, &item.FileSize, &item.FileCode, &item.UploaderID, &item.ClassID, &item.IsDeleted, &item.DeletedAt, &item.CreatedAt, &item.UpdatedAt); err != nil {
			return nil, 0, err
		}
		item, err = r.enrich(ctx, item)
		if err != nil {
			return nil, 0, err
		}
		items = append(items, item)
	}
	return items, total, rows.Err()
}

func (r Repository) FindByCode(ctx context.Context, userID int64, fileCode string, includeDeleted bool) (Upload, error) {
	if r.DB == nil {
		return Upload{}, errors.New("database is not configured")
	}
	deletedFilter := "u.is_deleted = false"
	if includeDeleted {
		deletedFilter = "u.is_deleted = true"
	}
	var item Upload
	err := r.DB.QueryRowContext(ctx, `
SELECT u.id, u.file, u.file_name, u.file_type, u.file_size, u.file_code, u.uploader_id, u.class_obj_id,
       u.is_deleted, u.deleted_at, u.created_at, u.updated_at
FROM uploads_upload u
WHERE u.file_code = $1 AND `+deletedFilter+`
  AND (u.uploader_id = $2 OR EXISTS(SELECT 1 FROM classes_membership cm WHERE cm.class_obj_id = u.class_obj_id AND cm.user_id = $2) OR EXISTS(SELECT 1 FROM sharing_sharedfile sf WHERE sf.upload_id = u.id AND sf.shared_with_id = $2 AND sf.status = 'accepted'))`, fileCode, userID).Scan(
		&item.ID, &item.ObjectName, &item.FileName, &item.FileType, &item.FileSize, &item.FileCode, &item.UploaderID, &item.ClassID, &item.IsDeleted, &item.DeletedAt, &item.CreatedAt, &item.UpdatedAt)
	if errors.Is(err, sql.ErrNoRows) {
		return Upload{}, ErrUploadNotFound
	}
	if err != nil {
		return Upload{}, err
	}
	return r.enrich(ctx, item)
}

func (r Repository) Restore(ctx context.Context, userID int64, id uuid.UUID) (Upload, error) {
	if r.DB == nil {
		return Upload{}, errors.New("database is not configured")
	}
	var item Upload
	err := r.DB.QueryRowContext(ctx, `
UPDATE uploads_upload
SET is_deleted = false, deleted_at = NULL, updated_at = NOW()
WHERE id = $1 AND uploader_id = $2 AND is_deleted = true
RETURNING id, file, file_name, file_type, file_size, file_code, uploader_id, class_obj_id, is_deleted, deleted_at, created_at, updated_at`, id, userID).Scan(
		&item.ID, &item.ObjectName, &item.FileName, &item.FileType, &item.FileSize, &item.FileCode, &item.UploaderID, &item.ClassID, &item.IsDeleted, &item.DeletedAt, &item.CreatedAt, &item.UpdatedAt)
	if errors.Is(err, sql.ErrNoRows) {
		return Upload{}, ErrUploadNotFound
	}
	if err != nil {
		return Upload{}, err
	}
	return r.enrich(ctx, item)
}

func (r Repository) SoftDelete(ctx context.Context, userID int64, fileCode string) error {
	if r.DB == nil {
		return errors.New("database is not configured")
	}
	result, err := r.DB.ExecContext(ctx, `UPDATE uploads_upload SET is_deleted = true, deleted_at = NOW(), updated_at = NOW() WHERE file_code = $1 AND uploader_id = $2 AND is_deleted = false`, fileCode, userID)
	if err != nil {
		return err
	}
	count, _ := result.RowsAffected()
	if count == 0 {
		return ErrUploadNotFound
	}
	return nil
}

func (r Repository) PermanentDelete(ctx context.Context, userID int64, id uuid.UUID) (string, string, error) {
	if r.DB == nil {
		return "", "", errors.New("database is not configured")
	}
	var fileName, objectName string
	err := r.DB.QueryRowContext(ctx, `DELETE FROM uploads_upload WHERE id = $1 AND uploader_id = $2 AND is_deleted = true RETURNING file_name, file`, id, userID).Scan(&fileName, &objectName)
	if errors.Is(err, sql.ErrNoRows) {
		return "", "", ErrUploadNotFound
	}
	return fileName, objectName, err
}

func (r Repository) enrich(ctx context.Context, item Upload) (Upload, error) {
	err := r.DB.QueryRowContext(ctx, `
SELECT u.full_name, u.user_type, NULLIF(u.profile_image, ''), c.name
FROM authentication_user u JOIN classes_class c ON c.id = $1
WHERE u.id = $2`, item.ClassID, item.UploaderID).Scan(&item.UploaderName, &item.UploaderType, &item.UploaderImage, &item.ClassName)
	return item, err
}

func generateFileCode() string {
	return strings.ToUpper(uuid.NewString()[:8])
}
