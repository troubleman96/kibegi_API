package config

import (
	"os"
	"strconv"
	"time"
)

// Config contains runtime settings for the Go API.
type Config struct {
	HTTPAddr            string
	DatabaseURL         string
	ShutdownTimeout     time.Duration
	DatabasePingTimeout time.Duration
}

// FromEnv loads configuration from environment variables with safe local defaults.
func FromEnv() Config {
	return Config{
		HTTPAddr:            getenv("HTTP_ADDR", ":8080"),
		DatabaseURL:         os.Getenv("DATABASE_URL"),
		ShutdownTimeout:     getDuration("SHUTDOWN_TIMEOUT", 10*time.Second),
		DatabasePingTimeout: getDuration("DATABASE_PING_TIMEOUT", 2*time.Second),
	}
}

func getenv(key, fallback string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return fallback
}

func getDuration(key string, fallback time.Duration) time.Duration {
	value := os.Getenv(key)
	if value == "" {
		return fallback
	}

	if duration, err := time.ParseDuration(value); err == nil {
		return duration
	}

	if seconds, err := strconv.Atoi(value); err == nil {
		return time.Duration(seconds) * time.Second
	}

	return fallback
}
