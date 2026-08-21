package schedule

import (
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"strconv"
	"strings"
	"time"

	qrcode "github.com/skip2/go-qrcode"

	"github.com/troubleman96/kibegi_API/internal/apps/authentication"
	"github.com/troubleman96/kibegi_API/internal/platform/httpx"
)

type App struct {
	Repository *Repository
	Auth       *authentication.TokenService
}

func (a App) PrivateHandler() http.Handler {
	return authentication.RequireAuth(a.Auth, http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		userID, ok := authentication.UserIDFromContext(r.Context())
		if !ok {
			httpx.WriteEnvelope(w, http.StatusUnauthorized, false, "Authentication credentials were not provided.", nil, nil)
			return
		}
		rest := strings.Trim(strings.TrimPrefix(r.URL.Path, "/api/v1/schedule/"), "/")
		parts := strings.Split(rest, "/")
		switch {
		case rest == "calendars":
			a.calendars(w, r, userID)
		case rest == "sms-account":
			a.smsAccount(w, r, userID)
		case len(parts) == 3 && parts[0] == "calendars" && parts[2] == "events":
			a.events(w, r, userID, parts[1])
		case len(parts) == 3 && parts[0] == "calendars" && parts[2] == "share":
			a.share(w, r, userID, parts[1])
		case len(parts) == 3 && parts[0] == "calendars" && parts[2] == "qr":
			a.qr(w, r, userID, parts[1])
		case len(parts) == 2 && parts[0] == "events":
			a.eventDetail(w, r, userID, parts[1])
		case len(parts) == 2 && parts[0] == "calendars":
			a.calendarDetail(w, r, userID, parts[1])
		default:
			httpx.WriteEnvelope(w, http.StatusNotFound, false, "Not found", nil, nil)
		}
	}))
}

func (a App) calendars(w http.ResponseWriter, r *http.Request, userID int64) {
	if r.Method != http.MethodGet {
		w.Header().Set("Allow", http.MethodGet)
		httpx.WriteEnvelope(w, http.StatusMethodNotAllowed, false, "method not allowed", nil, nil)
		return
	}
	items, err := a.Repository.ListCalendars(r.Context(), userID)
	if err != nil {
		httpx.WriteEnvelope(w, http.StatusServiceUnavailable, false, "Schedule service unavailable", nil, nil)
		return
	}
	httpx.WriteEnvelope(w, http.StatusOK, true, "Schedule calendars retrieved successfully", items, nil)
}

func (a App) calendarDetail(w http.ResponseWriter, r *http.Request, userID int64, rawID string) {
	id, err := strconv.ParseInt(rawID, 10, 64)
	if err != nil {
		httpx.WriteEnvelope(w, http.StatusNotFound, false, "Schedule calendar not found", nil, nil)
		return
	}
	calendar, err := a.Repository.FindOwnedCalendar(r.Context(), userID, id)
	if err != nil {
		httpx.WriteEnvelope(w, http.StatusNotFound, false, "Schedule calendar not found", nil, nil)
		return
	}
	switch r.Method {
	case http.MethodGet:
		events, err := a.Repository.ListEvents(r.Context(), id)
		if err != nil {
			httpx.WriteEnvelope(w, http.StatusServiceUnavailable, false, "Schedule service unavailable", nil, nil)
			return
		}
		httpx.WriteEnvelope(w, http.StatusOK, true, "Schedule calendar retrieved successfully", map[string]any{"id": calendar.ID, "name": calendar.Name, "calendar_type": calendar.CalendarType, "description": calendar.Description, "is_public_sync": calendar.IsPublicSync, "calendar_code": calendar.CalendarCode, "event_count": calendar.EventCount, "created_at": calendar.CreatedAt, "updated_at": calendar.UpdatedAt, "events": events}, nil)
	case http.MethodPatch, http.MethodPut:
		var input struct {
			Name         *string `json:"name"`
			Description  *string `json:"description"`
			IsPublicSync *bool   `json:"is_public_sync"`
		}
		if err := json.NewDecoder(r.Body).Decode(&input); err != nil {
			httpx.WriteEnvelope(w, http.StatusBadRequest, false, "Invalid input", nil, nil)
			return
		}
		if input.Name != nil {
			_, err = a.Repository.DB.ExecContext(r.Context(), `UPDATE schedule_schedulecalendar SET name=$3, updated_at=NOW() WHERE id=$1 AND owner_id=$2`, id, userID, *input.Name)
		}
		if err == nil && input.Description != nil {
			_, err = a.Repository.DB.ExecContext(r.Context(), `UPDATE schedule_schedulecalendar SET description=$3, updated_at=NOW() WHERE id=$1 AND owner_id=$2`, id, userID, *input.Description)
		}
		if err == nil && input.IsPublicSync != nil {
			_, err = a.Repository.DB.ExecContext(r.Context(), `UPDATE schedule_schedulecalendar SET is_public_sync=$3, updated_at=NOW() WHERE id=$1 AND owner_id=$2`, id, userID, *input.IsPublicSync)
		}
		if err != nil {
			httpx.WriteEnvelope(w, http.StatusServiceUnavailable, false, "Schedule service unavailable", nil, nil)
			return
		}
		httpx.WriteEnvelope(w, http.StatusOK, true, "Schedule calendar updated successfully", calendar, nil)
	default:
		httpx.WriteEnvelope(w, http.StatusMethodNotAllowed, false, "method not allowed", nil, nil)
	}
}

func (a App) events(w http.ResponseWriter, r *http.Request, userID int64, rawID string) {
	calendarID, err := strconv.ParseInt(rawID, 10, 64)
	if err != nil {
		httpx.WriteEnvelope(w, http.StatusNotFound, false, "Schedule calendar not found", nil, nil)
		return
	}
	if _, err := a.Repository.FindOwnedCalendar(r.Context(), userID, calendarID); err != nil {
		httpx.WriteEnvelope(w, http.StatusNotFound, false, "Schedule calendar not found", nil, nil)
		return
	}
	if r.Method == http.MethodGet {
		items, err := a.Repository.ListEvents(r.Context(), calendarID)
		if err != nil {
			httpx.WriteEnvelope(w, http.StatusServiceUnavailable, false, "Schedule service unavailable", nil, nil)
			return
		}
		httpx.WriteEnvelope(w, http.StatusOK, true, "Schedule events retrieved successfully", items, nil)
		return
	}
	if r.Method != http.MethodPost {
		httpx.WriteEnvelope(w, http.StatusMethodNotAllowed, false, "method not allowed", nil, nil)
		return
	}
	input, err := decodeEvent(r, calendarID)
	if err != nil {
		httpx.WriteEnvelope(w, http.StatusBadRequest, false, err.Error(), nil, nil)
		return
	}
	item, err := a.Repository.CreateEvent(r.Context(), calendarID, input)
	if err != nil {
		httpx.WriteEnvelope(w, http.StatusBadRequest, false, err.Error(), nil, nil)
		return
	}
	httpx.WriteEnvelope(w, http.StatusCreated, true, "Schedule event created successfully", item, nil)
}

func (a App) eventDetail(w http.ResponseWriter, r *http.Request, userID int64, rawID string) {
	id, err := strconv.ParseInt(rawID, 10, 64)
	if err != nil {
		httpx.WriteEnvelope(w, http.StatusNotFound, false, "Schedule event not found", nil, nil)
		return
	}
	item, err := a.Repository.FindOwnedEvent(r.Context(), userID, id)
	if err != nil {
		httpx.WriteEnvelope(w, http.StatusNotFound, false, "Schedule event not found", nil, nil)
		return
	}
	switch r.Method {
	case http.MethodGet:
		httpx.WriteEnvelope(w, http.StatusOK, true, "Schedule event retrieved successfully", item, nil)
	case http.MethodDelete:
		if err := a.Repository.DeleteEvent(r.Context(), userID, id); err != nil {
			httpx.WriteEnvelope(w, http.StatusServiceUnavailable, false, "Schedule service unavailable", nil, nil)
			return
		}
		httpx.WriteEnvelope(w, http.StatusOK, true, "Schedule event deleted successfully", nil, nil)
	case http.MethodPatch, http.MethodPut:
		input, err := decodeEvent(r, item.CalendarID)
		if err != nil {
			httpx.WriteEnvelope(w, http.StatusBadRequest, false, err.Error(), nil, nil)
			return
		}
		updated, err := a.Repository.UpdateEvent(r.Context(), userID, id, input)
		if err != nil {
			httpx.WriteEnvelope(w, http.StatusBadRequest, false, err.Error(), nil, nil)
			return
		}
		httpx.WriteEnvelope(w, http.StatusOK, true, "Schedule event updated successfully", updated, nil)
	default:
		httpx.WriteEnvelope(w, http.StatusMethodNotAllowed, false, "method not allowed", nil, nil)
	}
}

func (a App) share(w http.ResponseWriter, r *http.Request, userID int64, rawID string) {
	if r.Method != http.MethodGet {
		httpx.WriteEnvelope(w, http.StatusMethodNotAllowed, false, "method not allowed", nil, nil)
		return
	}
	id, err := strconv.ParseInt(rawID, 10, 64)
	if err != nil {
		httpx.WriteEnvelope(w, http.StatusNotFound, false, "Schedule calendar not found", nil, nil)
		return
	}
	calendar, err := a.Repository.FindOwnedCalendar(r.Context(), userID, id)
	if err != nil {
		httpx.WriteEnvelope(w, http.StatusNotFound, false, "Schedule calendar not found", nil, nil)
		return
	}
	httpx.WriteEnvelope(w, http.StatusOK, true, "Schedule share information retrieved successfully", a.sharePayload(r, calendar), nil)
}

func (a App) qr(w http.ResponseWriter, r *http.Request, userID int64, rawID string) {
	id, err := strconv.ParseInt(rawID, 10, 64)
	if err != nil {
		httpx.WriteEnvelope(w, http.StatusNotFound, false, "Schedule calendar not found", nil, nil)
		return
	}
	calendar, err := a.Repository.FindOwnedCalendar(r.Context(), userID, id)
	if err != nil {
		httpx.WriteEnvelope(w, http.StatusNotFound, false, "Schedule calendar not found", nil, nil)
		return
	}
	image, err := qrcode.Encode(a.sharePayload(r, calendar)["subscription_page_url"].(string), qrcode.Medium, 256)
	if err != nil {
		httpx.WriteEnvelope(w, http.StatusServiceUnavailable, false, "Schedule QR unavailable", nil, nil)
		return
	}
	w.Header().Set("Content-Type", "image/png")
	_, _ = w.Write(image)
}

func (a App) smsAccount(w http.ResponseWriter, r *http.Request, userID int64) {
	account, err := a.Repository.GetSMSAccount(r.Context(), userID)
	if err != nil {
		httpx.WriteEnvelope(w, http.StatusServiceUnavailable, false, "Schedule SMS account unavailable", nil, nil)
		return
	}
	if r.Method == http.MethodPatch || r.Method == http.MethodPut {
		var input struct {
			PhoneNumber string `json:"phone_number"`
		}
		if err := json.NewDecoder(r.Body).Decode(&input); err != nil {
			httpx.WriteEnvelope(w, http.StatusBadRequest, false, "Invalid input", nil, nil)
			return
		}
		account, err = a.Repository.UpdateSMSAccount(r.Context(), userID, strings.TrimSpace(input.PhoneNumber))
		if err != nil {
			httpx.WriteEnvelope(w, http.StatusServiceUnavailable, false, "Schedule SMS account unavailable", nil, nil)
			return
		}
	} else if r.Method != http.MethodGet {
		httpx.WriteEnvelope(w, http.StatusMethodNotAllowed, false, "method not allowed", nil, nil)
		return
	}
	httpx.WriteEnvelope(w, http.StatusOK, true, "Schedule SMS account retrieved successfully", account, nil)
}

func (a App) PublicHandler() http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		rest := strings.Trim(strings.TrimPrefix(r.URL.Path, "/api/v1/public/schedule/"), "/")
		parts := strings.Split(rest, "/")
		if len(parts) >= 3 && parts[0] == "code" && parts[2] == "info" {
			a.publicInfo(w, r, "", parts[1])
			return
		}
		if len(parts) < 2 {
			httpx.WriteEnvelope(w, http.StatusNotFound, false, "Schedule calendar not found", nil, nil)
			return
		}
		token := parts[0]
		switch parts[1] {
		case "info":
			a.publicInfo(w, r, token, "")
		case "subscribe":
			a.publicICS(w, r, token, false)
		case "download":
			a.publicICS(w, r, token, true)
		default:
			httpx.WriteEnvelope(w, http.StatusNotFound, false, "Schedule calendar not found", nil, nil)
		}
	})
}

func (a App) publicInfo(w http.ResponseWriter, r *http.Request, token, code string) {
	calendar, err := a.Repository.FindPublicCalendar(r.Context(), token, code)
	if err != nil {
		httpx.WriteEnvelope(w, http.StatusNotFound, false, "Schedule calendar not found", nil, nil)
		return
	}
	a.Repository.RecordAccess(r.Context(), calendar.ID, "info", r.RemoteAddr, r.UserAgent())
	events, err := a.Repository.ListEvents(r.Context(), calendar.ID)
	if err != nil {
		httpx.WriteEnvelope(w, http.StatusServiceUnavailable, false, "Schedule service unavailable", nil, nil)
		return
	}
	payload := a.sharePayload(r, calendar)
	payload["description"] = calendar.Description
	payload["event_count"] = len(events)
	httpx.WriteEnvelope(w, http.StatusOK, true, "Public schedule information retrieved successfully", payload, nil)
}

func (a App) publicICS(w http.ResponseWriter, r *http.Request, token string, attachment bool) {
	calendar, err := a.Repository.FindPublicCalendar(r.Context(), token, "")
	if err != nil {
		httpx.WriteEnvelope(w, http.StatusNotFound, false, "Schedule calendar not found", nil, nil)
		return
	}
	a.Repository.RecordAccess(r.Context(), calendar.ID, map[bool]string{true: "download", false: "subscribe"}[attachment], r.RemoteAddr, r.UserAgent())
	events, err := a.Repository.ListEvents(r.Context(), calendar.ID)
	if err != nil {
		httpx.WriteEnvelope(w, http.StatusServiceUnavailable, false, "Schedule service unavailable", nil, nil)
		return
	}
	w.Header().Set("Content-Type", "text/calendar; charset=utf-8")
	disposition := "inline"
	if attachment {
		disposition = "attachment"
	}
	w.Header().Set("Content-Disposition", disposition+`; filename="`+calendar.CalendarType+"-"+calendar.CalendarCode+`.ics"`)
	_, _ = w.Write([]byte(generateICS(calendar, events)))
}

func (a App) sharePayload(r *http.Request, calendar Calendar) map[string]any {
	base := requestBase(r)
	info := base + "/api/v1/public/schedule/" + calendar.ShareToken + "/info/"
	subscribe := base + "/api/v1/public/schedule/" + calendar.ShareToken + "/subscribe/"
	download := base + "/api/v1/public/schedule/" + calendar.ShareToken + "/download/"
	webcal := subscribe
	if strings.HasPrefix(webcal, "https://") {
		webcal = "webcal://" + strings.TrimPrefix(webcal, "https://")
	} else if strings.HasPrefix(webcal, "http://") {
		webcal = "webcal://" + strings.TrimPrefix(webcal, "http://")
	}
	return map[string]any{"calendar_id": strconv.FormatInt(calendar.ID, 10), "calendar_type": calendar.CalendarType, "calendar_code": calendar.CalendarCode, "subscribe_url": subscribe, "download_url": download, "webcal_url": webcal, "subscription_page_url": info, "frontend_subscription_url": nil, "code_lookup_url": base + "/api/v1/public/schedule/code/" + calendar.CalendarCode + "/info/"}
}

func decodeEvent(r *http.Request, calendarID int64) (Event, error) {
	var raw struct {
		Title           string  `json:"title"`
		Description     *string `json:"description"`
		Location        *string `json:"location"`
		StartAt         string  `json:"start_at"`
		EndAt           string  `json:"end_at"`
		EventType       string  `json:"event_type"`
		Recurrence      string  `json:"recurrence"`
		Days            any     `json:"days"`
		ReminderMinutes int     `json:"reminder_minutes"`
	}
	if err := json.NewDecoder(r.Body).Decode(&raw); err != nil {
		return Event{}, errors.New("Invalid event input")
	}
	start, err := time.Parse(time.RFC3339, raw.StartAt)
	if err != nil {
		return Event{}, errors.New("Invalid start_at")
	}
	end, err := time.Parse(time.RFC3339, raw.EndAt)
	if err != nil {
		return Event{}, errors.New("Invalid end_at")
	}
	if raw.EventType == "" {
		raw.EventType = "other"
	}
	if raw.Recurrence == "" {
		raw.Recurrence = "none"
	}
	if raw.ReminderMinutes == 0 {
		raw.ReminderMinutes = 15
	}
	return Event{CalendarID: calendarID, Title: raw.Title, Description: raw.Description, Location: raw.Location, StartAt: start, EndAt: end, EventType: raw.EventType, Recurrence: raw.Recurrence, Days: raw.Days, ReminderMinutes: raw.ReminderMinutes}, nil
}

func generateICS(calendar Calendar, events []Event) string {
	var b strings.Builder
	b.WriteString("BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//Kibegi//Schedule//EN\r\nX-WR-CALNAME:" + icsEscape(calendar.Name) + "\r\nX-PUBLISHED-TTL:PT15M\r\n")
	for _, event := range events {
		b.WriteString("BEGIN:VEVENT\r\nUID:" + eventUID(event) + "\r\nDTSTAMP:" + event.CreatedAt.UTC().Format("20060102T150405Z") + "\r\nDTSTART:" + event.StartAt.UTC().Format("20060102T150405Z") + "\r\nDTEND:" + event.EndAt.UTC().Format("20060102T150405Z") + "\r\nSUMMARY:" + icsEscape(event.Title) + "\r\n")
		if event.Description != nil {
			b.WriteString("DESCRIPTION:" + icsEscape(*event.Description) + "\r\n")
		}
		if event.Location != nil {
			b.WriteString("LOCATION:" + icsEscape(*event.Location) + "\r\n")
		}
		switch event.Recurrence {
		case "daily":
			b.WriteString("RRULE:FREQ=DAILY\r\n")
		case "weekly":
			b.WriteString("RRULE:FREQ=WEEKLY\r\n")
		case "monthly":
			b.WriteString("RRULE:FREQ=MONTHLY\r\n")
		}
		b.WriteString(fmt.Sprintf("BEGIN:VALARM\r\nACTION:DISPLAY\r\nDESCRIPTION:Reminder\r\nTRIGGER:-PT%dM\r\nEND:VALARM\r\nEND:VEVENT\r\n", event.ReminderMinutes))
	}
	b.WriteString("END:VCALENDAR\r\n")
	return b.String()
}

func icsEscape(value string) string {
	value = strings.ReplaceAll(value, "\\", "\\\\")
	value = strings.ReplaceAll(value, ";", "\\;")
	value = strings.ReplaceAll(value, ",", "\\,")
	return strings.ReplaceAll(value, "\n", "\\n")
}
func requestBase(r *http.Request) string {
	scheme := "http"
	if r.TLS != nil {
		scheme = "https"
	}
	return scheme + "://" + r.Host
}
