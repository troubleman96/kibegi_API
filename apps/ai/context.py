"""
Build a text snapshot of the user's Kibegi data (classes, schedule/timetable,
assignments, notifications, files) that the AI can read to answer questions
about reminders, timetables, deadlines and more.
"""
import logging
from datetime import timedelta

from django.utils import timezone

logger = logging.getLogger(__name__)

SCHEDULE_LOOKAHEAD_DAYS = 14
MAX_SCHEDULE_EVENTS = 30
MAX_ASSIGNMENTS = 15
MAX_NOTIFICATIONS = 8
MAX_FILES = 12

WEEKDAY_TO_DOW = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}

MONTHS = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
]


def _fmt(dt):
    """Format a datetime in local time as e.g. 'Mon 05 Aug 10:30'."""
    local = timezone.localtime(dt)
    weekday = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][local.weekday()]
    return f"{weekday} {local.day:02d} {MONTHS[local.month - 1]} {local.hour:02d}:{local.minute:02d}"


def _event_occurrences(event, start, end, max_count=40):
    """Yield (start_at, end_at) for occurrences of an event inside [start, end)."""
    if event.recurrence == "none":
        if start <= event.start_at < end:
            yield event.start_at, event.end_at
        return

    duration = event.end_at - event.start_at
    count = 0

    if event.recurrence == "daily":
        cursor = event.start_at
        while cursor < end and count < max_count:
            if cursor >= start:
                count += 1
                yield cursor, cursor + duration
            cursor += timedelta(days=1)
        return

    if event.recurrence == "monthly":
        cursor = event.start_at
        while cursor < end and count < max_count:
            if cursor >= start:
                count += 1
                yield cursor, cursor + duration
            try:
                cursor = cursor.replace(month=cursor.month % 12 + 1)
                if cursor.month == 1:
                    cursor = cursor.replace(year=cursor.year + 1)
            except ValueError:
                cursor = (cursor + timedelta(days=28)).replace(day=1)
        return

    if event.recurrence == "weekly":
        days = event.days or []
        weekdays = []
        for day in days:
            try:
                weekdays.append(WEEKDAY_TO_DOW[day.lower().strip()])
            except (AttributeError, KeyError):
                continue
        if not weekdays:
            return
        base_monday = event.start_at - timedelta(days=event.start_at.weekday())
        week = 0
        while week < 60 and count < max_count:
            monday = base_monday + timedelta(weeks=week)
            for dow in sorted(weekdays):
                candidate = monday + timedelta(
                    days=dow,
                    hours=event.start_at.hour,
                    minutes=event.start_at.minute,
                    seconds=event.start_at.second,
                )
                if candidate >= end:
                    continue
                if candidate >= start:
                    count += 1
                    yield candidate, candidate + duration
            week += 1


def _format_classes(user) -> str:
    from apps.classes.models import Membership

    memberships = list(
        Membership.objects.filter(user=user)
        .select_related("class_obj")
        .order_by("class_obj__name")[:20]
    )
    if not memberships:
        return "• None — the user is not in any classes yet."

    lines = []
    for m in memberships:
        c = m.class_obj
        lines.append(
            f"• {c.name} (code {c.class_code}) — role: {m.role}, members: {c.members.count()}"
        )
    return "\n".join(lines)


def _format_schedule(user) -> str:
    from apps.schedule.models import ScheduleCalendar, ScheduleEvent

    now = timezone.now()
    end = now + timedelta(days=SCHEDULE_LOOKAHEAD_DAYS)

    calendar_ids = list(
        ScheduleCalendar.objects.filter(owner=user).values_list("id", flat=True)
    )
    if not calendar_ids:
        return "• No timetable events set up yet."

    events = list(
        ScheduleEvent.objects.filter(calendar_id__in=calendar_ids)
        .select_related("calendar")
        .order_by("start_at")
    )

    upcoming = []
    for event in events:
        for occ_start, occ_end in _event_occurrences(event, now, end):
            upcoming.append((occ_start, occ_end, event))
            if len(upcoming) >= MAX_SCHEDULE_EVENTS:
                break
        if len(upcoming) >= MAX_SCHEDULE_EVENTS:
            break

    upcoming.sort(key=lambda item: item[0])
    if not upcoming:
        return f"• No events in the next {SCHEDULE_LOOKAHEAD_DAYS} days."

    lines = []
    for occ_start, occ_end, event in upcoming:
        location = f" at {event.location}" if event.location else ""
        description = f" — {event.description}" if event.description else ""
        lines.append(
            f"• {_fmt(occ_start)} → {_fmt(occ_end)} [{event.event_type}] "
            f"{event.title}{location}{description}"
        )
    return "\n".join(lines)


def _format_assignments(user) -> str:
    from apps.assignments.models import Assignment, AssignmentSubmission

    is_lecturer = getattr(user, "user_type", "") == "lecturer"

    if is_lecturer:
        assignments = (
            Assignment.objects.filter(created_by=user, is_active=True)
            .select_related("class_obj")
            .order_by("due_date", "-created_at")[:MAX_ASSIGNMENTS]
        )
        if not assignments:
            return "• No active assignments created."
        lines = []
        for a in assignments:
            due = f" due {_fmt(a.due_date)}" if a.due_date else " no due date"
            lines.append(f"• {a.title} — {a.class_obj.name}{due}, max score {a.max_score}")
        return "\n".join(lines)

    # Student: active assignments across their classes + their submission status
    class_ids = list(user.joined_classes.values_list("id", flat=True))
    if not class_ids:
        return "• None — user is not in any classes."
    assignments = (
        Assignment.objects.filter(class_obj_id__in=class_ids, is_active=True)
        .select_related("class_obj")
        .order_by("due_date", "-created_at")[:MAX_ASSIGNMENTS]
    )
    submissions = {
        s.assignment_id: s
        for s in AssignmentSubmission.objects.filter(
            student=user, assignment_id__in=[a.id for a in assignments]
        )
    }
    if not assignments:
        return "• No active assignments in your classes."
    lines = []
    for a in assignments:
        due = f" due {_fmt(a.due_date)}" if a.due_date else " no due date"
        sub = submissions.get(a.id)
        if sub:
            if sub.status == "submitted":
                state = " submitted"
            elif sub.status == "graded":
                state = f" graded ({sub.score}/{a.max_score})"
            elif sub.status == "returned":
                state = " returned for revision"
            else:
                state = " draft saved (not submitted)"
        else:
            state = " not started"
        lines.append(f"• {a.title} — {a.class_obj.name}{due}{state}")
    return "\n".join(lines)


def _format_notifications(user) -> str:
    from apps.notifications.models import Notification

    notifications = list(
        Notification.objects.filter(user=user, is_read=False)
        .order_by("-created_at")[:MAX_NOTIFICATIONS]
    )
    if not notifications:
        return "• No unread notifications."
    lines = []
    for n in notifications:
        lines.append(f"• [{n.notification_type}] {n.content}")
    return "\n".join(lines)


def _format_files(user) -> str:
    from apps.uploads.models import Upload

    uploads = (
        Upload.objects.filter(class_obj__memberships__user=user, is_deleted=False)
        .select_related("class_obj", "uploader")
        .order_by("-created_at")[:MAX_FILES]
    )
    lines = []
    for u in uploads:
        lines.append(f"• {u.file_name} ({u.file_type}) — in {u.class_obj.name}")
    if not lines:
        return "• No files uploaded in any class yet."
    return "\n".join(lines)


def build_platform_context(user, class_obj=None) -> str:
    """Return a read-only snapshot of the user's platform data for the AI."""
    now = timezone.now()
    today = timezone.localdate()

    sections = [
        "=== YOUR KIBEGI DATA (read this to answer questions about schedules, reminders, assignments, classes) ===",
        f"Today: {today.isoformat()} (current time: {_fmt(now)})",
        "",
        "YOUR CLASSES:",
        _format_classes(user),
        "",
        "TIMETABLE / SCHEDULE (next %d days):" % SCHEDULE_LOOKAHEAD_DAYS,
        _format_schedule(user),
        "",
        "ASSIGNMENTS:",
        _format_assignments(user),
        "",
        "REMINDERS / NOTIFICATIONS:",
        _format_notifications(user),
        "",
        "FILES ACROSS YOUR CLASSES:",
        _format_files(user),
        "",
    ]

    if class_obj is not None:
        sections.insert(
            2,
            "You are currently in the class: %s (code %s).\n"
            "Prioritise answers using this class's materials below."
            % (class_obj.name, class_obj.class_code),
        )

    return "\n".join(sections)
