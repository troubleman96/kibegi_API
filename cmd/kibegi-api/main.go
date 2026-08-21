package main

import (
	"context"
	"errors"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/troubleman96/kibegi_API/internal/apps/authentication"
	"github.com/troubleman96/kibegi_API/internal/apps/classes"
	"github.com/troubleman96/kibegi_API/internal/apps/core"
	"github.com/troubleman96/kibegi_API/internal/apps/notifications"
	"github.com/troubleman96/kibegi_API/internal/apps/sharing"
	"github.com/troubleman96/kibegi_API/internal/apps/uploads"
	"github.com/troubleman96/kibegi_API/internal/config"
	"github.com/troubleman96/kibegi_API/internal/platform/cache"
	"github.com/troubleman96/kibegi_API/internal/platform/database"
	"github.com/troubleman96/kibegi_API/internal/platform/email"
	"github.com/troubleman96/kibegi_API/internal/platform/middleware"
	"github.com/troubleman96/kibegi_API/internal/platform/storage"
)

func main() {
	cfg := config.FromEnv()
	logger := slog.New(slog.NewJSONHandler(os.Stdout, nil))

	db, err := database.OpenPostgres(database.Config{
		URL:             cfg.DatabaseURL,
		MaxOpenConns:    cfg.DBMaxOpenConns,
		MaxIdleConns:    cfg.DBMaxIdleConns,
		ConnMaxLifetime: cfg.DBConnMaxLifetime,
		ConnMaxIdleTime: cfg.DBConnMaxIdleTime,
	})
	if err != nil {
		logger.Error("open database", "error", err)
		os.Exit(1)
	}
	if db != nil {
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

	objectStorage, err := storage.New(storage.Config{
		Enabled:    cfg.MinioEnabled,
		Endpoint:   cfg.MinioEndpoint,
		AccessKey:  cfg.MinioAccessKey,
		SecretKey:  cfg.MinioSecretKey,
		Bucket:     cfg.MinioBucket,
		Secure:     cfg.MinioSecure,
		PublicBase: cfg.MediaPublicBaseURL,
	})
	if err != nil {
		logger.Error("configure object storage", "error", err)
		os.Exit(1)
	}
	if !objectStorage.Configured() {
		logger.Warn("MinIO/S3 storage is not configured; upload endpoints will be unavailable")
	}

	mux := http.NewServeMux()
	mux.Handle("/api/v1/health/", core.HealthHandler{
		DB:           db,
		Redis:        redisClient,
		PingTimeout:  cfg.DatabasePingTimeout,
		RedisTimeout: cfg.RedisPingTimeout,
		ServiceName:  "kibegi_api",
	})

	tokens := authentication.NewTokenService(cfg.JWTSecretKey, cfg.AccessTokenLifetime, cfg.RefreshTokenLifetime)
	mailer := email.NewSender(email.Config{
		Host: cfg.EmailHost, Port: cfg.EmailPort, Username: cfg.EmailUsername,
		Password: cfg.EmailPassword, From: cfg.EmailFrom, UseTLS: cfg.EmailUseTLS,
	})
	if !mailer.Configured() {
		logger.Warn("SMTP is not configured; registration OTP delivery will be unavailable")
	}

	authApp := authentication.App{
		Users:     authentication.UserRepository{DB: db},
		Tokens:    tokens,
		Cache:     redisClient,
		MediaBase: cfg.MediaPublicBaseURL,
	}
	mux.Handle("/api/v1/auth/register/", authApp.RegisterHandler(mailer))
	mux.Handle("/api/v1/auth/register/verify/", authApp.RegisterVerifyHandler())
	mux.Handle("/api/v1/auth/register/resend/", authApp.RegisterResendHandler(mailer))
	mux.Handle("/api/v1/auth/password-reset/", authApp.PasswordResetRequestHandler(mailer))
	mux.Handle("/api/v1/auth/password-reset/verify/", authApp.PasswordResetVerifyHandler())
	mux.Handle("/api/v1/auth/password-reset/confirm/", authApp.PasswordResetConfirmHandler())
	mux.Handle("/api/v1/auth/password-reset/resend/", authApp.PasswordResetResendHandler(mailer))
	mux.Handle("/api/v1/auth/login/", authApp.LoginHandler())
	mux.Handle("/api/v1/auth/token/refresh/", authApp.TokenRefreshHandler())
	mux.Handle("/api/v1/auth/logout/", authApp.LogoutHandler())
	mux.Handle("/api/v1/auth/change-password/", authApp.ChangePasswordHandler())
	mux.Handle("/api/v1/auth/profile/", authApp.ProfileHandler())

	classesApp := classes.App{
		Repository: classes.Repository{DB: db},
		Auth:       tokens,
		MediaBase:  cfg.MediaPublicBaseURL,
	}
	mux.Handle("/api/v1/classes/", classesApp.PathHandler())

	uploadsApp := uploads.App{
		Repository: uploads.Repository{DB: db},
		Auth:       tokens,
		Cache:      redisClient,
		Storage:    objectStorage,
		MediaBase:  cfg.MediaPublicBaseURL,
	}
	mux.Handle("/api/v1/uploads/", authentication.RequireAuth(tokens, uploadsApp.PathHandler()))

	sharingApp := sharing.App{
		Repository: sharing.Repository{DB: db},
		Auth:       tokens,
		Storage:    objectStorage,
		MediaBase:  cfg.MediaPublicBaseURL,
	}
	mux.Handle("/api/v1/sharing/", authentication.RequireAuth(tokens, sharingApp.PathHandler()))

	notificationsApp := notifications.App{
		Repository: notifications.Repository{DB: db},
		Auth:       tokens,
		Cache:      redisClient,
	}
	mux.Handle("/api/v1/notifications/", notificationsApp.PathHandler())

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

func requestTimeoutMiddleware(next http.Handler, timeout time.Duration) http.Handler {
	return http.TimeoutHandler(next, timeout, `{"success":false,"message":"request timed out","data":null,"errors":null}`)
}
