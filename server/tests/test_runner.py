import secrets
from typing import Any

import pytest
import uvicorn
from cryptography import x509

from app.config import Settings
from app.runner import _run_server, main


class FakeSocket:
    def __init__(self, host: str) -> None:
        self.host = host
        self.closed = False

    def close(self) -> None:
        self.closed = True


class FakeConfig:
    instances: list["FakeConfig"] = []

    def __init__(self, application: object, **kwargs: Any) -> None:
        self.application = application
        self.kwargs = kwargs
        self.socket = FakeSocket(str(kwargs["host"]))
        self.instances.append(self)

    def bind_socket(self) -> FakeSocket:
        return self.socket


class FakeServer:
    instances: list["FakeServer"] = []

    def __init__(self, config: FakeConfig) -> None:
        self.config = config
        self.sockets: list[FakeSocket] | None = None
        self.instances.append(self)

    def run(self, *, sockets: list[FakeSocket]) -> None:
        self.sockets = sockets


class FailingLoopbackConfig(FakeConfig):
    def bind_socket(self) -> FakeSocket:
        if self.kwargs["host"] == "127.0.0.1":
            raise OSError("synthetic loopback bind failure")
        return self.socket


def test_dual_bind_closes_lan_socket_when_loopback_bind_fails(monkeypatch) -> None:
    FailingLoopbackConfig.instances = []
    monkeypatch.setattr(uvicorn, "Config", FailingLoopbackConfig)

    settings = Settings(
        host="192.168.50.44",
        require_auth=True,
        tls_mode="required",
        tls_identities=("192.168.50.44",),
    )

    with pytest.raises(OSError, match="synthetic loopback bind failure"):
        _run_server(object(), settings, {})

    lan_config, loopback_config = FailingLoopbackConfig.instances
    assert lan_config.socket.closed is True
    assert loopback_config.socket.closed is False


def test_main_binds_private_ipv4_to_lan_and_loopback_explicitly(monkeypatch, tmp_path):
    pairing_code = f"test-{secrets.token_urlsafe(24)}"
    tls_state_dir = tmp_path / "tls"
    monkeypatch.setenv("STREAMDECK_HOST", "192.168.50.44")
    monkeypatch.setenv("STREAMDECK_PORT", "18766")
    monkeypatch.setenv("STREAMDECK_PAIRING_CODE", pairing_code)
    monkeypatch.setenv("STREAMDECK_TLS_IDENTITIES", "deck.example.test")
    monkeypatch.setenv("STREAMDECK_TLS_STATE_DIR", str(tls_state_dir))
    FakeConfig.instances = []
    FakeServer.instances = []
    monkeypatch.setattr(uvicorn, "Config", FakeConfig)
    monkeypatch.setattr(uvicorn, "Server", FakeServer)

    main()

    assert len(FakeConfig.instances) == 2
    lan_config, loopback_config = FakeConfig.instances
    application = lan_config.application
    assert application.state.settings.host == "192.168.50.44"
    assert application.state.settings.port == 18766
    assert [config.kwargs["host"] for config in FakeConfig.instances] == [
        "192.168.50.44",
        "127.0.0.1",
    ]
    assert all(config.kwargs["port"] == 18766 for config in FakeConfig.instances)
    assert all(config.kwargs["log_config"] is None for config in FakeConfig.instances)
    assert all(
        config.kwargs["ssl_certfile"] == str(tls_state_dir / "leaf-chain.pem")
        for config in FakeConfig.instances
    )
    assert all(
        config.kwargs["ssl_keyfile"] == str(tls_state_dir / "leaf-key.pem")
        for config in FakeConfig.instances
    )
    assert len(FakeServer.instances) == 1
    assert FakeServer.instances[0].config is lan_config
    assert FakeServer.instances[0].sockets == [
        lan_config.socket,
        loopback_config.socket,
    ]
    assert all(config.socket.closed for config in FakeConfig.instances)

    leaf_certificate = x509.load_pem_x509_certificate(
        (tls_state_dir / "leaf-chain.pem").read_bytes()
    )
    alternative_names = leaf_certificate.extensions.get_extension_for_class(
        x509.SubjectAlternativeName
    ).value
    dns_names = alternative_names.get_values_for_type(x509.DNSName)
    ip_addresses = alternative_names.get_values_for_type(x509.IPAddress)
    assert dns_names == ["deck.example.test"]
    assert [str(value) for value in ip_addresses] == [
        "192.168.50.44",
        "127.0.0.1",
    ]
