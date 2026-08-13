from __future__ import annotations

import json
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from app.db import Database
from app.migrations import LATEST_SCHEMA_VERSION
from app.rate_limit import AttemptRateLimiter
from app.repositories.profiles import ProfileRepository
from app.schemas import Profile

FIXTURE_PATH = (
    Path(__file__).resolve().parents[2] / "shared" / "fixtures" / "default-profile.json"
)


def _load_default_wire(*, profile_id: str, revision: int) -> dict[str, object]:
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    payload["id"] = profile_id
    payload["revision"] = revision
    return payload


def test_rate_limiter_allows_exactly_max_attempts_under_thread_contention() -> None:
    limiter = AttemptRateLimiter(max_attempts=5, window_seconds=60.0)
    results: list[bool] = []
    lock = threading.Lock()

    def attempt() -> None:
        allowed = limiter.allow("origin-A")
        with lock:
            results.append(allowed)

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(attempt) for _ in range(30)]
        for future in futures:
            future.result()

    assert sum(results) == 5
    assert len(results) == 30


def test_rate_limiter_reset_does_not_affect_other_origins() -> None:
    limiter = AttemptRateLimiter(max_attempts=2, window_seconds=60.0)

    assert limiter.allow("a") is True
    assert limiter.allow("a") is True
    assert limiter.allow("a") is False

    limiter.reset("a")

    assert limiter.allow("a") is True
    assert limiter.allow("b") is True
    assert limiter.allow("b") is True
    assert limiter.allow("b") is False


def test_rate_limiter_bounds_distinct_origin_state() -> None:
    limiter = AttemptRateLimiter(max_attempts=1, max_origins=2)

    assert limiter.allow("a") is True
    assert limiter.allow("b") is True
    assert limiter.allow("c") is False


def test_concurrent_profile_writes_are_serializable_without_lost_updates(
    tmp_path: Path,
) -> None:
    database = Database(tmp_path / "concurrent.sqlite3")
    database.initialize()
    repository = ProfileRepository(database)
    repository.seed_profile(
        Profile.model_validate(_load_default_wire(profile_id="default", revision=1))
    )

    def write(title: str) -> int:
        # Optimistic concurrency: read the latest revision from each thread, then
        # retry until the write succeeds. A healthy conflict simply means another
        # writer advanced the revision first.
        attempts = 20
        for _ in range(attempts):
            profile = repository.get_profile("default")
            next_revision = profile.revision + 1
            payload = _load_default_wire(profile_id="default", revision=next_revision)
            payload["pages"][0]["buttons"][0]["title"] = title
            try:
                saved = repository.save_profile(
                    Profile.model_validate(payload),
                    expected_revision=profile.revision,
                    reason="updated",
                )
            except Exception as exc:  # ProfileConflictError on expected mismatch
                if type(exc).__name__ == "ProfileConflictError":
                    continue
                raise
            return saved.revision
        raise AssertionError(f"write never succeeded for {title}")

    titles = {f"concurrent-{index}" for index in range(1, 7)}
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(write, title) for title in titles]
        revisions = sorted(future.result() for future in futures)

    # Every write eventually landed on a distinct, monotonically increasing
    # revision with no lost update: exactly the 6 final positions.
    assert len(revisions) == len(set(revisions)) == 6
    assert revisions == list(range(2, 8))  # seeded at revision 1 + six writes

    final = repository.get_profile("default")
    assert final.revision == 7
    assert final.pages[0].buttons[0].title in titles


def test_concurrent_initialize_migrations_are_idempotent(tmp_path: Path) -> None:
    # Single shared Database instance, as in the single-process server: many
    # threads may race startup/migration on the same instance.
    database = Database(tmp_path / "migrate-concurrent.sqlite3")

    def initialize() -> int:
        database.initialize()
        with database.connect() as connection:
            return int(connection.execute("PRAGMA user_version").fetchone()[0])

    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(initialize) for _ in range(8)]
        versions = [future.result() for future in futures]

    assert all(version == LATEST_SCHEMA_VERSION for version in versions)
