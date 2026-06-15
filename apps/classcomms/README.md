# Class Communications App

Legacy documentation only.

The project has moved to the standalone [`apps/channel`](../channel/README.md) app for broadcast campaigns.
Keep this page as a historical reference for the old class-linked messaging design.

## What It Used To Do

- stores class-specific SMS contacts
- lets a lecturer or class representative manage the contact list
- exposes a public registration link so students can submit their name and phone number
- keeps a class-specific SMS wallet with credits
- sends bulk SMS announcements through Africa's Talking
- records one delivery log per recipient for audit and troubleshooting
- promotes a class member to representative so they can manage communications

## Why It Existed

The existing `notifications` app is for in-app notifications only. That is not enough for students who may not be online when a venue changes.
This app adds an explicit SMS workflow with consent, credits, and delivery history so the communication channel is controlled and auditable.

## Data Model

### `ClassCommsProfile`

One profile exists per class.

Important fields:

- `class_obj`: the class that owns the communication space
- `public_token`: long token used by the public registration link
- `public_registration_enabled`: turns the public link on or off
- `registration_hint`: short helper text shown to the frontend
- `default_sender_name`: optional label for the frontend

### `ClassCommsWallet`

The wallet belongs to the class, not the individual rep.

Important fields:

- `balance_credits`: remaining SMS credits
- `provider_name`: SMS provider identifier, currently `africastalking`
- `sender_id`: optional sender ID used by the provider
- `is_active`: disables sending without deleting the wallet
- `last_topup_reference`: reference for manual or future payment flow tracking

### `ClassContact`

Represents a person who has opted in to class SMS updates.

Important fields:

- `full_name`
- `phone_number`
- `consent_granted`
- `consent_source`: `manual`, `public`, or `imported`
- `notes`
- `is_active`
- `registered_by` and `created_by` for audit trails

Contacts are unique per class and phone number.

### `ClassBroadcast`

Represents one announcement sent to the class contact list.

Important fields:

- `subject`
- `message`
- `venue`
- `status`: `draft`, `sending`, `sent`, `partial`, or `failed`
- `recipient_count`
- `sent_count`
- `failed_count`
- `skipped_count`
- `credits_used`

### `ClassBroadcastDelivery`

Stores the result for each recipient.

Important fields:

- `recipient_phone`
- `status`: `pending`, `sent`, `failed`, or `skipped`
- `provider_message_id`
- `provider_response`
- `error_message`
- `credits_used`

## Permissions

A user can manage the app for a class if they are:

- the class creator
- a lecturer member
- a representative member

Only those users may:

- manage the wallet
- add or edit contacts
- promote a member to representative
- send broadcasts
- inspect delivery history

## API Endpoints

Base authenticated route: `/api/v1/class-comms/`

### Class Profile

- `GET /api/v1/class-comms/classes/{class_id}/profile/`
- `PATCH /api/v1/class-comms/classes/{class_id}/profile/`

Use this to enable or disable the public registration link and update the helper text shown on the frontend.

### Wallet

- `GET /api/v1/class-comms/classes/{class_id}/wallet/`
- `PATCH /api/v1/class-comms/classes/{class_id}/wallet/`

Use this to inspect and top up the class SMS credits.

### Contacts

- `GET /api/v1/class-comms/classes/{class_id}/contacts/`
- `POST /api/v1/class-comms/classes/{class_id}/contacts/`
- `GET /api/v1/class-comms/contacts/{contact_id}/`
- `PATCH /api/v1/class-comms/contacts/{contact_id}/`
- `DELETE /api/v1/class-comms/contacts/{contact_id}/`

### Broadcasts

- `GET /api/v1/class-comms/classes/{class_id}/broadcasts/`
- `POST /api/v1/class-comms/classes/{class_id}/broadcasts/`
- `GET /api/v1/class-comms/broadcasts/{broadcast_id}/`

Broadcasts were sent immediately when created.
The backend checked the wallet balance before each send and wrote a delivery log for every contact.

### Representative Management

- `POST /api/v1/class-comms/classes/{class_id}/representatives/`

This updates a class membership role to `representative` or back to `student`.
It is intended for the class creator or lecturer to assign the active rep.

## Public Registration Flow

Public base route: `/api/v1/public/class-comms/`

- `GET /api/v1/public/class-comms/{public_token}/info/`
- `POST /api/v1/public/class-comms/{public_token}/register/`

Typical flow:

1. the frontend asks for the public info payload
2. the frontend shows the class name, hint text, and contact form
3. the student submits name and phone number
4. the backend stores or updates the contact and marks consent

The public route is intentionally minimal so the registration page can be shared by QR code, WhatsApp, SMS, or email.

## Message Sending Rules

- only consented, active contacts receive messages
- credits are deducted per successful recipient
- if credits run out mid-send, the remaining contacts are marked as skipped
- failed provider calls are logged as failed deliveries
- sending uses the shared Africa's Talking client from `apps.core.utils.sms`

## Environment Variables

```env
AFRICASTALKING_USERNAME=
AFRICASTALKING_API_KEY=
AFRICASTALKING_SENDER_ID=
AFRICASTALKING_SMS_URL=https://api.africastalking.com/version1/messaging
CLASS_COMMS_SMS_COST_PER_MESSAGE=1
```

## Example Frontend Use

A class rep can open the class comms dashboard and see:

- remaining credits
- registered contacts
- recent broadcasts
- delivery status for each recipient
- the public registration link

That gives the UI enough data to build a clean dashboard without extra backend round trips.

## Testing

Run the focused slice with:

```bash
./.venv/bin/python manage.py test apps.classcomms.tests --settings=kibegi_api.test_settings
```

The test coverage should include:

- rep promotion
- manual contact creation
- public contact registration
- SMS broadcast send and credit deduction
