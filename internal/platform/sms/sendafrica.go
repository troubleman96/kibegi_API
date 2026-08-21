package sms

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"strconv"
	"strings"
	"time"
)

var ErrNotConfigured = errors.New("SENDAFRICA_API_KEY is not configured")

type Config struct {
	BaseURL  string
	APIKey   string
	SenderID string
	Client   *http.Client
}

type Client struct {
	cfg    Config
	client *http.Client
}

func NewClient(cfg Config) *Client {
	if cfg.BaseURL == "" {
		cfg.BaseURL = "https://api.sendafrica.online"
	}
	if cfg.Client == nil {
		cfg.Client = &http.Client{Timeout: 15 * time.Second}
	}
	return &Client{cfg: cfg, client: cfg.Client}
}

func (c *Client) Configured() bool { return c != nil && c.cfg.APIKey != "" }

type providerResponse struct {
	Success bool `json:"success"`
	Error   struct {
		Code    string `json:"code"`
		Message string `json:"message"`
	} `json:"error"`
	Data struct {
		Balance   int    `json:"balance"`
		MessageID string `json:"message_id"`
	} `json:"data"`
}

func (c *Client) CheckBalance(ctx context.Context) (int, error) {
	if !c.Configured() {
		return 0, ErrNotConfigured
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, c.cfg.BaseURL+"/v1/credits/balance", nil)
	if err != nil {
		return 0, err
	}
	req.Header.Set("X-API-Key", c.cfg.APIKey)
	var response providerResponse
	if err := c.doJSON(req, &response); err != nil {
		return 0, err
	}
	if !response.Success {
		return 0, fmt.Errorf("[%s] %s", response.Error.Code, response.Error.Message)
	}
	return response.Data.Balance, nil
}

func (c *Client) Send(ctx context.Context, phoneNumber, message, senderID string) (string, map[string]any, error) {
	if !c.Configured() {
		return "", nil, ErrNotConfigured
	}
	payload := map[string]string{"to": phoneNumber, "message": message}
	if senderID == "" {
		senderID = c.cfg.SenderID
	}
	if senderID != "" {
		payload["from"] = senderID
	}
	body, err := json.Marshal(payload)
	if err != nil {
		return "", nil, err
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, c.cfg.BaseURL+"/v1/sms/", bytes.NewReader(body))
	if err != nil {
		return "", nil, err
	}
	req.Header.Set("X-API-Key", c.cfg.APIKey)
	req.Header.Set("Content-Type", "application/json")
	var response providerResponse
	if err := c.doJSON(req, &response); err != nil {
		return "", nil, err
	}
	if !response.Success {
		return "", nil, fmt.Errorf("[%s] %s", response.Error.Code, response.Error.Message)
	}
	raw := map[string]any{"success": response.Success, "data": response.Data}
	return response.Data.MessageID, raw, nil
}

func (c *Client) doJSON(req *http.Request, destination any) error {
	response, err := c.client.Do(req)
	if err != nil {
		return err
	}
	defer response.Body.Close()
	body, err := io.ReadAll(response.Body)
	if err != nil {
		return err
	}
	if response.StatusCode < 200 || response.StatusCode >= 300 {
		return fmt.Errorf("SMS provider returned HTTP %s: %s", response.Status, string(body))
	}
	if err := json.Unmarshal(body, destination); err != nil {
		return fmt.Errorf("SMS provider returned invalid JSON: %w", err)
	}
	return nil
}

func FormatMessage(subject, body, venue string) string {
	parts := []string{"Kibegi"}
	if subject != "" {
		parts = append(parts, subject)
	}
	if venue != "" {
		parts = append(parts, "Venue: "+venue)
	}
	if body != "" {
		parts = append(parts, body)
	}
	return strings.Join(parts, " | ")
}

func FormatCredits(value int) string { return strconv.Itoa(value) }
