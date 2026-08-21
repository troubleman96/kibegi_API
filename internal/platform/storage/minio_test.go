package storage

import (
	"context"
	"errors"
	"testing"
)

func TestNewStorageWithoutCredentialsIsSafe(t *testing.T) {
	storage, err := New(Config{Enabled: true, Bucket: "kibegi-uploads"})
	if err != nil {
		t.Fatalf("expected no configuration error, got %v", err)
	}
	if storage.Configured() {
		t.Fatal("expected storage to be unconfigured")
	}
	if _, err := storage.Stat(context.Background(), "missing"); !errors.Is(err, ErrNotConfigured) {
		t.Fatalf("expected ErrNotConfigured, got %v", err)
	}
}
