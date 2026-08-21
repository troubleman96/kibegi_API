# `internal/apps/sharing`

## Responsibility

The sharing package owns file-share creation, bulk sharing, sent/received/request lists, accept/reject transitions, detail, and shared-file download under `/api/v1/sharing/`.

## State model

A share has an owner/uploader relationship, recipient, upload reference, and status. Creation and bulk creation validate accessible uploads and target users. Accept/reject transitions must verify that the current user is the intended recipient and must not be replayed as a new state transition.

## Integration

Share writes may create notifications and affect the files compatibility view. Reads use sharing status plus upload authorization. Downloads stream through the same object-storage adapter after validating accepted-share access. Keep status transitions transactionally consistent with notification creation where possible, and invalidate files/share list caches after mutation.
