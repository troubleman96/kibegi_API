package cache

import (
	"context"
	"errors"
	"testing"
	"time"
)

func TestNewRedisWithoutURLIsSafeAndExplicitlyUnconfigured(t *testing.T) {
	client, err := NewRedis("", 20, 5, 5*time.Minute)
	if err != nil {
		t.Fatalf("expected no configuration error, got %v", err)
	}
	if client.Configured() {
		t.Fatal("expected Redis client to be unconfigured")
	}
	if err := client.Ping(context.Background()); !errors.Is(err, ErrNotConfigured) {
		t.Fatalf("expected ErrNotConfigured, got %v", err)
	}
	if err := client.Close(); err != nil {
		t.Fatalf("expected close to be safe, got %v", err)
	}
}

func TestNewRedisRejectsInvalidURL(t *testing.T) {
	if _, err := NewRedis("://not-a-url", 20, 5, time.Minute); err == nil {
		t.Fatal("expected invalid Redis URL to fail")
	}
}
