package schedule

import (
	"context"
	"database/sql"
	"errors"
	"fmt"
	"time"
)

var (
	ErrCalendarNotFound = errors.New("Schedule calendar not found")
	ErrEventNotFound    = errors.New("Schedule event not found")
)

type Calendar struct {
	ID           int64     `json:"id"`
	OwnerID      int64     `json:"-"`
	Name         string    `json:"name"`
	CalendarType string    `json:"calendar_type"`
	Description  *string   `json:"description"`
	IsPublicSync bool      `json:"is_public_sync"`
	ShareToken   string    `json:"-"`
	CalendarCode string    `json:"calendar_code"`
	EventCount   int       `json:"event_count"`
	CreatedAt    time.Time `json:"created_at"`
	UpdatedAt    time.Time `json:"updated_at"`
}

type Event struct {
	ID              int64     `json:"id"`
	CalendarID      int64     `json:"calendar"`
	Title           string    `json:"title"`
	Description     *string   `json:"description"`
	Location        *string   `json:"location"`
	StartAt         time.Time `json:"start_at"`
	EndAt           time.Time `json:"end_at"`
	EventType       string    `json:"event_type"`
	Recurrence      string    `json:"recurrence"`
	Days            any       `json:"days"`
	ReminderMinutes int       `json:"reminder_minutes"`
	Source          string    `json:"source"`
	CreatedAt       time.Time `json:"created_at"`
	UpdatedAt       time.Time `json:"updated_at"`
}

type SMSAccount struct {
	ID                 int64      `json:"id"`
	OwnerID            int64      `json:"-"`
	PhoneNumber        string     `json:"phone_number"`
	BalanceCredits     int        `json:"balance_credits"`
	ProviderName       string     `json:"provider_name"`
	SenderID           string     `json:"sender_id"`
	IsActive           bool       `json:"is_active"`
	LastTopupReference string     `json:"last_topup_reference"`
	LastTopupAt        *time.Time `json:"last_topup_at"`
	CreatedAt          time.Time  `json:"created_at"`
	UpdatedAt          time.Time  `json:"updated_at"`
}

type Repository struct{ DB *sql.DB }

func (r Repository) EnsureDefaults(ctx context.Context, userID int64) error {
	if r.DB == nil {
		return errors.New("database is not configured")
	}
	for _, item := range []struct{ kind, name string }{{"classes", "Classes Schedule"}, {"examination", "Examination Schedule"}} {
		_, err := r.DB.ExecContext(ctx, `
INSERT INTO schedule_schedulecalendar (name, calendar_type, description, is_public_sync, share_token, calendar_code, created_at, updated_at, owner_id)
SELECT $2, $1, '', true, md5(random()::text || clock_timestamp()::text), upper(substr(md5(random()::text || clock_timestamp()::text), 1, 6)), NOW(), NOW(), $3
WHERE NOT EXISTS (SELECT 1 FROM schedule_schedulecalendar WHERE owner_id = $3 AND calendar_type = $1)`, item.kind, item.name, userID)
		if err != nil {
			return err
		}
	}
	return nil
}

func (r Repository) ListCalendars(ctx context.Context, userID int64) ([]Calendar, error) {
	if err := r.EnsureDefaults(ctx, userID); err != nil {
		return nil, err
	}
	rows, err := r.DB.QueryContext(ctx, `SELECT c.id, c.name, c.calendar_type, c.description, c.is_public_sync, c.share_token, c.calendar_code, COUNT(e.id), c.created_at, c.updated_at FROM schedule_schedulecalendar c LEFT JOIN schedule_scheduleevent e ON e.calendar_id = c.id WHERE c.owner_id = $1 GROUP BY c.id ORDER BY c.calendar_type, c.created_at`, userID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	calendars := make([]Calendar, 0)
	for rows.Next() {
		var item Calendar
		if err := rows.Scan(&item.ID, &item.Name, &item.CalendarType, &item.Description, &item.IsPublicSync, &item.ShareToken, &item.CalendarCode, &item.EventCount, &item.CreatedAt, &item.UpdatedAt); err != nil {
			return nil, err
		}
		item.OwnerID = userID
		calendars = append(calendars, item)
	}
	return calendars, rows.Err()
}

func (r Repository) FindOwnedCalendar(ctx context.Context, userID, calendarID int64) (Calendar, error) {
	if err := r.EnsureDefaults(ctx, userID); err != nil {
		return Calendar{}, err
	}
	return r.findCalendar(ctx, `c.id = $1 AND c.owner_id = $2`, calendarID, userID)
}

func (r Repository) FindPublicCalendar(ctx context.Context, token, code string) (Calendar, error) {
	if r.DB == nil {
		return Calendar{}, errors.New("database is not configured")
	}
	if token != "" {
		return r.findCalendar(ctx, `c.share_token = $1 AND c.is_public_sync = true`, token)
	}
	return r.findCalendar(ctx, `upper(c.calendar_code) = upper($1) AND c.is_public_sync = true`, code)
}

func (r Repository) findCalendar(ctx context.Context, condition string, args ...any) (Calendar, error) {
	var item Calendar
	err := r.DB.QueryRowContext(ctx, `SELECT c.id, c.owner_id, c.name, c.calendar_type, c.description, c.is_public_sync, c.share_token, c.calendar_code, COUNT(e.id), c.created_at, c.updated_at FROM schedule_schedulecalendar c LEFT JOIN schedule_scheduleevent e ON e.calendar_id = c.id WHERE `+condition+` GROUP BY c.id`, args...).Scan(&item.ID, &item.OwnerID, &item.Name, &item.CalendarType, &item.Description, &item.IsPublicSync, &item.ShareToken, &item.CalendarCode, &item.EventCount, &item.CreatedAt, &item.UpdatedAt)
	if errors.Is(err, sql.ErrNoRows) {
		return Calendar{}, ErrCalendarNotFound
	}
	return item, err
}

func (r Repository) ListEvents(ctx context.Context, calendarID int64) ([]Event, error) {
	rows, err := r.DB.QueryContext(ctx, `SELECT id, calendar_id, title, description, location, start_at, end_at, event_type, recurrence, days, reminder_minutes, source, created_at, updated_at FROM schedule_scheduleevent WHERE calendar_id = $1 ORDER BY start_at, created_at`, calendarID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	events := make([]Event, 0)
	for rows.Next() {
		var item Event
		if err := rows.Scan(&item.ID, &item.CalendarID, &item.Title, &item.Description, &item.Location, &item.StartAt, &item.EndAt, &item.EventType, &item.Recurrence, &item.Days, &item.ReminderMinutes, &item.Source, &item.CreatedAt, &item.UpdatedAt); err != nil {
			return nil, err
		}
		events = append(events, item)
	}
	return events, rows.Err()
}

func (r Repository) CreateEvent(ctx context.Context, calendarID int64, input Event) (Event, error) {
	if !input.EndAt.After(input.StartAt) {
		return Event{}, errors.New("End time must be after start time.")
	}
	if input.Recurrence == "weekly" && input.Days == nil {
		return Event{}, errors.New("Weekly recurring events must include at least one day.")
	}
	var item Event
	err := r.DB.QueryRowContext(ctx, `INSERT INTO schedule_scheduleevent (title, description, location, start_at, end_at, event_type, recurrence, days, reminder_minutes, source, created_at, updated_at, calendar_id) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,'manual',NOW(),NOW(),$10) RETURNING id, calendar_id, title, description, location, start_at, end_at, event_type, recurrence, days, reminder_minutes, source, created_at, updated_at`, input.Title, input.Description, input.Location, input.StartAt, input.EndAt, input.EventType, input.Recurrence, input.Days, input.ReminderMinutes, calendarID).Scan(&item.ID, &item.CalendarID, &item.Title, &item.Description, &item.Location, &item.StartAt, &item.EndAt, &item.EventType, &item.Recurrence, &item.Days, &item.ReminderMinutes, &item.Source, &item.CreatedAt, &item.UpdatedAt)
	return item, err
}

func (r Repository) FindOwnedEvent(ctx context.Context, userID, eventID int64) (Event, error) {
	var item Event
	err := r.DB.QueryRowContext(ctx, `SELECT e.id, e.calendar_id, e.title, e.description, e.location, e.start_at, e.end_at, e.event_type, e.recurrence, e.days, e.reminder_minutes, e.source, e.created_at, e.updated_at FROM schedule_scheduleevent e JOIN schedule_schedulecalendar c ON c.id = e.calendar_id WHERE e.id = $1 AND c.owner_id = $2`, eventID, userID).Scan(&item.ID, &item.CalendarID, &item.Title, &item.Description, &item.Location, &item.StartAt, &item.EndAt, &item.EventType, &item.Recurrence, &item.Days, &item.ReminderMinutes, &item.Source, &item.CreatedAt, &item.UpdatedAt)
	if errors.Is(err, sql.ErrNoRows) {
		return Event{}, ErrEventNotFound
	}
	return item, err
}

func (r Repository) UpdateEvent(ctx context.Context, userID, eventID int64, input Event) (Event, error) {
	if !input.EndAt.After(input.StartAt) {
		return Event{}, errors.New("End time must be after start time.")
	}
	_, err := r.DB.ExecContext(ctx, `UPDATE schedule_scheduleevent e SET title=$3, description=$4, location=$5, start_at=$6, end_at=$7, event_type=$8, recurrence=$9, days=$10, reminder_minutes=$11, updated_at=NOW() FROM schedule_schedulecalendar c WHERE e.calendar_id=c.id AND e.id=$1 AND c.owner_id=$2`, eventID, userID, input.Title, input.Description, input.Location, input.StartAt, input.EndAt, input.EventType, input.Recurrence, input.Days, input.ReminderMinutes)
	if err != nil {
		return Event{}, err
	}
	return r.FindOwnedEvent(ctx, userID, eventID)
}

func (r Repository) DeleteEvent(ctx context.Context, userID, eventID int64) error {
	result, err := r.DB.ExecContext(ctx, `DELETE FROM schedule_scheduleevent e USING schedule_schedulecalendar c WHERE e.calendar_id=c.id AND e.id=$1 AND c.owner_id=$2`, eventID, userID)
	if err != nil {
		return err
	}
	count, _ := result.RowsAffected()
	if count == 0 {
		return ErrEventNotFound
	}
	return nil
}

func (r Repository) RecordAccess(ctx context.Context, calendarID int64, accessType, ip, userAgent string) {
	if r.DB != nil {
		_, _ = r.DB.ExecContext(ctx, `INSERT INTO schedule_schedulesyncaccesslog (access_type, ip_address, user_agent, accessed_at, calendar_id) VALUES ($1,$2,$3,NOW(),$4)`, accessType, ip, userAgent, calendarID)
	}
}

func (r Repository) GetSMSAccount(ctx context.Context, userID int64) (SMSAccount, error) {
	if r.DB == nil {
		return SMSAccount{}, errors.New("database is not configured")
	}
	var item SMSAccount
	err := r.DB.QueryRowContext(ctx, `INSERT INTO schedule_schedulesmsaccount (phone_number,balance_credits,provider_name,sender_id,is_active,last_topup_reference,last_topup_at,created_at,updated_at,owner_id) VALUES ('',0,'africastalking','',true,'',NULL,NOW(),NOW(),$1) ON CONFLICT (owner_id) DO UPDATE SET owner_id=EXCLUDED.owner_id RETURNING id, owner_id, phone_number, balance_credits, provider_name, sender_id, is_active, last_topup_reference, last_topup_at, created_at, updated_at`, userID).Scan(&item.ID, &item.OwnerID, &item.PhoneNumber, &item.BalanceCredits, &item.ProviderName, &item.SenderID, &item.IsActive, &item.LastTopupReference, &item.LastTopupAt, &item.CreatedAt, &item.UpdatedAt)
	return item, err
}

func (r Repository) UpdateSMSAccount(ctx context.Context, userID int64, phoneNumber string) (SMSAccount, error) {
	if _, err := r.DB.ExecContext(ctx, `UPDATE schedule_schedulesmsaccount SET phone_number=$2, updated_at=NOW() WHERE owner_id=$1`, userID, phoneNumber); err != nil {
		return SMSAccount{}, err
	}
	return r.GetSMSAccount(ctx, userID)
}

func eventUID(event Event) string {
	return fmt.Sprintf("schedule-event-%d@kibegi", event.ID)
}
