package schedule

import (
	"context"
	"database/sql"
	"fmt"
	"time"
)

type SMSProvider interface {
	Send(ctx context.Context, phoneNumber, message, senderID string) (string, map[string]any, error)
}

type ReminderDispatcher struct {
	DB       *sql.DB
	Provider SMSProvider
}

type ReminderSummary struct {
	Processed int `json:"processed"`
	Sent      int `json:"sent"`
	Failed    int `json:"failed"`
	Skipped   int `json:"skipped"`
}

type dueReminder struct {
	EventID      int64
	Title        string
	StartAt      time.Time
	CalendarName string
	AccountID    sql.NullInt64
	PhoneNumber  string
	Balance      int
	ProviderName string
	SenderID     string
}

func (d ReminderDispatcher) DispatchDueReminders(ctx context.Context, now time.Time, limit int, dryRun bool) (ReminderSummary, error) {
	if d.DB == nil {
		return ReminderSummary{}, fmt.Errorf("database is not configured")
	}
	if limit <= 0 {
		limit = 100
	}
	rows, err := d.DB.QueryContext(ctx, `
SELECT e.id, e.title, e.start_at, c.name, a.id, a.phone_number, COALESCE(a.balance_credits, 0), COALESCE(a.provider_name, 'sendafrica'), COALESCE(a.sender_id, '')
FROM schedule_scheduleevent e
JOIN schedule_schedulecalendar c ON c.id = e.calendar_id
LEFT JOIN schedule_schedulesmsaccount a ON a.owner_id = c.owner_id
LEFT JOIN schedule_schedulesmsdeliverylog l ON l.event_id = e.id
WHERE e.start_at - (e.reminder_minutes * INTERVAL '1 minute') <= $1
  AND e.start_at >= $1 - INTERVAL '30 minutes'
  AND e.start_at <= $1 + INTERVAL '7 days'
  AND (l.id IS NULL OR l.status NOT IN ('sent', 'pending'))
ORDER BY e.start_at ASC
LIMIT $2`, now, limit)
	if err != nil {
		return ReminderSummary{}, err
	}
	defer rows.Close()
	summary := ReminderSummary{}
	for rows.Next() {
		var reminder dueReminder
		if err := rows.Scan(&reminder.EventID, &reminder.Title, &reminder.StartAt, &reminder.CalendarName, &reminder.AccountID, &reminder.PhoneNumber, &reminder.Balance, &reminder.ProviderName, &reminder.SenderID); err != nil {
			return summary, err
		}
		summary.Processed++
		message := fmt.Sprintf("Kibegi | Schedule reminder: %s | %s", reminder.Title, reminder.StartAt.Local().Format("02 Jan 15:04"))
		if dryRun {
			summary.Skipped++
			continue
		}
		if !reminder.AccountID.Valid || reminder.PhoneNumber == "" {
			if err := d.recordLog(ctx, reminder, "skipped", 0, "No active SMS account or phone number.", "", nil); err != nil {
				return summary, err
			}
			summary.Skipped++
			continue
		}
		if reminder.Balance < 1 {
			if err := d.recordLog(ctx, reminder, "skipped", 0, "Insufficient SMS credits.", "", nil); err != nil {
				return summary, err
			}
			summary.Skipped++
			continue
		}
		if d.Provider == nil {
			if err := d.recordLog(ctx, reminder, "failed", 0, "SMS provider is not configured.", "", nil); err != nil {
				return summary, err
			}
			summary.Failed++
			continue
		}
		messageID, raw, err := d.Provider.Send(ctx, reminder.PhoneNumber, message, reminder.SenderID)
		if err != nil {
			if logErr := d.recordLog(ctx, reminder, "failed", 0, err.Error(), "", nil); logErr != nil {
				return summary, logErr
			}
			summary.Failed++
			continue
		}
		tx, err := d.DB.BeginTx(ctx, nil)
		if err != nil {
			return summary, err
		}
		result, err := tx.ExecContext(ctx, `UPDATE schedule_schedulesmsaccount SET balance_credits = balance_credits - 1, updated_at = NOW() WHERE id = $1 AND balance_credits >= 1`, reminder.AccountID.Int64)
		if err != nil {
			_ = tx.Rollback()
			return summary, err
		}
		affected, _ := result.RowsAffected()
		if affected == 0 {
			_ = tx.Rollback()
			if logErr := d.recordLog(ctx, reminder, "skipped", 0, "Insufficient SMS credits.", "", nil); logErr != nil {
				return summary, logErr
			}
			summary.Skipped++
			continue
		}
		_, err = tx.ExecContext(ctx, `INSERT INTO schedule_schedulesmsdeliverylog (recipient_phone, provider_name, provider_message_id, status, message, credits_used, error_message, provider_response, sent_at, created_at, updated_at, event_id, sms_account_id) VALUES ($1,$2,$3,'sent',$4,1,'',$5,$6,NOW(),NOW(),$7,$8)`, reminder.PhoneNumber, reminder.ProviderName, messageID, message, raw, now, reminder.EventID, reminder.AccountID.Int64)
		if err != nil {
			_ = tx.Rollback()
			return summary, err
		}
		if err := tx.Commit(); err != nil {
			return summary, err
		}
		summary.Sent++
	}
	return summary, rows.Err()
}

func (d ReminderDispatcher) recordLog(ctx context.Context, reminder dueReminder, status string, credits int, errorMessage, messageID string, raw any) error {
	message := fmt.Sprintf("Kibegi | Schedule reminder: %s | %s", reminder.Title, reminder.StartAt.Local().Format("02 Jan 15:04"))
	_, err := d.DB.ExecContext(ctx, `INSERT INTO schedule_schedulesmsdeliverylog (recipient_phone, provider_name, provider_message_id, status, message, credits_used, error_message, provider_response, sent_at, created_at, updated_at, event_id, sms_account_id) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,NOW(),NOW(),$10,$11) ON CONFLICT (event_id) DO UPDATE SET status=EXCLUDED.status, error_message=EXCLUDED.error_message, provider_response=EXCLUDED.provider_response, updated_at=NOW()`, reminder.PhoneNumber, reminder.ProviderName, messageID, status, message, credits, errorMessage, raw, time.Now().UTC(), reminder.EventID, nullableAccount(reminder.AccountID))
	return err
}

func nullableAccount(value sql.NullInt64) any {
	if value.Valid {
		return value.Int64
	}
	return nil
}
