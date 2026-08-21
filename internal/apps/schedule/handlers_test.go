package schedule

import (
	"net/http/httptest"
	"strings"
	"testing"
	"time"
)

func TestGenerateICSPreservesScheduleContract(t *testing.T) {
	start := time.Date(2026, 8, 21, 8, 0, 0, 0, time.UTC)
	end := start.Add(time.Hour)
	calendar := Calendar{Name: "Classes Schedule", CalendarType: "classes", CalendarCode: "ABC123"}
	event := Event{ID: 7, Title: "Algorithms", StartAt: start, EndAt: end, Recurrence: "weekly", ReminderMinutes: 15, CreatedAt: start}
	ics := generateICS(calendar, []Event{event})
	for _, expected := range []string{"PRODID:-//Kibegi//Schedule//EN", "X-WR-CALNAME:Classes Schedule", "UID:schedule-event-7@kibegi", "RRULE:FREQ=WEEKLY", "TRIGGER:-PT15M", "END:VCALENDAR"} {
		if !strings.Contains(ics, expected) {
			t.Fatalf("ICS output missing %q: %s", expected, ics)
		}
	}
}

func TestSharePayloadUsesPublicScheduleRoutes(t *testing.T) {
	request := httptest.NewRequest("GET", "https://api.kibegi.test/api/v1/schedule/calendars/1/share/", nil)
	app := App{}
	payload := app.sharePayload(request, Calendar{ID: 1, CalendarType: "classes", CalendarCode: "ABC123", ShareToken: "token-value"})
	if payload["subscribe_url"] != "https://api.kibegi.test/api/v1/public/schedule/token-value/subscribe/" {
		t.Fatalf("unexpected subscribe URL: %v", payload["subscribe_url"])
	}
	if payload["webcal_url"] != "webcal://api.kibegi.test/api/v1/public/schedule/token-value/subscribe/" {
		t.Fatalf("unexpected webcal URL: %v", payload["webcal_url"])
	}
}
