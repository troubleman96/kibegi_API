# `internal/apps/marketplace`

## Responsibility

The marketplace package owns categories, listings, search, user listings, listing detail, atomic purchases, and order history under `/api/v1/marketplace/`.

## Transaction rules

Purchases are correctness-sensitive. The repository must lock or conditionally update the listing and wallet/balance records inside a PostgreSQL transaction, prevent duplicate successful orders, and commit the order before returning success. Never use Redis as the balance authority; Redis may coordinate idempotency or cache read-only catalog data.

## Read paths

Category and listing searches should use bounded pagination and indexed fields. User-owned listing routes must filter by seller ID. Order detail and history must scope records to the authenticated buyer or seller according to the preserved contract. Invalidate catalog and order cache keys after listing or purchase mutations.
