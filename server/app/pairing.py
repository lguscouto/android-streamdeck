from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timezone

from app.db import Database

_REVOCATION_REASONS = frozenset({"user_request", "lost_device", "security", "replaced"})


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
        return True

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

        return self.issue_token(
            client_id,
            client_version,
            actor_kind="pairing_code",
        )

    def issue_token(
        self,
        client_id: str,
        client_version: str,
        *,
        actor_kind: str = "pairing_session",
    ) -> str:
        """Issue a token after an already-authenticated pairing session."""
        if actor_kind not in {"pairing_code", "pairing_session"}:
            raise ValueError("unsupported pairing actor")

        token = secrets.token_urlsafe(32)
        token_hash = _hash_token(token)
        timestamp = datetime.now(timezone.utc).isoformat()
        try:
            with self.database.transaction() as connection:
                existing = connection.execute(
                    """
                    SELECT credential_generation
                    FROM paired_clients
                    WHERE client_id = ?
                    """,
                    (client_id,),
                ).fetchone()
                if existing is None:
                    credential_generation = 1
                    event_type = "paired"
                    reason_code = None
                    connection.execute(
                        """
                        INSERT INTO paired_clients(
                            client_id, client_version, platform, device_label,
                            token_hash,
                            credential_generation, paired_at, last_seen_at,
                            revoked_at, revoked_reason
                        )
                        VALUES (?, ?, 'android', NULL, ?, ?, ?, NULL, NULL, NULL)
                        """,
                        (
                            client_id,
                            client_version,
                            token_hash,
                            credential_generation,
                            timestamp,
                        ),
                    )
                else:
                    credential_generation = int(existing["credential_generation"]) + 1
                    event_type = "repaired"
                    reason_code = "replaced"
                    connection.execute(
                        """
                        UPDATE paired_clients
                        SET
                            client_version = ?,
                            token_hash = ?,
                            credential_generation = ?,
                            paired_at = ?,
                            last_seen_at = NULL,
                            revoked_at = NULL,
                            revoked_reason = NULL
                        WHERE client_id = ?
                        """,
                        (
                            client_version,
                            token_hash,
                            credential_generation,
                            timestamp,
                            client_id,
                        ),
                    )
                connection.execute(
                    """
                    INSERT INTO paired_client_audit(
                        client_id, event_type, credential_generation, actor_kind,
                        reason_code, occurred_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        client_id,
                        event_type,
                        credential_generation,
                        actor_kind,
                        reason_code,
                        timestamp,
                    ),
                )
        except Exception as exc:
            raise PairingError("pairing persistence failed") from exc
        return token

    def list_clients(self) -> list[dict[str, object]]:
        """Return a sanitized device inventory without hashes or credentials."""
        connection = self.database.connect()
        try:
            rows = connection.execute(
                """
                SELECT client_id, client_version, platform, credential_generation,
                       paired_at, last_seen_at, revoked_at, revoked_reason
                FROM paired_clients
                ORDER BY revoked_at IS NOT NULL, paired_at DESC, client_id
                """
            ).fetchall()
            return [
                {
                    "client_id": str(row["client_id"]),
                    "client_version": str(row["client_version"]),
                    "platform": str(row["platform"]),
                    "credential_generation": int(row["credential_generation"]),
                    "paired_at": str(row["paired_at"]),
                    "last_seen_at": row["last_seen_at"],
                    "revoked_at": row["revoked_at"],
                    "revoked_reason": row["revoked_reason"],
                }
                for row in rows
            ]
        except Exception as exc:
            raise PairingError("device inventory lookup failed") from exc
        finally:
            connection.close()

    def revoke_client(self, client_id: str, reason_code: str) -> bool:
        """Revoke one device locally without retaining any plaintext credential."""
        if reason_code not in _REVOCATION_REASONS:
            raise ValueError("unsupported revocation reason")
        timestamp = datetime.now(timezone.utc).isoformat()
        try:
            with self.database.transaction() as connection:
                existing = connection.execute(
                    """
                    SELECT credential_generation, revoked_at
                    FROM paired_clients
                    WHERE client_id = ?
                    """,
                    (client_id,),
                ).fetchone()
                if existing is None or existing["revoked_at"] is not None:
                    return False
                credential_generation = int(existing["credential_generation"])
                connection.execute(
                    """
                    UPDATE paired_clients
                    SET revoked_at = ?, revoked_reason = ?
                    WHERE client_id = ? AND revoked_at IS NULL
                    """,
                    (timestamp, reason_code, client_id),
                )
                connection.execute(
                    """
                    INSERT INTO paired_client_audit(
                        client_id, event_type, credential_generation, actor_kind,
                        reason_code, occurred_at
                    )
                    VALUES (?, 'revoked', ?, 'local_owner', ?, ?)
                    """,
                    (client_id, credential_generation, reason_code, timestamp),
                )
        except Exception as exc:
            raise PairingError("device revocation failed") from exc
        return True

    def authenticate(self, client_id: str, token: str | None) -> bool:
        return self.active_credential_generation(client_id, token) is not None

    def active_credential_generation(
        self, client_id: str, token: str | None
    ) -> int | None:
        """Return the active credential generation only for a valid opaque token."""
        if not token:
            return None
        token_hash = _hash_token(token)
        connection = self.database.connect()
        try:
            row = connection.execute(
                """
                SELECT token_hash, credential_generation, revoked_at
                FROM paired_clients
                WHERE client_id = ?
                """,
                (client_id,),
            ).fetchone()
            if row is None or row["revoked_at"] is not None:
                return None
            if not hmac.compare_digest(str(row["token_hash"]), token_hash):
                return None
            return int(row["credential_generation"])
        except Exception as exc:
            raise PairingError("pairing lookup failed") from exc
        finally:
            connection.close()

    def is_credential_generation_active(
        self, client_id: str, credential_generation: int
    ) -> bool:
        """Check that a WebSocket session still has the current active credential."""
        if credential_generation < 1:
            return False
        connection = self.database.connect()
        try:
            row = connection.execute(
                """
                SELECT 1
                FROM paired_clients
                WHERE client_id = ?
                  AND credential_generation = ?
                  AND revoked_at IS NULL
                """,
                (client_id, credential_generation),
            ).fetchone()
            return row is not None
        except Exception as exc:
            raise PairingError("credential lookup failed") from exc
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
