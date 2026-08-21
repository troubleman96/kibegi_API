package notifications

import (
	"context"
	"database/sql"
	"errors"
	"fmt"
	"strings"
	"time"
)

var ErrNotificationNotFound = errors.New("Notification not found")
var ErrNotificationAlreadyRead = errors.New("Notification already marked as read")

type Notification struct {
	ID               int64     `json:"id"`
	NotificationType string    `json:"notification_type"`
	Content          string    `json:"content"`
	RelatedObjectID  string    `json:"related_object_id"`
	IsRead           bool      `json:"is_read"`
	CreatedAt        time.Time `json:"created_at"`
}

type Repository struct {
	DB *sql.DB
}

func (r Repository) Create(ctx context.Context, userID int64, notificationType, content, relatedObjectID string) (Notification, error) {
	if r.DB == nil {
		return Notification{}, errors.New("database is not configured")
	}
	var item Notification
	err := r.DB.QueryRowContext(ctx, `
INSERT INTO notifications_notification (notification_type, content, related_object_id, is_read, created_at, user_id)
VALUES ($1, $2, $3, false, NOW(), $4)
RETURNING id, notification_type, content, related_object_id, is_read, created_at`, notificationType, content, relatedObjectID, userID).Scan(
		&item.ID, &item.NotificationType, &item.Content, &item.RelatedObjectID, &item.IsRead, &item.CreatedAt)
	return item, err
}

func (r Repository) List(ctx context.Context, userID int64, isRead *bool, notificationType string, limit, offset int) ([]Notification, int, int, error) {
	if r.DB == nil {
		return nil, 0, 0, errors.New("database is not configured")
	}
	filters := []string{"user_id = $1"}
	args := []any{userID}
	if isRead != nil {
		filters = append(filters, fmt.Sprintf("is_read = $%d", len(args)+1))
		args = append(args, *isRead)
	}
	if notificationType != "" {
		filters = append(filters, fmt.Sprintf("notification_type = $%d", len(args)+1))
		args = append(args, notificationType)
	}
	where := strings.Join(filters, " AND ")
	var total, unread int
	if err := r.DB.QueryRowContext(ctx, `SELECT COUNT(*) FROM notifications_notification WHERE `+where, args...).Scan(&total); err != nil {
		return nil, 0, 0, err
	}
	if err := r.DB.QueryRowContext(ctx, `SELECT COUNT(*) FROM notifications_notification WHERE user_id = $1 AND is_read = false`, userID).Scan(&unread); err != nil {
		return nil, 0, 0, err
	}
	args = append(args, limit, offset)
	rows, err := r.DB.QueryContext(ctx, `
SELECT id, notification_type, content, related_object_id, is_read, created_at
FROM notifications_notification
WHERE `+where+`
ORDER BY created_at DESC
LIMIT $`+fmt.Sprint(len(args)-1)+` OFFSET $`+fmt.Sprint(len(args)), args...)
	if err != nil {
		return nil, 0, 0, err
	}
	defer rows.Close()
	items := make([]Notification, 0)
	for rows.Next() {
		var item Notification
		if err := rows.Scan(&item.ID, &item.NotificationType, &item.Content, &item.RelatedObjectID, &item.IsRead, &item.CreatedAt); err != nil {
			return nil, 0, 0, err
		}
		items = append(items, item)
	}
	return items, total, unread, rows.Err()
}

func (r Repository) UnreadCount(ctx context.Context, userID int64) (int, error) {
	if r.DB == nil {
		return 0, errors.New("database is not configured")
	}
	var count int
	err := r.DB.QueryRowContext(ctx, `SELECT COUNT(*) FROM notifications_notification WHERE user_id = $1 AND is_read = false`, userID).Scan(&count)
	return count, err
}

func (r Repository) MarkRead(ctx context.Context, id, userID int64) (Notification, error) {
	if r.DB == nil {
		return Notification{}, errors.New("database is not configured")
	}
	var item Notification
	err := r.DB.QueryRowContext(ctx, `
UPDATE notifications_notification
SET is_read = true
WHERE id = $1 AND user_id = $2 AND is_read = false
RETURNING id, notification_type, content, related_object_id, is_read, created_at`, id, userID).Scan(
		&item.ID, &item.NotificationType, &item.Content, &item.RelatedObjectID, &item.IsRead, &item.CreatedAt)
	if err == nil {
		return item, nil
	}
	if !errors.Is(err, sql.ErrNoRows) {
		return Notification{}, err
	}
	var exists, alreadyRead bool
	if err := r.DB.QueryRowContext(ctx, `SELECT EXISTS(SELECT 1 FROM notifications_notification WHERE id = $1 AND user_id = $2), COALESCE((SELECT is_read FROM notifications_notification WHERE id = $1 AND user_id = $2), false)`, id, userID).Scan(&exists, &alreadyRead); err != nil {
		return Notification{}, err
	}
	if !exists {
		return Notification{}, ErrNotificationNotFound
	}
	if alreadyRead {
		return Notification{}, ErrNotificationAlreadyRead
	}
	return Notification{}, ErrNotificationNotFound
}

func (r Repository) MarkAllRead(ctx context.Context, userID int64) (int64, error) {
	if r.DB == nil {
		return 0, errors.New("database is not configured")
	}
	result, err := r.DB.ExecContext(ctx, `UPDATE notifications_notification SET is_read = true WHERE user_id = $1 AND is_read = false`, userID)
	if err != nil {
		return 0, err
	}
	return result.RowsAffected()
}

func (r Repository) Delete(ctx context.Context, id, userID int64) error {
	if r.DB == nil {
		return errors.New("database is not configured")
	}
	result, err := r.DB.ExecContext(ctx, `DELETE FROM notifications_notification WHERE id = $1 AND user_id = $2`, id, userID)
	if err != nil {
		return err
	}
	count, _ := result.RowsAffected()
	if count == 0 {
		return ErrNotificationNotFound
	}
	return nil
}
