package database

import "testing"

func TestOpenPostgresWithoutURL(t *testing.T) {
	db, err := OpenPostgres(Config{})
	if err != nil {
		t.Fatalf("expected no error, got %v", err)
	}
	if db != nil {
		t.Fatal("expected nil database when URL is not configured")
	}
}
