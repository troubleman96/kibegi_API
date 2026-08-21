package authentication

import (
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"strconv"
	"time"

	"github.com/golang-jwt/jwt/v5"
)

var ErrJWTNotConfigured = errors.New("JWT secret is not configured")

// TokenService preserves the SimpleJWT access/refresh claim names used by the
// existing Django frontend and API clients.
type TokenService struct {
	secret          []byte
	accessLifetime  time.Duration
	refreshLifetime time.Duration
}

func NewTokenService(secret string, accessLifetime, refreshLifetime time.Duration) *TokenService {
	return &TokenService{
		secret:          []byte(secret),
		accessLifetime:  accessLifetime,
		refreshLifetime: refreshLifetime,
	}
}

func (s *TokenService) IssuePair(userID int64, now time.Time) (refresh, access string, err error) {
	if len(s.secret) == 0 {
		return "", "", ErrJWTNotConfigured
	}
	if s.accessLifetime <= 0 {
		s.accessLifetime = time.Hour
	}
	if s.refreshLifetime <= 0 {
		s.refreshLifetime = 7 * 24 * time.Hour
	}

	refresh, err = s.issue(userID, "refresh", now, s.refreshLifetime)
	if err != nil {
		return "", "", err
	}
	access, err = s.issue(userID, "access", now, s.accessLifetime)
	if err != nil {
		return "", "", err
	}
	return refresh, access, nil
}

func (s *TokenService) issue(userID int64, tokenType string, now time.Time, lifetime time.Duration) (string, error) {
	claims := jwt.MapClaims{
		"token_type": tokenType,
		"exp":        now.Add(lifetime).Unix(),
		"iat":        now.Unix(),
		"jti":        newJTI(),
		"user_id":    userID,
	}
	return jwt.NewWithClaims(jwt.SigningMethodHS256, claims).SignedString(s.secret)
}

func (s *TokenService) ParseAccess(tokenString string) (int64, error) {
	if len(s.secret) == 0 {
		return 0, ErrJWTNotConfigured
	}
	parsed, err := jwt.Parse(tokenString, func(token *jwt.Token) (any, error) {
		if token.Method != jwt.SigningMethodHS256 {
			return nil, fmt.Errorf("unexpected JWT signing method: %s", token.Method.Alg())
		}
		return s.secret, nil
	}, jwt.WithValidMethods([]string{jwt.SigningMethodHS256.Alg()}))
	if err != nil || !parsed.Valid {
		if err == nil {
			err = errors.New("invalid JWT")
		}
		return 0, err
	}

	claims, ok := parsed.Claims.(jwt.MapClaims)
	if !ok || claims["token_type"] != "access" {
		return 0, errors.New("JWT is not an access token")
	}
	return claimInt64(claims, "user_id")
}

func claimInt64(claims jwt.MapClaims, key string) (int64, error) {
	switch value := claims[key].(type) {
	case float64:
		return int64(value), nil
	case int64:
		return value, nil
	case int:
		return int64(value), nil
	case string:
		parsed, err := strconv.ParseInt(value, 10, 64)
		if err != nil {
			return 0, err
		}
		return parsed, nil
	case json.Number:
		parsed, err := value.Int64()
		if err != nil {
			return 0, err
		}
		return parsed, nil
	default:
		return 0, fmt.Errorf("JWT claim %q is missing or invalid", key)
	}
}

func newJTI() string {
	var raw [16]byte
	if _, err := rand.Read(raw[:]); err != nil {
		return fmt.Sprintf("%d", time.Now().UnixNano())
	}
	return hex.EncodeToString(raw[:])
}
