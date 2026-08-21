package authentication

import (
	"crypto/sha256"
	"encoding/base64"
	"fmt"
	"testing"
	"time"

	"golang.org/x/crypto/pbkdf2"
)

func TestVerifyDjangoPassword(t *testing.T) {
	iterations := 260000
	salt := "abc123"
	digest := pbkdf2.Key([]byte("test123"), []byte(salt), iterations, sha256.Size, sha256.New)
	encoded := fmt.Sprintf("pbkdf2_sha256$%d$%s$%s", iterations, salt, base64.StdEncoding.EncodeToString(digest))
	valid, err := VerifyDjangoPassword(encoded, "test123")
	if err != nil {
		t.Fatalf("expected hash verification to succeed, got %v", err)
	}
	if !valid {
		t.Fatal("expected valid Django password hash")
	}
	wrongPassword, err := VerifyDjangoPassword(encoded, "wrong-password")
	if err != nil {
		t.Fatalf("expected wrong password comparison to succeed, got %v", err)
	}
	if wrongPassword {
		t.Fatal("expected wrong password to be rejected")
	}

	if _, err := VerifyDjangoPassword("argon2$invalid", "test123"); err == nil {
		t.Fatal("expected unsupported algorithm to fail")
	}
}

func TestTokenServiceIssuesAndParsesDjangoCompatibleClaims(t *testing.T) {
	now := time.Date(2026, time.August, 21, 12, 0, 0, 0, time.UTC)
	service := NewTokenService("test-secret", time.Hour, 7*24*time.Hour)
	refresh, access, err := service.IssuePair(42, now)
	if err != nil {
		t.Fatalf("issue token pair: %v", err)
	}
	if refresh == "" || access == "" {
		t.Fatal("expected both tokens")
	}
	userID, err := service.ParseAccess(access)
	if err != nil {
		t.Fatalf("parse access token: %v", err)
	}
	if userID != 42 {
		t.Fatalf("expected user ID 42, got %d", userID)
	}
	if _, err := service.ParseAccess(refresh); err == nil {
		t.Fatal("expected refresh token to be rejected by access parser")
	}
}

func TestTokenServiceRequiresSecret(t *testing.T) {
	service := NewTokenService("", time.Hour, 24*time.Hour)
	if _, _, err := service.IssuePair(1, time.Now()); err == nil {
		t.Fatal("expected missing secret to fail token issuance")
	}
}
