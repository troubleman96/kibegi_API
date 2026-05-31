# Marketplace Frontend Guide

This document explains how the UI should consume and configure the marketplace API. It is written as a frontend handoff: what data exists, which endpoints to call, which fields are editable, and how to build the main student buy/sell flows.

## Purpose

The marketplace lets students:

- browse available items
- create listings for items they want to sell
- filter and search listings
- view their own listings
- purchase items from other students
- review their purchase and sales history

The API is designed around a simple object model so the frontend can keep the UI fast and predictable.

For the UI, think of this as a university marketplace with a Jiji-style browse experience and an Amazon-style product detail flow, but limited to student-to-student commerce.

## Authentication

All marketplace endpoints require a valid JWT access token.

Use this header on every request:

```http
Authorization: Bearer <access_token>
```

If the token expires, refresh it using the existing auth refresh flow before retrying marketplace requests.

## Data Model

### Category

A category groups listings into useful browse buckets.

Fields returned by the API:

- `id`
- `name`
- `slug`
- `description`
- `is_active`
- `listing_count`
- `created_at`
- `updated_at`

Frontend use:

- show categories in filters, tabs, dropdowns, and sidebars
- use `slug` for filtering and deep links
- hide inactive categories from normal browsing

### Recommended University Category Set

These are the categories the UI can present by default for a campus marketplace. They are suggestions for the frontend configuration and content strategy, not a hard API restriction.

- `electronics`: phones, laptops, chargers, headphones, power banks
- `books`: textbooks, novels, course packs, past question papers
- `stationery`: pens, notebooks, bags, calculators, rulers
- `fashion`: clothes, shoes, watches, bags, accessories
- `furniture`: desks, chairs, lamps, study tables, small storage units
- `dorm-essentials`: bedding, buckets, fans, extension cords, kitchen basics
- `gadgets`: smartwatches, tablets, gaming accessories, speakers
- `services`: tutoring, design help, photo printing, repair help
- `food-snacks`: packaged snacks, drinks, meal prep items where allowed
- `transport`: bike accessories, helmets, small travel gear
- `misc`: anything useful that does not fit the main buckets

Frontend guidance:

- show the first 6 to 8 categories as primary tabs
- keep the rest in an overflow menu or filter drawer
- sort by `listing_count` when you want the hottest categories first
- use clear category icons and short descriptions so students can scan quickly
- these categories are seeded by the backend, so the UI can load them immediately after login or marketplace bootstrap

### Listing

A listing is a student-posted item for sale.

Fields returned by the API:

- `id`
- `listing_code`
- `title`
- `description`
- `price`
- `quantity`
- `sold_quantity`
- `available_quantity`
- `condition`
- `status`
- `image`
- `image_url`
- `location`
- `category`
- `category_name`
- `category_slug`
- `seller`
- `created_at`
- `updated_at`

Important behavior:

- `listing_code` is the friendly lookup key for detail, edit, delete, and purchase actions.
- `seller` is assigned from the authenticated user when a listing is created.
- `available_quantity` is derived from `quantity - sold_quantity`.
- `status` controls visibility and purchase availability.

### ListingOrder

An order is a completed purchase record.

Fields returned by the API:

- `id`
- `listing`
- `buyer`
- `seller`
- `quantity`
- `unit_price`
- `total_price`
- `status`
- `created_at`
- `updated_at`

Frontend use:

- show in purchase history and sales history
- use `buyer` and `seller` to split orders into two user views
- treat these as immutable completed records in the current API

## Enums And Allowed Values

### Listing status

- `active`: visible and purchasable
- `inactive`: temporarily hidden
- `sold_out`: no stock left
- `archived`: hidden from normal browsing and used for soft delete behavior

### Listing condition

- `new`
- `like_new`
- `good`
- `fair`
- `poor`

### Order status

- `completed`
- `cancelled`

The current create flow creates `completed` orders immediately.

## Endpoint Summary

Base path:

```text
/api/v1/marketplace/
```

### Categories

- `GET /categories/`
- `GET /categories/<slug>/`

### Listings

- `GET /listings/`
- `POST /listings/`
- `GET /listings/search/?q=calculator`
- `GET /listings/me/`
- `GET /listings/<listing_code>/`
- `PATCH /listings/<listing_code>/`
- `DELETE /listings/<listing_code>/`
- `POST /listings/<listing_code>/purchase/`

### Orders

- `GET /orders/`
- `GET /orders/<id>/`

## Response Shape

Most marketplace endpoints return the shared project envelope:

```json
{
  "success": true,
  "message": "...",
  "data": [],
  "errors": null
}
```

Single-object responses return the object in `data`.

List endpoints may return a flat array or a paginated payload depending on the view.

## UI Configuration Recommendations

The frontend should define one marketplace config object and reuse it across screens.

Suggested values:

- `basePath`: `/api/v1/marketplace`
- `listingLookupKey`: `listing_code`
- `categoryLookupKey`: `slug`
- `authRequired`: `true`
- `imageField`: `image`
- `imagePreviewField`: `image_url`
- `defaultCurrency`: whatever the app uses for display, formatted in the UI

Suggested marketplace sections for a more complete campus-commerce experience:

- featured listings
- recently added
- nearby or campus-specific listings if location data is being used
- low stock or almost sold out items
- student-only deals and quick picks
- saved searches, if the frontend adds them later

Suggested route mapping:

- marketplace home: browse active listings
- category page: filter listings by `category_slug`
- listing details: open by `listing_code`
- my listings: open by seller identity
- orders page: split by purchases and sales using `type` query parameter

## Listing Creation Form

The create form should submit these writable fields:

- `title`
- `description`
- `price`
- `quantity`
- `condition`
- `image`
- `location`
- `category`

Fields that should not be editable by the UI:

- `listing_code`
- `sold_quantity`
- `available_quantity`
- `seller`
- `status`
- timestamps

Recommended client-side validation:

- `title` required, short and human readable
- `price` must be greater than zero
- `quantity` must be at least 1
- `condition` must match one of the supported values
- `image` should be optional, but previewable when present

## Purchase Flow

Purchase endpoint:

```http
POST /api/v1/marketplace/listings/<listing_code>/purchase/
```

Body:

```json
{
  "quantity": 1
}
```

Frontend behavior:

- disable the buy button when `available_quantity` is 0
- prevent buying your own listing in the UI if the seller id matches the current user id
- allow quantity selection only up to `available_quantity`
- after success, refresh the listing detail and the orders list
- if a purchase fails because stock changed, show a stock-not-available message and reload the item

## Browse And Filter Strategy

Recommended filters:

- search text `q`
- category `category`
- seller `seller_id`
- listing status `status`
- minimum price `min_price`
- maximum price `max_price`

Suggested default browsing behavior:

- show only `active` and `sold_out` listings to normal students
- surface `sold_out` items as visible but disabled or clearly marked
- hide `archived` listings from standard browsing

## List Views

### Marketplace Home

Use `GET /listings/` for the main browse feed.

Show:

- image preview
- title
- price
- category
- condition
- seller name
- stock indicator
- created time

Recommended home-page layout:

- category strip at the top
- search bar with autocomplete or instant submit
- featured items carousel or highlighted grid
- newest items section
- low-stock items section
- a seller trust card or profile snippet

### Search Results

Use `GET /listings/search/?q=<term>`.

This is a lightweight search screen for fast text lookup.

### My Listings

Use `GET /listings/me/`.

This is the seller dashboard:

- edit listing
- archive listing
- review stock and sale status
- see who bought items when order history is added to the seller workflow later

### Orders

Use `GET /orders/?type=purchases` and `GET /orders/?type=sales`.

This should power two tabs:

- purchases: items I bought
- sales: items I sold

Recommended order page extras:

- total spent / total earned summary cards
- last purchase date
- item thumbnails
- quick re-buy or repeat seller contact actions if added later

## Detail Screen Behavior

The listing detail screen should render:

- item image
- title
- description
- price
- condition badge
- category
- location
- seller card
- quantity controls
- buy button
- edit/archive controls for the seller

The detail screen should use `listing_code` from the route.

## Suggested UI States

Handle these states explicitly:

- loading
- empty list
- no search results
- category empty
- sold out item
- archived item
- permission denied
- validation error
- purchase failed due to stock change

Also handle the common commerce states a university marketplace needs:

- out-of-campus item warning
- seller unavailable
- listing removed by owner
- order created successfully
- order history empty
- category filter has no matches

## Examples

### Create listing request

```json
{
  "title": "Calculus Textbook",
  "description": "Second edition in good condition",
  "price": "150.00",
  "quantity": 2,
  "condition": "good",
  "category": 1,
  "location": "Main campus"
}
```

### Purchase request

```json
{
  "quantity": 1
}
```

### Category filter

```text
/api/v1/marketplace/listings/?category=textbooks
```

### Search filter

```text
/api/v1/marketplace/listings/search/?q=calculator
```

## Practical Notes For The UI

- Use `listing_code` everywhere you need stable item URLs.
- Use `category.slug` for category links and `category.id` for create/update payloads.
- Use `seller.id` when comparing ownership.
- Treat `sold_quantity` and `available_quantity` as read-only display data.
- Refresh the listing after every purchase or seller edit.
- Keep the buy button disabled while a purchase request is in flight.
- Use category chips, price range sliders, and quick filters to mimic a modern marketplace without adding unsupported backend complexity.

## University Marketplace UX Suggestions

If the frontend wants a more complete Jiji/Amazon-like campus experience, these are the best UI patterns to build on top of the current API:

- global search at the top of every marketplace page
- category browse rail for quick drill-down
- product cards with image, price, seller, condition, and stock badge
- detail page with a strong primary buy button and seller profile block
- seller dashboard with edit and archive actions
- order history page with purchase and sales tabs
- empty-state cards that push users toward creating a listing
- promoted sections for electronics, books, and dorm essentials because those are the most common student categories

Do not assume backend support for carts, payments, or wishlists yet. If the UI needs those, they should be treated as future features and hidden behind feature flags or disabled states until endpoints exist.

## Future Extension Points

The current API is ready for future additions like:

- favorites / wishlists
- seller chat or contact cards
- moderation / reporting
- delivery or meetup scheduling
- payment provider integration
- listing expiration dates

If any of those are added later, this document should be updated so the UI contract stays current.
