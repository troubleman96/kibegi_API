# Kibegi API

Kibegi is a Django REST API for a digital school platform. The current backend covers authentication, profiles, classes, schedules, standalone broadcast channels, SMS delivery, uploads, sharing, notifications, and related support services.

## What Is In Production

- JWT auth with email registration, Google login, password reset, and phone verification
- Student profiles with `phone_number` and `phone_verified`
- Class management and resource sharing
- Schedule calendars for classes and examinations
- SMS reminders for schedule events
- Standalone `channel` app for broadcast campaigns
- SendAfrica SMS delivery
- Admin pages for wallet, channel, and delivery management

## Main Apps

- [`apps/authentication`](apps/authentication/README.md)
- [`apps/classes`](apps/classes/README.md)
- [`apps/schedule`](apps/schedule/README.md)
- [`apps/channel`](apps/channel/README.md)
- [`apps/classcomms`](apps/classcomms/README.md) legacy compatibility layer
- [`apps/sms`](apps/sms)
- [`apps/uploads`](apps/uploads/README.md)
- [`apps/sharing`](apps/sharing/README.md)
- [`apps/friends`](apps/friends/README.md)
- [`apps/notifications`](apps/notifications/README.md)
- [`apps/library`](apps/library/README.md)
- [`apps/marketplace`](apps/marketplace/README.md)
- [`apps/storage`](apps/storage/README.md)

## Local Setup

```bash
cd API
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

## Environment

Create `API/.env` with the values your deployment uses. The important ones are:

```env
SECRET_KEY=...
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
DATABASE_URL=...
DEFAULT_FROM_EMAIL=...
EMAIL_HOST=...
EMAIL_HOST_USER=...
EMAIL_HOST_PASSWORD=...
SEND_AFRICA_API_URL=https://sendafrica.online/api
SEND_AFRICA_USERNAME=...
SEND_AFRICA_API_KEY=...
SEND_AFRICA_SENDER_ID=...
```

For production on the VPS:

```bash
git pull
source .venv/bin/activate
python manage.py migrate
python manage.py collectstatic --noinput
sudo systemctl restart kibegi.service
```

## Channel Flow

The standalone channel app lets a verified user:

- create a unique channel name
- choose public or private visibility
- share an invite link
- search and join public channels
- add registered Kibegi users by email, phone, or full name
- send broadcast SMS to active members

Rules:

- channel names must be unique
- only registered users can be added
- users must verify their phone number before creating, joining, or broadcasting
- each recipient consumes 1 SMS credit

## SMS Credits

Credits are tracked in two places for compatibility:

- the legacy `SmsAccount` wallet
- the channel-specific `ChannelWallet`

The channel wallet now syncs with the latest top-up source so the UI and admin pages show the same balance.

## Testing

```bash
env DEBUG=False .venv/bin/python manage.py test apps.channel.tests --settings=kibegi_api.test_settings
```

## API Docs

- Swagger: `/api/docs/`
- ReDoc: `/api/redoc/`
- Schema: `/api/schema/`
