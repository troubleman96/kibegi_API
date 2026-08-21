package authentication

import (
	"crypto/rand"
	"crypto/sha256"
	"crypto/subtle"
	"encoding/base64"
	"fmt"
	"strconv"
	"strings"

	"golang.org/x/crypto/pbkdf2"
)

// VerifyDjangoPassword supports Django's default pbkdf2_sha256 format:
// pbkdf2_sha256$iterations$salt$base64_digest.
func VerifyDjangoPassword(encoded, password string) (bool, error) {
	parts := strings.Split(encoded, "$")
	if len(parts) != 4 || parts[0] != "pbkdf2_sha256" {
		return false, fmt.Errorf("unsupported Django password hash algorithm")
	}

	iterations, err := strconv.Atoi(parts[1])
	if err != nil || iterations <= 0 {
		return false, fmt.Errorf("invalid Django password iterations")
	}

	expected, err := decodeBase64(parts[3])
	if err != nil {
		return false, fmt.Errorf("decode Django password hash: %w", err)
	}
	actual := pbkdf2.Key([]byte(password), []byte(parts[2]), iterations, sha256.Size, sha256.New)
	return subtle.ConstantTimeCompare(actual, expected) == 1, nil
}

func EncodeDjangoPassword(password string, iterations int) (string, error) {
	if iterations <= 0 {
		iterations = 870000
	}
	var rawSalt [16]byte
	if _, err := rand.Read(rawSalt[:]); err != nil {
		return "", err
	}
	salt := base64.RawURLEncoding.EncodeToString(rawSalt[:])
	digest := pbkdf2.Key([]byte(password), []byte(salt), iterations, sha256.Size, sha256.New)
	return fmt.Sprintf("pbkdf2_sha256$%d$%s$%s", iterations, salt, base64.StdEncoding.EncodeToString(digest)), nil
}

func decodeBase64(value string) ([]byte, error) {
	if decoded, err := base64.RawStdEncoding.DecodeString(value); err == nil {
		return decoded, nil
	}
	return base64.StdEncoding.DecodeString(value)
}
