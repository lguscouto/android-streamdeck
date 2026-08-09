# Android Stream Deck server

Minimal local FastAPI server for the Android Stream Deck protocol.

## Run the server

From this directory, run:

```bash
uv run streamdeck-server
```

The operational entrypoint reads the bind configuration and passes it to
Uvicorn. The defaults are:

- host: `127.0.0.1`
- port: `8765`

The health endpoint is available at `http://127.0.0.1:8765/health` when the
defaults are used.

## Configure the bind address

Set the environment variables before starting the entrypoint:

```bash
export STREAMDECK_HOST=0.0.0.0
export STREAMDECK_PORT=18766
uv run streamdeck-server
```

For a single invocation in a POSIX shell:

```bash
STREAMDECK_HOST=127.0.0.1 STREAMDECK_PORT=18766 uv run streamdeck-server
```

`STREAMDECK_PORT` must be an integer from `1` to `65535`. The
`STREAMDECK_HOST` value is passed directly to Uvicorn.

The file `.env.example` documents the bind variables, but it is only an
example and is **not loaded automatically**. Export or set the variables in
the process environment explicitly; this project does not add `python-dotenv`.
`STREAMDECK_DATABASE_PATH` selects the local SQLite file and defaults to
`server/data/streamdeck.sqlite3`.

## Versioned HTTP API

The API is available under `/api/v1`:

- `GET /api/v1/profile` returns the active profile.
- `GET /api/v1/profiles/{profile_id}/snapshot` returns the current snapshot;
  pass `?revision=N` for an exact historical revision (`N >= 1`).
- `GET /api/v1/actions` returns the closed catalog in stable order:
  `hotkey`, `key`, `media`, `text`, `url`, `application`.
- `PUT /api/v1/profiles/{profile_id}?expected_revision=N` validates and stores
  the next profile revision. The URL ID and body ID must match.

The action catalog is descriptive only. The HTTP API does not execute shell,
command, subprocess, or arbitrary Windows actions. Validation, not-found,
conflict, and internal failures use the sanitized shape:

```json
{"code":"PROFILE_REVISION_CONFLICT","message":"Profile revision conflict","retryable":true}
```

## Development checks

```bash
uv run pytest -q
uv run ruff check .
```
