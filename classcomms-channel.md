# Kibegi Channel Workflow

This document describes how class communications work in Kibegi after the channel update.

## What the channel is

- Every class can have a channel for announcements and venue updates.
- Lecturers and class representatives can manage the channel.
- Broadcasts are sent as SMS through SendAfrica.

## Who can receive broadcasts

- Only Kibegi users who are already registered and joined to the class can be added as channel members.
- A phone number must match an active Kibegi user in that class.
- Non-members are rejected with a clear error message so the channel stays member-only.

## How a student joins

- A class rep or lecturer can share the channel registration link from the Channel page.
- The invite page explains the class code and points students to create a Kibegi account first if they do not have one.
- After they create an account and join the class, they can be added as a channel member.

## Broadcast flow

1. The class rep writes a subject, message, and optional venue.
2. Kibegi sends the SMS to all registered channel members.
3. Kibegi also sends an email reminder/notification where email is available.
4. Delivery status is stored in the class communications logs.

## VPS deployment notes

- Pull the latest `API` and `UI` changes.
- Run migrations for the new `classcomms` contact member link.
- Restart the API after deployment so the new member-only validation is active.

