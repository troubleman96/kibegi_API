package core

import (
	"context"
	"database/sql"
	"net/http"
	"time"

	"github.com/troubleman96/kibegi_API/internal/platform/cache"
	"github.com/troubleman96/kibegi_API/internal/platform/httpx"
)

// HealthHandler exposes a lightweight uptime and database readiness check.
type HealthHandler struct {
	DB           *sql.DB
	Redis        *cache.Redis
	PingTimeout  time.Duration
	RedisTimeout time.Duration
	ServiceName  string
	Now          func() time.Time
}

type healthResponse struct {
	Success bool       `json:"success"`
	Message string     `json:"message"`
	Data    healthData `json:"data"`
	Errors  any        `json:"errors"`
}

type healthData struct {
	Status    string       `json:"status"`
	Service   string       `json:"service"`
	Timestamp string       `json:"timestamp"`
	Checks    healthChecks `json:"checks"`
}

type healthChecks struct {
	Database databaseCheck `json:"database"`
	Redis    *cacheCheck   `json:"redis,omitempty"`
}

type databaseCheck struct {
	Status string `json:"status"`
	Error  any    `json:"error"`
}

type cacheCheck struct {
	Status string `json:"status"`
	Error  any    `json:"error"`
}

func (h HealthHandler) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		w.Header().Set("Allow", http.MethodGet)
		httpx.WriteJSON(w, http.StatusMethodNotAllowed, map[string]any{
			"success": false,
			"message": "method not allowed",
			"data":    nil,
			"errors":  nil,
		})
		return
	}

	now := time.Now
	if h.Now != nil {
		now = h.Now
	}

	serviceName := h.ServiceName
	if serviceName == "" {
		serviceName = "kibegi_api"
	}

	dbStatus := "ok"
	var dbError any
	statusCode := http.StatusOK
	message := "healthy"

	if h.DB == nil {
		dbStatus = "error"
		dbError = "database is not configured"
	} else {
		pingTimeout := h.PingTimeout
		if pingTimeout <= 0 {
			pingTimeout = 2 * time.Second
		}
		ctx, cancel := context.WithTimeout(r.Context(), pingTimeout)
		err := h.DB.PingContext(ctx)
		cancel()
		if err != nil {
			dbStatus = "error"
			dbError = err.Error()
		}
	}

	var redisStatus *cacheCheck
	if h.Redis != nil && h.Redis.Configured() {
		redisTimeout := h.RedisTimeout
		if redisTimeout <= 0 {
			redisTimeout = time.Second
		}
		ctx, cancel := context.WithTimeout(r.Context(), redisTimeout)
		err := h.Redis.Ping(ctx)
		cancel()
		redisStatus = &cacheCheck{Status: "ok"}
		if err != nil {
			redisStatus.Status = "error"
			redisStatus.Error = err.Error()
		}
	}

	if dbStatus != "ok" || (redisStatus != nil && redisStatus.Status != "ok") {
		statusCode = http.StatusServiceUnavailable
		message = "unhealthy"
	}

	httpx.WriteJSON(w, statusCode, healthResponse{
		// The Django implementation uses success_response even for its 503 branch,
		// so this field intentionally remains true for compatibility.
		Success: true,
		Message: message,
		Data: healthData{
			Status:    mapHealthStatus(dbStatus),
			Service:   serviceName,
			Timestamp: now().UTC().Format(time.RFC3339Nano),
			Checks: healthChecks{
				Database: databaseCheck{
					Status: dbStatus,
					Error:  dbError,
				},
				Redis: redisStatus,
			},
		},
		Errors: nil,
	})
}

func mapHealthStatus(databaseStatus string) string {
	if databaseStatus == "ok" {
		return "ok"
	}
	return "error"
}
