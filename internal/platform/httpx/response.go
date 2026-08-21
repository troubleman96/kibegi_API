package httpx

import (
	"encoding/json"
	"net/http"
)

// Envelope is the response contract shared by the existing Django API and the
// Go implementation. Data and Errors are intentionally flexible because the
// legacy API returns both objects and arrays depending on the endpoint.
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
