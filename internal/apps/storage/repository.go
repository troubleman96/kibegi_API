package storage

import (
	"context"
	"database/sql"
	"time"
)

type UserStorage struct {
	ID               int64      `json:"id"`
	User             int64      `json:"user"`
	UserEmail        string     `json:"user_email"`
	UserFullName     string     `json:"user_full_name"`
	TotalQuotaMB     float64    `json:"total_quota_mb"`
	UsedStorageBytes int64      `json:"used_storage_bytes"`
	UsedStorageMB    float64    `json:"used_storage_mb"`
	FreeStorageMB    float64    `json:"free_storage_mb"`
	FreeStorageBytes int64      `json:"free_storage_bytes"`
	UsagePercentage  float64    `json:"usage_percentage"`
	IsFull           bool       `json:"is_full"`
	IsNearLimit      bool       `json:"is_near_limit"`
	CreatedAt        time.Time  `json:"created_at"`
	UpdatedAt        time.Time  `json:"updated_at"`
	LastCalculated   *time.Time `json:"last_calculated"`
}

type StorageInfo struct {
	TotalQuotaMB     float64    `json:"total_quota_mb"`
	UsedStorageMB    float64    `json:"used_storage_mb"`
	FreeStorageMB    float64    `json:"free_storage_mb"`
	UsedStorageBytes int64      `json:"used_storage_bytes"`
	FreeStorageBytes int64      `json:"free_storage_bytes"`
	UsagePercentage  float64    `json:"usage_percentage"`
	IsFull           bool       `json:"is_full"`
	IsNearLimit      bool       `json:"is_near_limit"`
	LastCalculated   *time.Time `json:"last_calculated"`
}

type UsageHistory struct {
	ID               int64     `json:"id"`
	UserStorage      int64     `json:"user_storage"`
	UsedStorageBytes int64     `json:"used_storage_bytes"`
	UsedStorageMB    float64   `json:"used_storage_mb"`
	RecordedAt       time.Time `json:"recorded_at"`
}

type Repository struct{ DB *sql.DB }

func (r Repository) ensure(ctx context.Context, userID int64, recalculate bool) (UserStorage, error) {
	if _, err := r.DB.ExecContext(ctx, `INSERT INTO storage_userstorage (user_id,total_quota_mb,used_storage_bytes,created_at,updated_at,last_calculated) VALUES ($1,50.00,0,NOW(),NOW(),NOW()) ON CONFLICT (user_id) DO NOTHING`, userID); err != nil {
		return UserStorage{}, err
	}
	if recalculate {
		if _, err := r.DB.ExecContext(ctx, `UPDATE storage_userstorage SET used_storage_bytes=COALESCE((SELECT SUM(file_size) FROM uploads_upload WHERE uploader_id=$1),0),last_calculated=NOW(),updated_at=NOW() WHERE user_id=$1`, userID); err != nil {
			return UserStorage{}, err
		}
	}
	return r.find(ctx, userID)
}

func (r Repository) find(ctx context.Context, userID int64) (UserStorage, error) {
	var x UserStorage
	err := r.DB.QueryRowContext(ctx, `SELECT s.id,s.user_id,u.email,u.full_name,s.total_quota_mb,s.used_storage_bytes,s.created_at,s.updated_at,s.last_calculated FROM storage_userstorage s JOIN authentication_user u ON u.id=s.user_id WHERE s.user_id=$1`, userID).Scan(&x.ID, &x.User, &x.UserEmail, &x.UserFullName, &x.TotalQuotaMB, &x.UsedStorageBytes, &x.CreatedAt, &x.UpdatedAt, &x.LastCalculated)
	if err != nil {
		return x, err
	}
	return normalize(x), nil
}

func normalize(x UserStorage) UserStorage {
	const mb = 1024.0 * 1024.0
	x.UsedStorageMB = round2(float64(x.UsedStorageBytes) / mb)
	x.FreeStorageMB = round2(maxFloat(0, x.TotalQuotaMB-x.UsedStorageMB))
	quotaBytes := int64(x.TotalQuotaMB * mb)
	x.FreeStorageBytes = quotaBytes - x.UsedStorageBytes
	if x.FreeStorageBytes < 0 {
		x.FreeStorageBytes = 0
	}
	if x.TotalQuotaMB == 0 {
		x.UsagePercentage = 0
	} else {
		x.UsagePercentage = round2(float64(x.UsedStorageBytes) / quotaBytesFloat(x.TotalQuotaMB) * 100)
	}
	if x.UsagePercentage < 0 {
		x.UsagePercentage = 0
	}
	if x.UsagePercentage > 100 {
		x.UsagePercentage = 100
	}
	x.IsFull = x.UsedStorageBytes >= quotaBytes
	x.IsNearLimit = x.UsagePercentage >= 90
	return x
}
func quotaBytesFloat(mb float64) float64 { return mb * 1024 * 1024 }
func maxFloat(a, b float64) float64 {
	if a > b {
		return a
	}
	return b
}
func round2(v float64) float64 {
	if v < 0.005 && v > -0.005 {
		return 0
	}
	return float64(int64(v*100+0.5)) / 100
}

func (r Repository) Current(ctx context.Context, userID int64, recalculate bool) (UserStorage, error) {
	return r.ensure(ctx, userID, recalculate)
}
func (r Repository) Info(ctx context.Context, userID int64) (StorageInfo, error) {
	x, err := r.ensure(ctx, userID, true)
	if err != nil {
		return StorageInfo{}, err
	}
	return StorageInfo{TotalQuotaMB: x.TotalQuotaMB, UsedStorageMB: x.UsedStorageMB, FreeStorageMB: x.FreeStorageMB, UsedStorageBytes: x.UsedStorageBytes, FreeStorageBytes: x.FreeStorageBytes, UsagePercentage: x.UsagePercentage, IsFull: x.IsFull, IsNearLimit: x.IsNearLimit, LastCalculated: x.LastCalculated}, nil
}
func (r Repository) History(ctx context.Context, userID int64, limit int) ([]UsageHistory, error) {
	rows, err := r.DB.QueryContext(ctx, `SELECT h.id,h.user_storage,h.used_storage_bytes,h.recorded_at FROM storage_storageusagehistory h JOIN storage_userstorage s ON s.id=h.user_storage_id WHERE s.user_id=$1 ORDER BY h.recorded_at DESC LIMIT $2`, userID, limit)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := make([]UsageHistory, 0)
	for rows.Next() {
		var x UsageHistory
		if err := rows.Scan(&x.ID, &x.UserStorage, &x.UsedStorageBytes, &x.RecordedAt); err != nil {
			return nil, err
		}
		x.UsedStorageMB = round2(float64(x.UsedStorageBytes) / (1024 * 1024))
		out = append(out, x)
	}
	return out, rows.Err()
}
