import pytest

from app.config import Settings


def test_private_remote_bind_auto_requires_tls_with_host_identity(tmp_path) -> None:
    settings = Settings(
        host="192.168.50.10",
        port=9443,
        database_path=tmp_path / "streamdeck.sqlite3",
        pairing_code="pairing-test",
        require_auth=True,
        tls_mode="auto",
        tls_state_dir=tmp_path / "tls",
    )

    assert settings.tls_required is True
    assert settings.tls_identities == ("192.168.50.10",)
    assert settings.tls_state_dir == tmp_path / "tls"


@pytest.mark.parametrize(
    "identity",
    ("*.example.test", "https://deck.example.test", "deck.example.test:8765"),
)
def test_settings_rejects_noncanonical_tls_identity(tmp_path, identity: str) -> None:
    with pytest.raises(ValueError, match="TLS identity"):
        Settings(
            host="192.168.50.10",
            port=9443,
            database_path=tmp_path / "streamdeck.sqlite3",
            pairing_code="pairing-test",
            require_auth=True,
            tls_mode="required",
            tls_state_dir=tmp_path / "tls",
            tls_identities=(identity,),
        )
