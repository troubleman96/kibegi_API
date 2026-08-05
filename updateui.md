# UI Organization Proposal

The frontend should group features by user intent, not by backend implementation.

## Recommended Sidebar Structure

- Dashboard
- Messaging
  - SMS Wallet
    - balance
    - buy credits
    - delivery history
  - Class Communication
    - contacts
    - broadcast messages
    - public registration link
  - Schedule
    - calendar
    - events
    - reminder settings
    - SMS reminder logs
- Notifications
- Files
- Settings

## Why This Works

- SMS is the shared utility layer, so balance and credit purchases should live there.
- Class Communication is a separate workflow for class reps and should feel like its own app area.
- Schedule is another workflow that also uses SMS, but it should stay distinct from class communication.

## Suggested Labeling

Use simple names that match what users are trying to do:

- SMS
- Class Communication
- Schedule

If the UI needs a top-level grouping, use:

- Messaging
- Operations
- Tools

## User Flow

- Check balance in SMS.
- Buy credits in SMS.
- Manage class members and send updates in Class Communication.
- Create reminders and schedule notices in Schedule.

This keeps the interface clean and makes the product feel like one app with separate tools, instead of unrelated screens.
