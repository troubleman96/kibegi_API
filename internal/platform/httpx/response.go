package httpx

import (
	"encoding/json"
	"net/http"
)

// Envelope is the stable Kibegi API response contract. Data and Errors are
// intentionally flexible because endpoints return both objects and arrays.
type Envelope struct {
	Success bool   `json:"success"`
	Message string `json:"message"`
	Data    any    `json:"data"`
	Errors  any    `json:"errors"`
}

func WriteJSON(w http.ResponseWriter, statusCode int, payload any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(statusCode)
	_ = json.NewEncoder(w).Encode(payload)
}

func WriteEnvelope(w http.ResponseWriter, statusCode int, success bool, message string, data, errs any) {
	WriteJSON(w, statusCode, Envelope{
		Success: success,
		Message: message,
		Data:    data,
		Errors:  errs,
	})
}
