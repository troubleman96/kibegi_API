# Channel App

This app provides Kibegi's standalone broadcast channels.

## What it does

- Lets a user create a unique channel name.
- Supports `public` and `private` channels.
- Lets registered Kibegi users join with their existing account identity.
- Lets channel owners add registered users by email, phone, or full name.
- Sends broadcast SMS messages to all active channel members.

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
- Broadcast credits use the existing Kibegi SMS wallet infrastructure.

