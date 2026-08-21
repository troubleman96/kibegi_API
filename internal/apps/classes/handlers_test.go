package classes

import (
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/google/uuid"
)

func TestDetailPayloadPreservesClassQRContract(t *testing.T) {
	request := httptest.NewRequest("GET", "https://api.kibegi.test/api/v1/classes/", nil)
	item := Class{ID: uuid.New(), Name: "Algorithms", ClassCode: "ABC123", CreatorID: 1}
	payload := (App{}).detailPayload(request, item)

	qrPayload, ok := payload["join_qr_payload"].(map[string]any)
	if !ok {
		t.Fatal("expected QR payload object")
	}
	if qrPayload["type"] != "class_join" || qrPayload["class_code"] != "ABC123" || qrPayload["join_endpoint"] != "/api/v1/classes/join/" {
		t.Fatalf("unexpected QR payload: %#v", qrPayload)
	}
	if payload["join_qr_value"] != "ABC123" {
		t.Fatalf("unexpected QR value: %#v", payload["join_qr_value"])
	}
	qrImage, ok := payload["join_qr_image"].(string)
	if !ok || !strings.HasPrefix(qrImage, "data:image/png;base64,") {
		t.Fatalf("expected PNG data URL, got %#v", payload["join_qr_image"])
	}
}
