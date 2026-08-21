package database

import (
	"database/sql"
	"time"

	_ "github.com/jackc/pgx/v5/stdlib"
)

// Config controls the shared PostgreSQL pool used by the Go service.
type Config struct {
	URL             string
	MaxOpenConns    int
	MaxIdleConns    int
	ConnMaxLifetime time.Duration
	ConnMaxIdleTime time.Duration
}

func OpenPostgres(cfg Config) (*sql.DB, error) {
	if cfg.URL == "" {
		return nil, nil
	}

	db, err := sql.Open("pgx", cfg.URL)
	if err != nil {
		return nil, err
	}

	db.SetMaxOpenConns(cfg.MaxOpenConns)
	db.SetMaxIdleConns(minInt(cfg.MaxIdleConns, cfg.MaxOpenConns))
	db.SetConnMaxLifetime(cfg.ConnMaxLifetime)
	db.SetConnMaxIdleTime(cfg.ConnMaxIdleTime)

	return db, nil
}

func minInt(left, right int) int {
	if left < right {
		return left
	}
	return right
}
