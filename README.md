# Store API

REST API for retail store locations, built with [FastAPI](https://fastapi.tiangolo.com/). Store records live in a JSON file at the project root (`stores.json` by default). Interactive docs are generated from the code.

## Features

- Create, list, read, replace, update, and delete stores
- Filter by text, city, category, and active status, with sort and pagination
- Request validation and OpenAPI docs at `/docs` and `/redoc`
- Configuration through environment variables and a `.env` file
- Atomic JSON writes and a lock file so overlapping writes do not corrupt the document

The JSON file is a good fit for local development and small datasets on one machine. The HTTP contract can stay the same if the storage layer is later swapped for a database.

## Requirements

- Python 3.11 or newer

## Setup

From the project root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

`.env` is gitignored. `.env.example` lists every setting.

## Run

`python -m app.main` reads `HOST`, `PORT`, `DEBUG`, and `LOG_LEVEL` from the environment:

```bash
python -m app.main
```

Or start Uvicorn directly:

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

- API root: http://127.0.0.1:8000/
- Swagger UI: http://127.0.0.1:8000/docs
- ReDoc: http://127.0.0.1:8000/redoc
- OpenAPI schema: http://127.0.0.1:8000/openapi.json

With `DEBUG=true`, the process reloads when Python files change. JSON edits do not restart the server. The running process reads the file on each request.

## Environment

| Variable | Default | Description |
| --- | --- | --- |
| `APP_NAME` | `Store API` | Name shown in docs and the health check |
| `APP_VERSION` | `1.0.0` | Version shown in docs and the health check |
| `APP_ENV` | `development` | Environment label reported by `/health` |
| `DEBUG` | `false` | Enables auto-reload when you start the app with `python -m app.main` |
| `HOST` | `127.0.0.1` | Bind address for `python -m app.main` |
| `PORT` | `8000` | Bind port for `python -m app.main` |
| `DATA_FILE` | `stores.json` | Store data file. Relative paths are resolved from the project root. Absolute paths are used as given. |
| `CORS_ORIGINS` | `*` | Comma-separated browser origins, or `*` to allow any origin |
| `LOG_LEVEL` | `info` | One of `debug`, `info`, `warning`, `error`, `critical` |

Shell environment variables override `.env`. A local `.env` is already present with development defaults. `DEBUG` defaults to `false` in code and is set to `true` in `.env`.

`CORS_ORIGINS=*` does not allow credentialed browser requests. Set explicit origins when a browser app sends cookies.

## API

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/` | API name, version, and links |
| `GET` | `/health` | Status plus the number of stores in the file |
| `GET` | `/api/v1/stores` | List stores |
| `POST` | `/api/v1/stores` | Create a store. Returns `201` and a `Location` header. |
| `GET` | `/api/v1/stores/{store_id}` | Fetch one store |
| `PUT` | `/api/v1/stores/{store_id}` | Replace the store. `id` and `created_at` stay the same. |
| `PATCH` | `/api/v1/stores/{store_id}` | Update the fields you send |
| `DELETE` | `/api/v1/stores/{store_id}` | Delete a store. Returns `204` with an empty body. |

### List query parameters

| Parameter | Description |
| --- | --- |
| `q` | Case-insensitive substring match on name, description, or city |
| `city` | Exact city name, case-insensitive |
| `category` | One of the categories below |
| `is_active` | `true` or `false` |
| `sort` | `name`, `-name`, `created_at`, or `-created_at`. Default is `-created_at` (newest first). |
| `skip` | Number of matching records to skip. Default `0`. |
| `limit` | Page size from 1 to 100. Default `20`. |

The list response looks like this:

```json
{
  "items": [],
  "total": 0,
  "skip": 0,
  "limit": 20
}
```

`total` is the number of matches before paging.

### Store fields

| Field | Required on create | Notes |
| --- | --- | --- |
| `name` | yes | 1–120 characters |
| `description` | no | Up to 2000 characters |
| `address` | yes | `street`, `city`, and `country` are required. `state` and `postal_code` are optional. |
| `phone` | no | 7–15 digits. Spaces, `+`, hyphens, dots, and parentheses are allowed. |
| `email` | no | Valid email address |
| `website` | no | `http` or `https` URL |
| `category` | yes | `grocery`, `electronics`, `clothing`, `pharmacy`, `hardware`, `bookstore`, `restaurant`, `convenience`, `other` |
| `is_active` | no | Defaults to `true` |
| `opening_hours` | no | Each day is `HH:MM-HH:MM` or `closed` |

The server sets `id`, `created_at`, and `updated_at`. Clients cannot send those fields. Unknown fields are rejected with `422`.

`PUT` expects the same body as create. `PATCH` accepts any subset. When `address` or `opening_hours` is included in a patch, that nested object is replaced as a whole. Omitted fields are left unchanged. An empty patch returns the store as it is.

### Examples

List the sample stores:

```bash
curl http://127.0.0.1:8000/api/v1/stores
```

Active grocery stores in San Francisco:

```bash
curl "http://127.0.0.1:8000/api/v1/stores?city=San%20Francisco&category=grocery&is_active=true"
```

Create a store:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/stores \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Corner Shop",
    "description": "A small convenience store.",
    "address": {
      "street": "1 Main Street",
      "city": "Austin",
      "state": "TX",
      "postal_code": "73301",
      "country": "USA"
    },
    "phone": "+1 512 555 0199",
    "email": "corner@example.com",
    "website": "https://example.com/corner",
    "category": "convenience",
    "is_active": true,
    "opening_hours": {
      "monday": "09:00-17:00",
      "sunday": "closed"
    }
  }'
```

Update one field:

```bash
curl -X PATCH http://127.0.0.1:8000/api/v1/stores/STORE_ID \
  -H "Content-Type: application/json" \
  -d '{"is_active": false}'
```

Delete:

```bash
curl -X DELETE http://127.0.0.1:8000/api/v1/stores/STORE_ID
```

### Errors

| Status | When |
| --- | --- |
| `404` | The store id is not in the file |
| `422` | The body or query string failed validation |
| `500` | The JSON file is missing the expected shape, is invalid JSON, or cannot be written |

A not-found response is `{"detail": "Store '...' was not found."}`. Validation errors use FastAPI's default `detail` array of field errors.

## Data file

`stores.json` is the database. The document is an object with a `stores` array:

```json
{
  "stores": [
    {
      "id": "6f1d8c3a-1b2e-4c77-9a10-0b1c2d3e4f50",
      "name": "Harbor Market",
      "address": {
        "street": "120 Market Street",
        "city": "San Francisco",
        "state": "CA",
        "postal_code": "94105",
        "country": "USA"
      },
      "category": "grocery",
      "is_active": true,
      "created_at": "2026-01-15T10:00:00+00:00",
      "updated_at": "2026-01-15T10:00:00+00:00"
    }
  ]
}
```

The repository ships with three sample stores: Harbor Market (San Francisco), Northwind Electronics (Seattle), and Linden Books (Portland, inactive).

Each write saves a temporary file beside the data file and replaces `stores.json` only after the document is flushed. Readers therefore see either the previous document or the new one. A `stores.json.lock` file next to the data file keeps writers from overlapping. Copy `stores.json` to back it up. You can edit it by hand while the server is running; the next request loads the new contents. Keep the `{"stores": [...]}` shape, or the API responds with `500`.

Run one server process against a given file. The lock covers overlapping requests, including extra Uvicorn workers, but this storage is still meant for a single machine and a modest number of stores.

If `DATA_FILE` does not exist, the API creates it as `{"stores": []}` on startup.

## Project layout

```
store-api/
├── app/
│   ├── main.py            # App factory, CORS, routes, entrypoint
│   ├── config.py          # Settings from the environment and .env
│   ├── schemas.py         # Request and response models
│   ├── repository.py      # JSON file reads and writes
│   ├── dependencies.py
│   └── routers/
│       ├── health.py
│       └── stores.py
├── tests/
│   ├── conftest.py
│   └── test_api.py
├── stores.json            # Store data
├── .env.example
├── pytest.ini
├── requirements.txt
└── README.md
```

## Tests

Tests use a temporary JSON file and do not modify `stores.json`.

```bash
pytest
```

## Sample records

| Id | Name | City | Category | Active |
| --- | --- | --- | --- | --- |
| `6f1d8c3a-1b2e-4c77-9a10-0b1c2d3e4f50` | Harbor Market | San Francisco | grocery | yes |
| `7c2e9d4b-2c3f-4d88-8b21-1c2d3e4f5061` | Northwind Electronics | Seattle | electronics | yes |
| `8d3fac5c-3d40-4e99-9c32-2d3e4f506172` | Linden Books | Portland | bookstore | no |
