package sharing

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
	ErrShareNotFound = errors.New("share not found")
	ErrShareDenied   = errors.New("share access denied")
	ErrDuplicate     = errors.New("file already shared with this user")
)

type Share struct {
	ID              uuid.UUID  `json:"id"`
	UploadID        uuid.UUID  `json:"-"`
	FileName        string     `json:"file_name"`
	FileType        string     `json:"file_type"`
	FileCode        string     `json:"file_code"`
	SharedBy        int64      `json:"shared_by"`
	SharedByName    string     `json:"shared_by_name"`
	SharedByEmail   string     `json:"shared_by_email"`
	SharedByImage   any        `json:"shared_by_profile_image"`
	SharedWith      int64      `json:"shared_with"`
	SharedWithName  string     `json:"shared_with_name"`
	SharedWithEmail string     `json:"shared_with_email"`
	SharedWithImage any        `json:"shared_with_profile_image"`
	Status          string     `json:"status"`
	Message         string     `json:"message"`
	SharedAt        time.Time  `json:"shared_at"`
	AcceptedAt      *time.Time `json:"accepted_at"`
	RejectedAt      *time.Time `json:"rejected_at"`
	IsDeleted       bool       `json:"-"`
	ObjectName      string     `json:"-"`
}

type Repository struct {
	DB *sql.DB
}

func (r Repository) Create(ctx context.Context, fileCode string, sharedBy, sharedWith int64, message string) (Share, error) {
	if r.DB == nil {
		return Share{}, errors.New("database is not configured")
	}
	var uploadID uuid.UUID
	var uploaderID int64
	var classID uuid.UUID
	if err := r.DB.QueryRowContext(ctx, `SELECT id, uploader_id, class_obj_id FROM uploads_upload WHERE file_code = $1 AND is_deleted = false`, strings.ToUpper(strings.TrimSpace(fileCode))).Scan(&uploadID, &uploaderID, &classID); errors.Is(err, sql.ErrNoRows) {
		return Share{}, ErrShareNotFound
	} else if err != nil {
		return Share{}, err
	}
	if uploaderID != sharedBy || sharedBy == sharedWith {
		return Share{}, ErrShareDenied
	}
	var member bool
	if err := r.DB.QueryRowContext(ctx, `SELECT EXISTS(SELECT 1 FROM classes_membership WHERE class_obj_id = $1 AND user_id = $2)`, classID, sharedWith).Scan(&member); err != nil {
		return Share{}, err
	}
	if !member {
		return Share{}, ErrShareDenied
	}
	var exists bool
	if err := r.DB.QueryRowContext(ctx, `SELECT EXISTS(SELECT 1 FROM sharing_sharedfile WHERE upload_id = $1 AND shared_with_id = $2)`, uploadID, sharedWith).Scan(&exists); err != nil {
		return Share{}, err
	}
	if exists {
		return Share{}, ErrDuplicate
	}
	var id uuid.UUID
	if err := r.DB.QueryRowContext(ctx, `
INSERT INTO sharing_sharedfile (id, status, message, shared_at, accepted_at, rejected_at, shared_by_id, shared_with_id, upload_id)
VALUES ($1, 'pending', $2, NOW(), NULL, NULL, $3, $4, $5)
RETURNING id`, uuid.New(), message, sharedBy, sharedWith, uploadID).Scan(&id); err != nil {
		return Share{}, err
	}
	return r.Find(ctx, id, sharedBy)
}

func (r Repository) List(ctx context.Context, userID int64, mode, status string, limit, offset int) ([]Share, int, error) {
	if r.DB == nil {
		return nil, 0, errors.New("database is not configured")
	}
	filters := []string{"u.is_deleted = false"}
	args := []any{}
	switch mode {
	case "requests", "received":
		filters = append(filters, fmt.Sprintf("s.shared_with_id = $%d", len(args)+1))
		args = append(args, userID)
	case "sent":
		filters = append(filters, fmt.Sprintf("s.shared_by_id = $%d", len(args)+1))
		args = append(args, userID)
	}
	if status != "" {
		filters = append(filters, fmt.Sprintf("s.status = $%d", len(args)+1))
		args = append(args, status)
	}
	where := strings.Join(filters, " AND ")
	var total int
	if err := r.DB.QueryRowContext(ctx, `SELECT COUNT(*) FROM sharing_sharedfile s JOIN uploads_upload u ON u.id = s.upload_id WHERE `+where, args...).Scan(&total); err != nil {
		return nil, 0, err
	}
	args = append(args, limit, offset)
	rows, err := r.DB.QueryContext(ctx, `
SELECT s.id, s.upload_id, u.file_name, u.file_type, u.file_code, u.file, s.shared_by_id, sb.full_name, sb.email, NULLIF(sb.profile_image, ''), s.shared_with_id, sw.full_name, sw.email, NULLIF(sw.profile_image, ''), s.status, s.message, s.shared_at, s.accepted_at, s.rejected_at, u.is_deleted
FROM sharing_sharedfile s
JOIN uploads_upload u ON u.id = s.upload_id
JOIN authentication_user sb ON sb.id = s.shared_by_id
JOIN authentication_user sw ON sw.id = s.shared_with_id
WHERE `+where+`
ORDER BY s.shared_at DESC
LIMIT $`+fmt.Sprint(len(args)-1)+` OFFSET $`+fmt.Sprint(len(args)), args...)
	if err != nil {
		return nil, 0, err
	}
	defer rows.Close()
	items := make([]Share, 0)
	for rows.Next() {
		item, err := scanShare(rows)
		if err != nil {
			return nil, 0, err
		}
		items = append(items, item)
	}
	return items, total, rows.Err()
}

func (r Repository) Find(ctx context.Context, id uuid.UUID, userID int64) (Share, error) {
	if r.DB == nil {
		return Share{}, errors.New("database is not configured")
	}
	row := r.DB.QueryRowContext(ctx, `
SELECT s.id, s.upload_id, u.file_name, u.file_type, u.file_code, u.file, s.shared_by_id, sb.full_name, sb.email, NULLIF(sb.profile_image, ''), s.shared_with_id, sw.full_name, sw.email, NULLIF(sw.profile_image, ''), s.status, s.message, s.shared_at, s.accepted_at, s.rejected_at, u.is_deleted
FROM sharing_sharedfile s
JOIN uploads_upload u ON u.id = s.upload_id
JOIN authentication_user sb ON sb.id = s.shared_by_id
JOIN authentication_user sw ON sw.id = s.shared_with_id
WHERE s.id = $1 AND (s.shared_by_id = $2 OR s.shared_with_id = $2)`, id, userID)
	item, err := scanShare(row)
	if errors.Is(err, sql.ErrNoRows) {
		return Share{}, ErrShareNotFound
	}
	return item, err
}

func (r Repository) Transition(ctx context.Context, id uuid.UUID, userID int64, status string) (Share, error) {
	if r.DB == nil {
		return Share{}, errors.New("database is not configured")
	}
	var item Share
	acceptedAt := "NULL"
	rejectedAt := "NULL"
	if status == "accepted" {
		acceptedAt = "NOW()"
	} else {
		rejectedAt = "NOW()"
	}
	query := fmt.Sprintf(`
UPDATE sharing_sharedfile
SET status = $3, accepted_at = %s, rejected_at = %s
WHERE id = $1 AND shared_with_id = $2
RETURNING id`, acceptedAt, rejectedAt)
	if err := r.DB.QueryRowContext(ctx, query, id, userID, status).Scan(&item.ID); errors.Is(err, sql.ErrNoRows) {
		return Share{}, ErrShareNotFound
	} else if err != nil {
		return Share{}, err
	}
	return r.Find(ctx, id, userID)
}

func scanShare(scanner interface{ Scan(dest ...any) error }) (Share, error) {
	var item Share
	var sharedByImage, sharedWithImage sql.NullString
	err := scanner.Scan(&item.ID, &item.UploadID, &item.FileName, &item.FileType, &item.FileCode, &item.ObjectName, &item.SharedBy, &item.SharedByName, &item.SharedByEmail, &sharedByImage, &item.SharedWith, &item.SharedWithName, &item.SharedWithEmail, &sharedWithImage, &item.Status, &item.Message, &item.SharedAt, &item.AcceptedAt, &item.RejectedAt, &item.IsDeleted)
	if sharedByImage.Valid {
		item.SharedByImage = sharedByImage.String
	}
	if sharedWithImage.Valid {
		item.SharedWithImage = sharedWithImage.String
	}
	return item, err
}
