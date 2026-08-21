package friends

import (
	"context"
	"database/sql"
	"errors"
	"fmt"
	"strings"
	"time"

	"github.com/troubleman96/kibegi_API/internal/apps/notifications"
)

var (
	ErrFriendNotFound = errors.New("Friendship not found")
	ErrFriendExists   = errors.New("Friend request already exists")
	ErrSelfFriend     = errors.New("Cannot add yourself as a friend")
)

type User struct {
	ID           int64  `json:"id"`
	Email        string `json:"email"`
	FullName     string `json:"full_name"`
	UserType     string `json:"user_type"`
	ProfileImage any    `json:"profile_image"`
}

type Friendship struct {
	ID         int64      `json:"id"`
	UserID     int64      `json:"user"`
	FriendID   int64      `json:"friend"`
	User       User       `json:"-"`
	Friend     User       `json:"-"`
	Nickname   string     `json:"nickname"`
	Status     string     `json:"status"`
	CreatedAt  time.Time  `json:"created_at"`
	AcceptedAt *time.Time `json:"accepted_at"`
}

type Repository struct {
	DB            *sql.DB
	Notifications notifications.Repository
}

func (r Repository) FindUser(ctx context.Context, id *int64, email string) (User, error) {
	if r.DB == nil {
		return User{}, errors.New("database is not configured")
	}
	var user User
	var image sql.NullString
	var err error
	if id != nil {
		err = r.DB.QueryRowContext(ctx, `SELECT id, email, full_name, user_type, NULLIF(profile_image, '') FROM authentication_user WHERE id = $1`, *id).Scan(&user.ID, &user.Email, &user.FullName, &user.UserType, &image)
	} else {
		err = r.DB.QueryRowContext(ctx, `SELECT id, email, full_name, user_type, NULLIF(profile_image, '') FROM authentication_user WHERE LOWER(email) = LOWER($1)`, email).Scan(&user.ID, &user.Email, &user.FullName, &user.UserType, &image)
	}
	if errors.Is(err, sql.ErrNoRows) {
		return User{}, ErrFriendNotFound
	}
	if image.Valid {
		user.ProfileImage = image.String
	}
	return user, err
}

func (r Repository) Add(ctx context.Context, userID, friendID int64) (Friendship, error) {
	if userID == friendID {
		return Friendship{}, ErrSelfFriend
	}
	if r.DB == nil {
		return Friendship{}, errors.New("database is not configured")
	}
	var exists bool
	if err := r.DB.QueryRowContext(ctx, `SELECT EXISTS(SELECT 1 FROM friends_friendship WHERE (user_id = $1 AND friend_id = $2) OR (user_id = $2 AND friend_id = $1))`, userID, friendID).Scan(&exists); err != nil {
		return Friendship{}, err
	}
	if exists {
		return Friendship{}, ErrFriendExists
	}
	var item Friendship
	err := r.DB.QueryRowContext(ctx, `INSERT INTO friends_friendship (nickname, status, created_at, accepted_at, user_id, friend_id) VALUES ('', 'pending', NOW(), NULL, $1, $2) RETURNING id, nickname, status, created_at, accepted_at`, userID, friendID).Scan(&item.ID, &item.Nickname, &item.Status, &item.CreatedAt, &item.AcceptedAt)
	if err != nil {
		return Friendship{}, err
	}
	item.UserID, item.FriendID = userID, friendID
	item.User, _ = r.FindUser(ctx, &userID, "")
	item.Friend, _ = r.FindUser(ctx, &friendID, "")
	_, _ = r.Notifications.Create(ctx, friendID, "friend_request", item.User.FullName+" sent you a friend request", fmt.Sprint(item.ID))
	return item, nil
}

func (r Repository) List(ctx context.Context, userID int64, status string, limit, offset int) ([]Friendship, int, error) {
	if r.DB == nil {
		return nil, 0, errors.New("database is not configured")
	}
	filters := []string{"(f.user_id = $1 OR f.friend_id = $1)"}
	args := []any{userID}
	if status != "" {
		filters = append(filters, fmt.Sprintf("f.status = $%d", len(args)+1))
		args = append(args, status)
	}
	where := strings.Join(filters, " AND ")
	var count int
	if err := r.DB.QueryRowContext(ctx, `SELECT COUNT(*) FROM friends_friendship f WHERE `+where, args...).Scan(&count); err != nil {
		return nil, 0, err
	}
	args = append(args, limit, offset)
	rows, err := r.DB.QueryContext(ctx, `
SELECT f.id, f.user_id, u.email, u.full_name, u.user_type, NULLIF(u.profile_image, ''), f.friend_id, fr.email, fr.full_name, fr.user_type, NULLIF(fr.profile_image, ''), f.nickname, f.status, f.created_at, f.accepted_at
FROM friends_friendship f JOIN authentication_user u ON u.id = f.user_id JOIN authentication_user fr ON fr.id = f.friend_id
WHERE `+where+` ORDER BY f.created_at DESC LIMIT $`+fmt.Sprint(len(args)-1)+` OFFSET $`+fmt.Sprint(len(args)), args...)
	if err != nil {
		return nil, 0, err
	}
	defer rows.Close()
	items := make([]Friendship, 0)
	for rows.Next() {
		item, err := scanFriendship(rows)
		if err != nil {
			return nil, 0, err
		}
		items = append(items, item)
	}
	return items, count, rows.Err()
}

func (r Repository) Incoming(ctx context.Context, userID int64, limit, offset int) ([]Friendship, int, error) {
	return r.ListDirectional(ctx, "friend_id", userID, "pending", limit, offset)
}

func (r Repository) Sent(ctx context.Context, userID int64, limit, offset int) ([]Friendship, int, error) {
	return r.ListDirectional(ctx, "user_id", userID, "pending", limit, offset)
}

func (r Repository) ListDirectional(ctx context.Context, column string, userID int64, status string, limit, offset int) ([]Friendship, int, error) {
	if column != "friend_id" && column != "user_id" {
		return nil, 0, errors.New("invalid friendship direction")
	}
	if r.DB == nil {
		return nil, 0, errors.New("database is not configured")
	}
	var count int
	if err := r.DB.QueryRowContext(ctx, `SELECT COUNT(*) FROM friends_friendship WHERE `+column+` = $1 AND status = $2`, userID, status).Scan(&count); err != nil {
		return nil, 0, err
	}
	rows, err := r.DB.QueryContext(ctx, `
SELECT f.id, f.user_id, u.email, u.full_name, u.user_type, NULLIF(u.profile_image, ''), f.friend_id, fr.email, fr.full_name, fr.user_type, NULLIF(fr.profile_image, ''), f.nickname, f.status, f.created_at, f.accepted_at
FROM friends_friendship f JOIN authentication_user u ON u.id = f.user_id JOIN authentication_user fr ON fr.id = f.friend_id
WHERE f.`+column+` = $1 AND f.status = $2 ORDER BY f.created_at DESC LIMIT $3 OFFSET $4`, userID, status, limit, offset)
	if err != nil {
		return nil, 0, err
	}
	defer rows.Close()
	items := make([]Friendship, 0)
	for rows.Next() {
		item, err := scanFriendship(rows)
		if err != nil {
			return nil, 0, err
		}
		items = append(items, item)
	}
	return items, count, rows.Err()
}

func (r Repository) SearchUsers(ctx context.Context, userID int64, query string, limit int) ([]User, error) {
	if r.DB == nil {
		return nil, errors.New("database is not configured")
	}
	rows, err := r.DB.QueryContext(ctx, `SELECT id, email, full_name, user_type, NULLIF(profile_image, '') FROM authentication_user WHERE id <> $1 AND is_active = true AND (email ILIKE $2 OR full_name ILIKE $2) ORDER BY full_name LIMIT $3`, userID, "%"+query+"%", limit)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	users := make([]User, 0)
	for rows.Next() {
		var user User
		var image sql.NullString
		if err := rows.Scan(&user.ID, &user.Email, &user.FullName, &user.UserType, &image); err != nil {
			return nil, err
		}
		if image.Valid {
			user.ProfileImage = image.String
		}
		users = append(users, user)
	}
	return users, rows.Err()
}

func (r Repository) Transition(ctx context.Context, id, userID int64, action string) (Friendship, error) {
	if r.DB == nil {
		return Friendship{}, errors.New("database is not configured")
	}
	var item Friendship
	var err error
	switch action {
	case "accept":
		err = r.DB.QueryRowContext(ctx, `UPDATE friends_friendship SET status = 'accepted', accepted_at = NOW() WHERE id = $1 AND friend_id = $2 AND status = 'pending' RETURNING id, user_id, friend_id, nickname, status, created_at, accepted_at`, id, userID).Scan(&item.ID, &item.UserID, &item.FriendID, &item.Nickname, &item.Status, &item.CreatedAt, &item.AcceptedAt)
	case "decline", "cancel":
		var column string
		if action == "decline" {
			column = "friend_id"
		} else {
			column = "user_id"
		}
		_, err = r.DB.ExecContext(ctx, `DELETE FROM friends_friendship WHERE id = $1 AND `+column+` = $2 AND status = 'pending'`, id, userID)
		if err == nil {
			item.ID = id
		}
	default:
		return Friendship{}, errors.New("invalid friendship action")
	}
	if errors.Is(err, sql.ErrNoRows) {
		return Friendship{}, ErrFriendNotFound
	}
	if err != nil {
		return Friendship{}, err
	}
	if action != "accept" {
		return item, nil
	}
	item.User, _ = r.FindUser(ctx, &item.UserID, "")
	item.Friend, _ = r.FindUser(ctx, &item.FriendID, "")
	_, _ = r.Notifications.Create(ctx, item.UserID, "friend_accepted", item.Friend.FullName+" accepted your friend request", fmt.Sprint(item.ID))
	return item, nil
}

func (r Repository) UpdateNickname(ctx context.Context, id, userID int64, nickname string) error {
	if r.DB == nil {
		return errors.New("database is not configured")
	}
	result, err := r.DB.ExecContext(ctx, `UPDATE friends_friendship SET nickname = $3 WHERE id = $1 AND user_id = $2 AND status = 'accepted'`, id, userID, nickname)
	if err != nil {
		return err
	}
	count, _ := result.RowsAffected()
	if count == 0 {
		return ErrFriendNotFound
	}
	return nil
}

func (r Repository) Remove(ctx context.Context, id, userID int64) error {
	if r.DB == nil {
		return errors.New("database is not configured")
	}
	result, err := r.DB.ExecContext(ctx, `DELETE FROM friends_friendship WHERE id = $1 AND (user_id = $2 OR friend_id = $2)`, id, userID)
	if err != nil {
		return err
	}
	count, _ := result.RowsAffected()
	if count == 0 {
		return ErrFriendNotFound
	}
	return nil
}

func scanFriendship(scanner interface{ Scan(dest ...any) error }) (Friendship, error) {
	var item Friendship
	var userImage, friendImage sql.NullString
	err := scanner.Scan(&item.ID, &item.UserID, &item.User.Email, &item.User.FullName, &item.User.UserType, &userImage, &item.FriendID, &item.Friend.Email, &item.Friend.FullName, &item.Friend.UserType, &friendImage, &item.Nickname, &item.Status, &item.CreatedAt, &item.AcceptedAt)
	item.User.ID = item.UserID
	item.Friend.ID = item.FriendID
	if userImage.Valid {
		item.User.ProfileImage = userImage.String
	}
	if friendImage.Valid {
		item.Friend.ProfileImage = friendImage.String
	}
	return item, err
}
