package email

import (
	"crypto/tls"
	"errors"
	"fmt"
	"net/smtp"
	"strconv"
)

var ErrNotConfigured = errors.New("email is not configured")

type Config struct {
	Host     string
	Port     int
	Username string
	Password string
	From     string
	UseTLS   bool
}

type Sender struct {
	cfg Config
}

func NewSender(cfg Config) *Sender {
	return &Sender{cfg: cfg}
}

func (s *Sender) Configured() bool {
	return s != nil && s.cfg.Host != "" && s.cfg.Port > 0 && s.cfg.From != ""
}

func (s *Sender) SendOTP(to, subject, body string) error {
	if !s.Configured() {
		return ErrNotConfigured
	}
	address := s.cfg.Host + ":" + strconv.Itoa(s.cfg.Port)
	message := []byte("From: " + s.cfg.From + "\r\n" +
		"To: " + to + "\r\n" +
		"Subject: " + subject + "\r\n" +
		"MIME-Version: 1.0\r\n" +
		"Content-Type: text/plain; charset=UTF-8\r\n\r\n" + body + "\r\n")
	var auth smtp.Auth
	if s.cfg.Username != "" {
		auth = smtp.PlainAuth("", s.cfg.Username, s.cfg.Password, s.cfg.Host)
	}
	if !s.cfg.UseTLS {
		return smtp.SendMail(address, auth, s.cfg.From, []string{to}, message)
	}

	connection, err := tls.Dial("tcp", address, &tls.Config{ServerName: s.cfg.Host, MinVersion: tls.VersionTLS12})
	if err != nil {
		return err
	}
	client, err := smtp.NewClient(connection, s.cfg.Host)
	if err != nil {
		return err
	}
	defer client.Close()
	if auth != nil {
		if err := client.Auth(auth); err != nil {
			return err
		}
	}
	if err := client.Mail(s.cfg.From); err != nil {
		return err
	}
	if err := client.Rcpt(to); err != nil {
		return err
	}
	writer, err := client.Data()
	if err != nil {
		return err
	}
	if _, err := writer.Write(message); err != nil {
		return err
	}
	if err := writer.Close(); err != nil {
		return err
	}
	return client.Quit()
}

func RegistrationMessage(name, code string, expiryMinutes int) (string, string) {
	return "Kibegi email verification", fmt.Sprintf("Hello %s,\n\nYour Kibegi verification code is %s. It expires in %d minutes.\n\nIf you did not start this registration, you can ignore this email.", name, code, expiryMinutes)
}
