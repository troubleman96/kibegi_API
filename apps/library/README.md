# Library App

The library app is a public campus knowledge hub for books, past papers, notes, slides, projects, assignments, and other useful resources.

## What It Does

- lets students upload helpful study materials
- makes those materials publicly browseable
- keeps this storage separate from the personal storage quota system
- supports search, filtering, detail pages, and downloads

## API Endpoints

Public browse endpoints:

- `GET /api/v1/library/categories/`
- `GET /api/v1/library/items/`
- `GET /api/v1/library/items/search/?q=math`
- `GET /api/v1/library/items/<item_code>/`
- `GET /api/v1/library/items/<item_code>/download/`

Authenticated upload and management endpoints:

- `POST /api/v1/library/items/`
- `GET /api/v1/library/items/me/`
- `PATCH /api/v1/library/items/<item_code>/`
- `DELETE /api/v1/library/items/<item_code>/`

## Default Categories

The backend seeds these library categories:

- books
- past papers
- notes
- slides
- projects
- assignments
- research
- other

## Storage Note

Library uploads are stored in a dedicated `library/` media path and are not connected to the user storage quota model used by personal uploads.
