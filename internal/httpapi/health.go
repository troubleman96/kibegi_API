package httpapi

import (
	"context"
	"database/sql"
	"encoding/json"
	"net/http"
	"time"
)

// HealthHandler exposes a lightweight uptime and database readiness check.
type HealthHandler struct {
	DB          *sql.DB
	PingTimeout time.Duration
	ServiceName string
	Now         func() time.Time
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
}

type databaseCheck struct {
	Status string `json:"status"`
	Error  any    `json:"error"`
}

func (h HealthHandler) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		w.Header().Set("Allow", http.MethodGet)
		writeJSON(w, http.StatusMethodNotAllowed, map[string]any{
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

	if dbStatus != "ok" {
		statusCode = http.StatusServiceUnavailable
		message = "unhealthy"
	}

	writeJSON(w, statusCode, healthResponse{
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

func writeJSON(w http.ResponseWriter, statusCode int, payload any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(statusCode)
	_ = json.NewEncoder(w).Encode(payload)
}
