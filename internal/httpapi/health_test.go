package httpapi

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"
)

func TestHealthHandlerWithoutDatabaseMatchesLegacyContract(t *testing.T) {
	handler := HealthHandler{
		Now: func() time.Time {
			return time.Date(2026, time.August, 21, 12, 34, 56, 789000000, time.UTC)
		},
	}

	req := httptest.NewRequest(http.MethodGet, "/api/v1/health/", nil)
	res := httptest.NewRecorder()
	handler.ServeHTTP(res, req)

	if res.Code != http.StatusServiceUnavailable {
		t.Fatalf("expected 503, got %d", res.Code)
	}

	var body struct {
		Success bool   `json:"success"`
		Message string `json:"message"`
		Data    struct {
			Status    string `json:"status"`
			Service   string `json:"service"`
			Timestamp string `json:"timestamp"`
			Checks    struct {
				Database struct {
					Status string `json:"status"`
					Error  string `json:"error"`
				} `json:"database"`
			} `json:"checks"`
		} `json:"data"`
	}
	if err := json.NewDecoder(res.Body).Decode(&body); err != nil {
		t.Fatalf("decode response: %v", err)
	}

	if !body.Success {
		t.Fatal("expected legacy success_response envelope to remain true")
	}
	if body.Message != "unhealthy" || body.Data.Status != "error" {
		t.Fatalf("unexpected health status: %+v", body)
	}
	if body.Data.Service != "kibegi_api" {
		t.Fatalf("unexpected service: %q", body.Data.Service)
	}
	if body.Data.Timestamp != "2026-08-21T12:34:56.789Z" {
		t.Fatalf("unexpected timestamp: %q", body.Data.Timestamp)
	}
	if body.Data.Checks.Database.Status != "error" {
		t.Fatalf("unexpected database status: %q", body.Data.Checks.Database.Status)
	}
	if body.Data.Checks.Database.Error != "database is not configured" {
		t.Fatalf("unexpected database error: %q", body.Data.Checks.Database.Error)
	}
}

func TestHealthHandlerRejectsNonGet(t *testing.T) {
	req := httptest.NewRequest(http.MethodPost, "/api/v1/health/", nil)
	res := httptest.NewRecorder()
	(HealthHandler{}).ServeHTTP(res, req)

	if res.Code != http.StatusMethodNotAllowed {
		t.Fatalf("expected 405, got %d", res.Code)
	}
	if got := res.Header().Get("Allow"); got != http.MethodGet {
		t.Fatalf("expected Allow header %q, got %q", http.MethodGet, got)
	}
}
