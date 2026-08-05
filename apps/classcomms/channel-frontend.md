**Overview**

- **Goal:** Describe how to build the Class Communications frontend — the contact manager, wallet display, broadcast composer, delivery log, and public self-registration page.
- **Scope:** All endpoints, request/response shapes, permission rules, UI flows, and edge cases.

---

**What this feature is**

Class Communications lets a lecturer or class representative collect phone contacts for their class, top up SMS credits, and send broadcast messages to all registered contacts. Members (or anyone with the link) can self-register their own phone number via a public page — no login required.

**Who can manage:** Only the class creator, or a member with role `lecturer` or `representative`. All management endpoints return `403` if the caller does not qualify.

---

**Authentication**

All endpoints except the two public registration endpoints require:
```
Authorization: Bearer <access_token>
```

Public endpoints (`/public/<token>/info/` and `/public/<token>/register/`) require no token — the URL token is the only gate.

---

**Endpoints**

**1. Profile — registration settings**

```
GET   /api/v1/class-comms/classes/<class_id>/profile/
PATCH /api/v1/class-comms/classes/<class_id>/profile/
Authorization: Bearer <token>
```

GET response `200 OK`:
```json
{
  "success": true,
  "data": {
    "id": 1,
    "class_obj": "uuid",
    "public_token": "abc123xyz",
    "public_registration_enabled": true,
    "default_sender_name": "KiBEGI",
    "registration_hint": "Register your name and phone number to receive class updates.",
    "created_by": 5,
    "created_at": "2026-01-10T08:00:00Z",
    "updated_at": "2026-05-31T10:00:00Z",
    "registration_urls": {
      "public_token": "abc123xyz",
      "public_info_url": "https://api.kibegi.com/api/v1/public/class-comms/abc123xyz/info/",
      "public_register_url": "https://api.kibegi.com/api/v1/public/class-comms/abc123xyz/register/"
    },
    "contact_count": 42,
    "broadcast_count": 7
  }
}
```

PATCH body (all fields optional):
```json
{
  "public_registration_enabled": false,
  "default_sender_name": "CS101",
  "registration_hint": "Join our class updates list."
}
```

**UI use:** Settings panel — toggle public registration on/off, edit the hint text shown on the public form, copy the registration link, view contact and broadcast counts.

---

**2. Wallet — SMS credits**

```
GET   /api/v1/class-comms/classes/<class_id>/wallet/
PATCH /api/v1/class-comms/classes/<class_id>/wallet/
Authorization: Bearer <token>
```

GET response `200 OK`:
```json
{
  "success": true,
  "data": {
    "id": 3,
    "class_obj": "uuid",
    "balance_credits": 50,
    "provider_name": "africastalking",
    "sender_id": "KiBEGI",
    "is_active": true,
    "last_topup_reference": "TXN-20260530-001",
    "last_topup_at": "2026-05-30T09:15:00Z",
    "created_at": "2026-01-10T08:00:00Z",
    "updated_at": "2026-05-30T09:15:00Z",
    "contact_count": 42,
    "broadcast_count": 7
  }
}
```

PATCH body (fields to update after a top-up):
```json
{
  "balance_credits": 100,
  "last_topup_reference": "TXN-20260531-002",
  "is_active": true
}
```

**UI use:** Wallet card showing current balance and active status. Warn when `balance_credits` is low (e.g. < 10). Show `is_active=false` as a banner — all broadcasts are blocked until reactivated. Top-up is external (manual payment flow); the frontend just patches the new balance + reference.

---

**3. Contacts — list and add**

```
GET  /api/v1/class-comms/classes/<class_id>/contacts/
POST /api/v1/class-comms/classes/<class_id>/contacts/
Authorization: Bearer <token>
```

GET response `200 OK` (paginated):
```json
{
  "success": true,
  "data": {
    "count": 42,
    "next": "/api/v1/class-comms/classes/<id>/contacts/?page=2",
    "previous": null,
    "results": [
      {
        "id": "uuid",
        "class_obj": "uuid",
        "full_name": "Alice Nakato",
        "phone_number": "+256700123456",
        "consent_granted": true,
        "consent_source": "public",
        "notes": "",
        "is_active": true,
        "registered_by": null,
        "created_by": 5,
        "added_by_name": "Dr. Mugisha",
        "verified_at": "2026-04-01T12:00:00Z",
        "created_at": "2026-04-01T12:00:00Z",
        "updated_at": "2026-04-01T12:00:00Z"
      }
    ]
  }
}
```

POST body:
```json
{
  "full_name": "Bob Ssemakula",
  "phone_number": "+256772345678",
  "consent_granted": true,
  "notes": "Transferred from WhatsApp group"
}
```

POST response: `201 Created` (new contact) or `200 OK` (phone number already existed — contact updated).

**`consent_source` values:** `manual` (added by manager), `public` (self-registered), `imported`.

**UI use:** Contacts table with search/filter. "Add contact" form. Import button (for CSV, if implemented later). Badge the source — "Self-registered" vs "Added manually".

---

**4. Contact detail — update and delete**

```
GET    /api/v1/class-comms/contacts/<contact_id>/
PATCH  /api/v1/class-comms/contacts/<contact_id>/
DELETE /api/v1/class-comms/contacts/<contact_id>/
Authorization: Bearer <token>
```

PATCH body (any subset):
```json
{
  "full_name": "Alice Nakato Kizza",
  "consent_granted": false,
  "is_active": false,
  "notes": "Opted out 2026-05-31"
}
```

DELETE response `200 OK`:
```json
{ "success": true, "message": "Contact deleted." }
```

**UI use:** Edit contact drawer/modal. Toggle `consent_granted` (opt-out) and `is_active` (suspend without deleting). Delete with confirm dialog. Contacts with `consent_granted=false` or `is_active=false` are skipped in broadcasts — show a visual indicator.

---

**5. Representatives — promote / demote**

```
POST /api/v1/class-comms/classes/<class_id>/representatives/
Authorization: Bearer <token>
```

Body:
```json
{
  "user_id": "uuid",
  "role": "representative"
}
```

Set `role` to `"student"` to demote back. Response `200 OK`:
```json
{
  "success": true,
  "data": {
    "membership_id": 12,
    "user_id": "uuid",
    "role": "representative"
  }
}
```

**UI use:** Members list with a "Make representative" / "Remove representative" action per row. Only the class creator or existing lecturer can call this.

---

**6. Broadcasts — list and send**

```
GET  /api/v1/class-comms/classes/<class_id>/broadcasts/
POST /api/v1/class-comms/classes/<class_id>/broadcasts/
Authorization: Bearer <token>
```

GET response (paginated):
```json
{
  "success": true,
  "data": {
    "count": 7,
    "results": [
      {
        "id": "uuid",
        "class_obj": "uuid",
        "sender": 5,
        "sender_name": "Dr. Mugisha",
        "subject": "CAT 2 Reminder",
        "message": "CAT 2 is tomorrow at 9am.",
        "venue": "LLT 3",
        "status": "sent",
        "recipient_count": 42,
        "sent_count": 40,
        "failed_count": 1,
        "skipped_count": 1,
        "credits_used": 40,
        "sent_at": "2026-05-30T14:05:00Z",
        "created_at": "2026-05-30T14:04:55Z",
        "delivery_count": 42,
        "delivery_summary": { "sent": 40, "failed": 1, "skipped": 1 },
        "recent_deliveries": []
      }
    ]
  }
}
```

POST body:
```json
{
  "subject": "CAT 2 Reminder",
  "message": "CAT 2 is tomorrow at 9am. Please bring your student ID.",
  "venue": "LLT 3"
}
```

POST response `201 Created` — returned **after** all SMS messages have been attempted (the dispatch is synchronous, not queued):
```json
{
  "success": true,
  "data": {
    "id": "uuid",
    "status": "sent",
    "sent_count": 40,
    "failed_count": 1,
    "skipped_count": 1,
    "credits_used": 40,
    "sent_at": "2026-05-30T14:05:02Z"
  }
}
```

**Status values:**

| Value | Meaning |
|---|---|
| `draft` | Created, not sent yet |
| `sending` | Dispatch in progress |
| `sent` | All contacts received it |
| `partial` | Some sent, some failed or skipped |
| `failed` | Nothing sent (wallet inactive, no contacts, or all failed) |

**The final SMS text** is composed by the backend as:
```
Kibegi class update | {subject} | Venue: {venue} | {message}
```
`subject` and `venue` are omitted if blank.

**UI use:** Broadcast composer form with `subject` (optional), `message` (required), `venue` (optional). Show a credits estimate before sending (`balance_credits` from wallet ÷ contact count). After POST completes, display result summary with sent/failed/skipped counts and status badge. Block "Send" button if `wallet.is_active=false` or `balance_credits < 1`.

**Important:** The POST request blocks until every SMS is attempted. For large contact lists this may take several seconds. Show a loading/spinner state and do not allow double-submit.

---

**7. Broadcast detail**

```
GET /api/v1/class-comms/broadcasts/<broadcast_id>/
Authorization: Bearer <token>
```

Response includes `delivery_summary` and the 5 most recent `recent_deliveries`:
```json
{
  "success": true,
  "data": {
    "id": "uuid",
    "status": "partial",
    "sent_count": 38,
    "failed_count": 2,
    "skipped_count": 2,
    "credits_used": 38,
    "delivery_count": 42,
    "delivery_summary": { "sent": 38, "failed": 2, "skipped": 2 },
    "recent_deliveries": [
      {
        "id": "uuid",
        "recipient_phone": "+256700123456",
        "status": "sent",
        "provider_message_id": "ATXid_abc",
        "credits_used": 1,
        "error_message": "",
        "sent_at": "2026-05-30T14:05:01Z"
      },
      {
        "id": "uuid",
        "recipient_phone": "+256701999999",
        "status": "failed",
        "provider_message_id": "",
        "credits_used": 0,
        "error_message": "Invalid phone number",
        "sent_at": null
      }
    ]
  }
}
```

**Delivery statuses:** `sent`, `failed`, `skipped` (no consent, inactive contact, or insufficient credits at time of send).

**UI use:** Broadcast detail drawer with a delivery breakdown doughnut/bar chart. Show failed numbers so the manager can investigate or re-add corrected contacts.

---

**8. Public registration info (no auth)**

```
GET /api/v1/public/class-comms/<public_token>/info/
```

Response `200 OK`:
```json
{
  "success": true,
  "data": {
    "class_id": "uuid",
    "class_name": "Introduction to Programming",
    "class_code": "CS101",
    "description": "First-year programming course.",
    "registration_hint": "Register your name and phone number to receive class updates.",
    "public_registration_enabled": true,
    "default_sender_name": "KiBEGI",
    "credits_remaining": 50,
    "contacts_registered": 42,
    "registration_urls": {
      "public_token": "abc123xyz",
      "public_info_url": "...",
      "public_register_url": "..."
    }
  }
}
```

Response `403` when `public_registration_enabled=false`:
```json
{ "success": false, "message": "Public registration is disabled for this class." }
```

**UI use:** The public registration landing page. Show class name, description, and `registration_hint`. Hide the form and show a message if `public_registration_enabled=false`.

---

**9. Public register (no auth)**

```
POST /api/v1/public/class-comms/<public_token>/register/
```

Body:
```json
{
  "full_name": "Alice Nakato",
  "phone_number": "+256700123456",
  "consent_granted": true
}
```

Response `201 Created` (new) or `200 OK` (phone already registered — updated):
```json
{
  "success": true,
  "message": "Successfully registered.",
  "data": {
    "id": "uuid",
    "full_name": "Alice Nakato",
    "phone_number": "+256700123456",
    "consent_granted": true,
    "consent_source": "public",
    "verified_at": "2026-05-31T11:00:00Z"
  }
}
```

Response `403` when registration is disabled (same as `/info/`).

**UI use:** Simple form — name, phone, consent checkbox. On success show a confirmation message. On `200 OK` (already registered) tell the user their details were updated. Phone number field should accept international format (`+256...`).

---

**Frontend integration patterns**

- **Registration link sharing:** Read `registration_urls.public_register_url` from the profile endpoint. Show it as a copyable link + QR code so members can scan to register.
- **Credits warning:** If `wallet.balance_credits` < 10, show a warning banner on the broadcast composer. If `wallet.is_active=false`, disable the Send button and show "SMS wallet is inactive — contact an admin."
- **Contact opt-out:** A `PATCH contacts/<id>/` with `{ consent_granted: false }` is the opt-out action. Contacts with no consent appear in the list with a muted style and an "Opted out" badge — they are silently skipped in broadcasts.
- **Broadcast loading state:** The POST to `/broadcasts/` is blocking — it returns only after every SMS is fired. Use a loading overlay and disable all form controls. Set a long timeout (30–60 s) on the HTTP client for this call.
- **Status badge colours:** `sent` → green, `partial` → amber, `failed` → red, `sending` → blue spinner, `draft` → grey.
- **Delivery breakdown:** On the broadcast detail view, break down `delivery_summary` into a small stat row: `40 sent · 1 failed · 1 skipped`. Link "failed" and "skipped" counts to a filtered delivery list.
- **Public page routing:** The public token lives in the URL — route it as `/class-reg/:token` (or similar). On load, call `/info/` first. If `public_registration_enabled=false`, render a "Registration closed" screen without showing the form.

---

**Typical flows**

**Manager sets up the class for SMS:**
1. Open class → Communications tab
2. GET `/profile/` → see current settings and the public link
3. PATCH `/profile/` if hint text needs updating
4. GET `/wallet/` → check balance; PATCH `/wallet/` after a top-up

**Member self-registers:**
1. Scans QR / opens public link → GET `/public/<token>/info/` → landing page loads
2. Fills in name + phone + consent → POST `/public/<token>/register/` → success confirmation

**Lecturer sends a broadcast:**
1. Opens Broadcasts tab → GET `/broadcasts/` → sees history
2. Clicks "New broadcast" → fills subject, message, venue
3. Previews credit cost estimate (contacts × 1 credit)
4. Submits → POST `/broadcasts/` → loading state
5. Response returns → display result summary with status badge and sent/failed/skipped counts
6. Click broadcast row → GET `/broadcasts/<id>/` → delivery detail

---

**Where to look in the code**

- Models: models.py
- Service (dispatch logic): services.py
- Views: views.py
- Authenticated routes: urls.py
- Public routes: public_urls.py
- Serializers: serializers.py
- Main router: urls.py
