# Channel App

This app powers Kibegi's standalone broadcast channels. It replaced the older class-linked messaging idea and now behaves like a campaign/broadcast space that lives on its own.

## What it does

- Lets a verified user create a unique channel name
- Supports `public` and `private` channels
- Lets registered Kibegi users join with their existing account identity
- Lets channel owners add registered users by email, phone, or full name
- Sends broadcast SMS messages to all active channel members
- Shows channel credits and delivery history in both the UI and Django admin

## Key endpoints

- `GET /api/v1/channel/channels/`
- `POST /api/v1/channel/channels/`
- `GET /api/v1/channel/channels/<channel_id>/`
- `PATCH /api/v1/channel/channels/<channel_id>/`
- `POST /api/v1/channel/channels/<channel_id>/members/`
- `POST /api/v1/channel/channels/<channel_id>/join/`
- `POST /api/v1/channel/channels/<channel_id>/broadcasts/`
- `GET /api/v1/public/channel/<invite_token>/info/`
- `POST /api/v1/public/channel/<invite_token>/join/`

## Notes

- Channel names must be unique.
- Public channels can be searched from the UI.
- Private channels are joined through the invite link.
- Users must verify their phone number before creating, joining, or broadcasting.
- Broadcast credits are synchronized with the SMS wallet infrastructure so admin top-ups and channel sends stay aligned.
