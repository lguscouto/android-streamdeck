from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest

from app.gpu_telemetry import (
    AmdGpuTelemetryNative,
    GpuTelemetry,
    read_amd_gpus,
    read_nvidia_gpus,
    read_primary_gpu,
    select_primary_gpu,
)


def test_nvidia_provider_normalizes_all_devices_and_shuts_down(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[object] = []

    class FakeNvml:
        NVML_TEMPERATURE_GPU = 0

        @staticmethod
        def nvmlInit() -> None:
            calls.append("init")

        @staticmethod
        def nvmlShutdown() -> None:
            calls.append("shutdown")

        @staticmethod
        def nvmlDeviceGetCount() -> int:
            return 2

        @staticmethod
        def nvmlDeviceGetHandleByIndex(index: int) -> str:
            return f"handle-{index}"

        @staticmethod
        def nvmlDeviceGetMemoryInfo(handle: str) -> SimpleNamespace:
            return SimpleNamespace(used=2 * 1024**3, total=8 * 1024**3)

        @staticmethod
        def nvmlDeviceGetTemperature(handle: str, sensor: int) -> int:
            return 61

    monkeypatch.setitem(sys.modules, "pynvml", FakeNvml)

    result = read_nvidia_gpus()

    assert result == (
        GpuTelemetry("nvidia", 0, True, 61, 2 * 1024**3, 8 * 1024**3),
        GpuTelemetry("nvidia", 1, True, 61, 2 * 1024**3, 8 * 1024**3),
    )
    assert calls == ["init", "shutdown"]


def test_nvidia_provider_shuts_down_when_memory_read_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    class FakeNvml:
        NVML_TEMPERATURE_GPU = 0
        nvmlInit = staticmethod(lambda: calls.append("init"))
        nvmlShutdown = staticmethod(lambda: calls.append("shutdown"))
        nvmlDeviceGetCount = staticmethod(lambda: 1)
        nvmlDeviceGetHandleByIndex = staticmethod(lambda _index: object())

        @staticmethod
        def nvmlDeviceGetMemoryInfo(_handle: object) -> SimpleNamespace:
            raise RuntimeError("driver path must stay private")

    monkeypatch.setitem(sys.modules, "pynvml", FakeNvml)

    assert read_nvidia_gpus() == ()
    assert calls == ["init", "shutdown"]


def test_nvidia_provider_missing_module_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_import = __import__

    def missing_import(name: str, *args: object, **kwargs: object) -> object:
        if name == "pynvml":
            raise ImportError("not installed")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", missing_import)
    assert read_nvidia_gpus() == ()


def test_amd_provider_maps_native_records_without_exposing_strings() -> None:
    record = AmdGpuTelemetryNative(
        abi_version=1,
        provider_index=3,
        is_discrete=1,
        temperature_celsius=55,
        used_bytes=2 * 1024**3,
        total_bytes=8 * 1024**3,
    )

    class FakeFunction:
        def __init__(self, callback):
            self.callback = callback
            self.argtypes = None
            self.restype = None

        def __call__(self, *args):
            return self.callback(*args)

    class FakeBridge:
        streamdeck_gpu_bridge_abi_version = FakeFunction(lambda: 1)

        streamdeck_read_amd_gpus = FakeFunction(
            lambda buffer, capacity: (
                1
                if buffer is None or capacity == 0
                else (buffer.__setitem__(0, record) or 1)
            )
        )

    result = read_amd_gpus(
        bridge_path="C:/internal/streamdeck_gpu_bridge.dll",
        loader=lambda _path: FakeBridge(),
        platform="win32",
    )

    assert result == (GpuTelemetry("amd", 3, True, 55, 2 * 1024**3, 8 * 1024**3),)


def test_amd_provider_rejects_wrong_abi_and_missing_bridge() -> None:
    class WrongAbiBridge:
        @staticmethod
        def streamdeck_gpu_bridge_abi_version() -> int:
            return 2

    assert (
        read_amd_gpus(
            bridge_path="C:/internal/streamdeck_gpu_bridge.dll",
            loader=lambda _path: WrongAbiBridge(),
            platform="win32",
        )
        == ()
    )
    assert (
        read_amd_gpus(
            bridge_path="C:/missing/streamdeck_gpu_bridge.dll",
            loader=lambda _path: (_ for _ in ()).throw(OSError("missing")),
            platform="win32",
        )
        == ()
    )


def test_gpu_selection_prefers_complete_discrete_larger_vram_then_stable_tie() -> None:
    candidates = (
        GpuTelemetry("nvidia", 0, True, 60, None, None),
        GpuTelemetry("amd", 0, False, 65, 4 * 1024**3, 8 * 1024**3),
        GpuTelemetry("nvidia", 1, True, 61, 2 * 1024**3, 8 * 1024**3),
        GpuTelemetry("amd", 1, True, 62, 2 * 1024**3, 8 * 1024**3),
    )

    assert select_primary_gpu(candidates) == candidates[2]


def test_read_primary_gpu_continues_when_one_provider_fails() -> None:
    class FailingProvider:
        def read_candidates(self) -> tuple[GpuTelemetry, ...]:
            raise RuntimeError("private provider failure")

    class WorkingProvider:
        def read_candidates(self) -> tuple[GpuTelemetry, ...]:
            return (GpuTelemetry("amd", 0, True, 50, None, None),)

    assert read_primary_gpu((FailingProvider(), WorkingProvider())) == GpuTelemetry(
        "amd", 0, True, 50, None, None
    )
