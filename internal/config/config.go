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
	DBMaxOpenConns      int
	DBMaxIdleConns      int
	DBConnMaxLifetime   time.Duration
	DBConnMaxIdleTime   time.Duration
	RedisURL            string
	RedisPoolSize       int
	RedisMinIdleConns   int
	CacheDefaultTTL     time.Duration
	ShutdownTimeout     time.Duration
	DatabasePingTimeout time.Duration
	RedisPingTimeout    time.Duration
}

// FromEnv loads configuration from environment variables with safe local defaults.
func FromEnv() Config {
	return Config{
		HTTPAddr:            getenv("HTTP_ADDR", ":8080"),
		DatabaseURL:         os.Getenv("DATABASE_URL"),
		DBMaxOpenConns:      getInt("DB_MAX_OPEN_CONNS", 50),
		DBMaxIdleConns:      getInt("DB_MAX_IDLE_CONNS", 25),
		DBConnMaxLifetime:   getDuration("DB_CONN_MAX_LIFETIME", 30*time.Minute),
		DBConnMaxIdleTime:   getDuration("DB_CONN_MAX_IDLE_TIME", 5*time.Minute),
		RedisURL:            os.Getenv("REDIS_URL"),
		RedisPoolSize:       getInt("REDIS_POOL_SIZE", 20),
		RedisMinIdleConns:   getInt("REDIS_MIN_IDLE_CONNS", 5),
		CacheDefaultTTL:     getDuration("CACHE_DEFAULT_TTL", 5*time.Minute),
		ShutdownTimeout:     getDuration("SHUTDOWN_TIMEOUT", 10*time.Second),
		DatabasePingTimeout: getDuration("DATABASE_PING_TIMEOUT", 2*time.Second),
		RedisPingTimeout:    getDuration("REDIS_PING_TIMEOUT", 1*time.Second),
	}
}

func getenv(key, fallback string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return fallback
}

func getInt(key string, fallback int) int {
	value := os.Getenv(key)
	if value == "" {
		return fallback
	}
	parsed, err := strconv.Atoi(value)
	if err != nil || parsed < 0 {
		return fallback
	}
	return parsed
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
