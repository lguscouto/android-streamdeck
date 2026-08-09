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

The file `.env.example` documents the available variables, but it is only an
example and is **not loaded automatically**. Export or set the variables in
the process environment explicitly; this project does not add `python-dotenv`.

## Development checks

```bash
uv run pytest -q
uv run ruff check .
```
