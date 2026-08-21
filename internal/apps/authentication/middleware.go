package authentication

import (
	"context"
	"net/http"
	"strings"

	"github.com/troubleman96/kibegi_API/internal/platform/httpx"
)

func RequireAuth(tokens *TokenService, next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		header := strings.TrimSpace(r.Header.Get("Authorization"))
		if len(header) < 7 || !strings.EqualFold(header[:6], "Bearer") || strings.TrimSpace(header[6:]) == "" {
			httpx.WriteEnvelope(w, http.StatusUnauthorized, false, "Authentication credentials were not provided.", nil, nil)
			return
		}
		userID, err := tokens.ParseAccess(strings.TrimSpace(header[6:]))
		if err != nil {
			httpx.WriteEnvelope(w, http.StatusUnauthorized, false, "Given token not valid for any token type", nil, nil)
			return
		}
		ctx := context.WithValue(r.Context(), userIDKey, userID)
		next.ServeHTTP(w, r.WithContext(ctx))
	})
}

func UserIDFromContext(ctx context.Context) (int64, bool) {
	userID, ok := ctx.Value(userIDKey).(int64)
	return userID, ok
}
