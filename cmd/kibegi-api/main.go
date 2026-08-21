package main

import (
	"context"
	"database/sql"
	"errors"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	_ "github.com/jackc/pgx/v5/stdlib"

	"github.com/troubleman96/kibegi_API/internal/apps/core"
	"github.com/troubleman96/kibegi_API/internal/config"
	"github.com/troubleman96/kibegi_API/internal/platform/cache"
	"github.com/troubleman96/kibegi_API/internal/platform/middleware"
)

func main() {
	cfg := config.FromEnv()
	logger := slog.New(slog.NewJSONHandler(os.Stdout, nil))

	var db *sql.DB
	if cfg.DatabaseURL != "" {
		openedDB, err := sql.Open("pgx", cfg.DatabaseURL)
		if err != nil {
			logger.Error("open database", "error", err)
			os.Exit(1)
		}
		db = openedDB
		db.SetMaxOpenConns(cfg.DBMaxOpenConns)
		db.SetMaxIdleConns(minInt(cfg.DBMaxIdleConns, cfg.DBMaxOpenConns))
		db.SetConnMaxLifetime(cfg.DBConnMaxLifetime)
		db.SetConnMaxIdleTime(cfg.DBConnMaxIdleTime)
		defer db.Close()
	} else {
		logger.Warn("DATABASE_URL is not configured; health endpoint will report database failure")
	}

	redisClient, err := cache.NewRedis(cfg.RedisURL, cfg.RedisPoolSize, cfg.RedisMinIdleConns, cfg.CacheDefaultTTL)
	if err != nil {
		logger.Error("configure redis", "error", err)
		os.Exit(1)
	}
	defer redisClient.Close()
	if !redisClient.Configured() {
		logger.Warn("REDIS_URL is not configured; cache and coordination features will be disabled")
	}

	mux := http.NewServeMux()
	mux.Handle("/api/v1/health/", core.HealthHandler{
		DB:           db,
		Redis:        redisClient,
		PingTimeout:  cfg.DatabasePingTimeout,
		RedisTimeout: cfg.RedisPingTimeout,
		ServiceName:  "kibegi_api",
	})

	baseHandler := requestTimeoutMiddleware(mux, 30*time.Second)
	baseHandler = middleware.Recoverer(logger)(baseHandler)
	baseHandler = middleware.AccessLog(logger)(baseHandler)
	baseHandler = middleware.RequestID(baseHandler)

	server := &http.Server{
		Addr:              cfg.HTTPAddr,
		Handler:           baseHandler,
		ReadHeaderTimeout: 5 * time.Second,
		ReadTimeout:       30 * time.Second,
		WriteTimeout:      30 * time.Second,
		IdleTimeout:       60 * time.Second,
	}

	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	serverErr := make(chan error, 1)
	go func() {
		logger.Info("starting Go API", "addr", cfg.HTTPAddr)
		if err := server.ListenAndServe(); !errors.Is(err, http.ErrServerClosed) {
			serverErr <- err
		}
		close(serverErr)
	}()

	select {
	case err := <-serverErr:
		if err != nil {
			logger.Error("HTTP server stopped unexpectedly", "error", err)
			os.Exit(1)
		}
	case <-ctx.Done():
		shutdownCtx, cancel := context.WithTimeout(context.Background(), cfg.ShutdownTimeout)
		defer cancel()
		if err := server.Shutdown(shutdownCtx); err != nil {
			logger.Error("graceful shutdown failed", "error", err)
			os.Exit(1)
		}
		logger.Info("Go API stopped")
	}
}

func minInt(left, right int) int {
	if left < right {
		return left
	}
	return right
}

func requestTimeoutMiddleware(next http.Handler, timeout time.Duration) http.Handler {
	return http.TimeoutHandler(next, timeout, `{"success":false,"message":"request timed out","data":null,"errors":null}`)
}
