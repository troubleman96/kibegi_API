package cache

import (
	"context"
	"encoding/json"
	"errors"
	"time"

	"github.com/redis/go-redis/v9"
)

var ErrNotConfigured = errors.New("redis is not configured")

// Redis provides a shared, pooled Redis client for cache, rate-limit, lock, and
// future background-job coordination. Redis is an accelerator and coordination
// layer; PostgreSQL remains the source of truth for durable application data.
type Redis struct {
	client     *redis.Client
	defaultTTL time.Duration
}

func NewRedis(redisURL string, poolSize, minIdleConns int, defaultTTL time.Duration) (*Redis, error) {
	if redisURL == "" {
		return &Redis{defaultTTL: defaultTTL}, nil
	}

	options, err := redis.ParseURL(redisURL)
	if err != nil {
		return nil, err
	}
	if poolSize > 0 {
		options.PoolSize = poolSize
	}
	if minIdleConns >= 0 {
		options.MinIdleConns = minIdleConns
	}
	options.ContextTimeoutEnabled = true

	return &Redis{
		client:     redis.NewClient(options),
		defaultTTL: defaultTTL,
	}, nil
}

func (r *Redis) Configured() bool {
	return r != nil && r.client != nil
}

func (r *Redis) Ping(ctx context.Context) error {
	if !r.Configured() {
		return ErrNotConfigured
	}
	return r.client.Ping(ctx).Err()
}

func (r *Redis) Get(ctx context.Context, key string, destination any) error {
	if !r.Configured() {
		return ErrNotConfigured
	}
	value, err := r.client.Get(ctx, key).Result()
	if err != nil {
		return err
	}
	return json.Unmarshal([]byte(value), destination)
}

func (r *Redis) Set(ctx context.Context, key string, value any, ttl time.Duration) error {
	if !r.Configured() {
		return ErrNotConfigured
	}
	if ttl <= 0 {
		ttl = r.defaultTTL
	}
	encoded, err := json.Marshal(value)
	if err != nil {
		return err
	}
	return r.client.Set(ctx, key, encoded, ttl).Err()
}

func (r *Redis) Delete(ctx context.Context, keys ...string) error {
	if !r.Configured() {
		return ErrNotConfigured
	}
	if len(keys) == 0 {
		return nil
	}
	return r.client.Del(ctx, keys...).Err()
}

// IncrementRateLimit atomically increments a counter and applies the TTL only
// on its first write, which keeps rate-limit windows consistent across nodes.
func (r *Redis) IncrementRateLimit(ctx context.Context, key string, ttl time.Duration) (int64, error) {
	if !r.Configured() {
		return 0, ErrNotConfigured
	}
	count, err := r.client.Incr(ctx, key).Result()
	if err != nil {
		return 0, err
	}
	if count == 1 {
		if ttl <= 0 {
			ttl = r.defaultTTL
		}
		if err := r.client.Expire(ctx, key, ttl).Err(); err != nil {
			return 0, err
		}
	}
	return count, nil
}

func (r *Redis) AcquireLock(ctx context.Context, key, token string, ttl time.Duration) (bool, error) {
	if !r.Configured() {
		return false, ErrNotConfigured
	}
	if ttl <= 0 {
		ttl = r.defaultTTL
	}
	return r.client.SetNX(ctx, key, token, ttl).Result()
}

func (r *Redis) ReleaseLock(ctx context.Context, key, token string) error {
	if !r.Configured() {
		return ErrNotConfigured
	}
	const releaseScript = `
if redis.call("get", KEYS[1]) == ARGV[1] then
	return redis.call("del", KEYS[1])
end
return 0`
	return r.client.Eval(ctx, releaseScript, []string{key}, token).Err()
}

func (r *Redis) Close() error {
	if !r.Configured() {
		return nil
	}
	return r.client.Close()
}
