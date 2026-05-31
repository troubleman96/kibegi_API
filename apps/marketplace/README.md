    # Marketplace App

    The marketplace app gives students a place to list items for sale and buy items from other users.

    ## Core Concepts

    - `Category`: groups listings by subject or item type.
    - `Listing`: a product posted by a student seller.
    - `ListingOrder`: a completed purchase record.

    ## API Endpoints

    All endpoints require authentication.

    - `GET /api/v1/marketplace/categories/`
    - `GET /api/v1/marketplace/categories/<slug>/`
    - `GET /api/v1/marketplace/listings/`
    - `POST /api/v1/marketplace/listings/`
    - `GET /api/v1/marketplace/listings/search/?q=calculator`
    - `GET /api/v1/marketplace/listings/me/`
    - `GET /api/v1/marketplace/listings/<listing_code>/`
    - `PATCH /api/v1/marketplace/listings/<listing_code>/`
    - `DELETE /api/v1/marketplace/listings/<listing_code>/`
    - `POST /api/v1/marketplace/listings/<listing_code>/purchase/`
    - `GET /api/v1/marketplace/orders/`
    - `GET /api/v1/marketplace/orders/<id>/`

    ## Notes

    - Listings use a short `listing_code` for friendly lookup.
    - Purchases are recorded immediately as completed orders.
    - Stock is reduced on purchase and listings move to `sold_out` when quantity reaches zero.
    - Default university categories are seeded in the database, including electronics, books, stationery, fashion, furniture, dorm essentials, gadgets, services, food & snacks, transport, and misc.
