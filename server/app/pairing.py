from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timezone

from app.db import Database


class PairingError(RuntimeError):
    """Base class for safe pairing failures."""


class PairingCodeInvalidError(PairingError):
    """Raised when the manually supplied pairing code is invalid."""


class PairingUnavailableError(PairingError):
    """Raised when pairing has not been configured on the server."""


class PairingService:
    """Issue and verify opaque client tokens without persisting plaintext secrets."""

    def __init__(self, database: Database, pairing_code: str | None) -> None:
        self.database = database
        self._pairing_code = pairing_code

    @property
    def enabled(self) -> bool:
        return self._pairing_code is not None

    def claim_token(
        self,
        client_id: str,
        client_version: str,
        pairing_code: str,
    ) -> str:
        configured_code = self._pairing_code
        if configured_code is None:
            raise PairingUnavailableError("pairing is not configured")
        if not hmac.compare_digest(pairing_code, configured_code):
            raise PairingCodeInvalidError("pairing code is invalid")

        token = secrets.token_urlsafe(32)
        token_hash = _hash_token(token)
        timestamp = datetime.now(timezone.utc).isoformat()
        try:
            with self.database.transaction() as connection:
                connection.execute(
                    """
                    INSERT INTO paired_clients(
                        client_id, client_version, token_hash, paired_at, last_seen_at
                    )
                    VALUES (?, ?, ?, ?, NULL)
                    ON CONFLICT(client_id) DO UPDATE SET
                        client_version = excluded.client_version,
                        token_hash = excluded.token_hash,
                        paired_at = excluded.paired_at,
                        last_seen_at = NULL
                    """,
                    (client_id, client_version, token_hash, timestamp),
                )
        except Exception as exc:
            raise PairingError("pairing persistence failed") from exc
        return token

    def authenticate(self, client_id: str, token: str | None) -> bool:
        if not self.enabled or not token:
            return False
        token_hash = _hash_token(token)
        connection = self.database.connect()
        try:
            row = connection.execute(
                """
                SELECT token_hash
                FROM paired_clients
                WHERE client_id = ?
                """,
                (client_id,),
            ).fetchone()
            if row is None:
                return False
            return hmac.compare_digest(str(row["token_hash"]), token_hash)
        except Exception as exc:
            raise PairingError("pairing lookup failed") from exc
        finally:
            connection.close()


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


__all__ = [
    "PairingCodeInvalidError",
    "PairingError",
    "PairingService",
    "PairingUnavailableError",
]
