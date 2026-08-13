from __future__ import annotations

import ctypes
import os
from pathlib import Path


class AmdGpuTelemetryNative(ctypes.Structure):
    _fields_ = [
        ("abi_version", ctypes.c_uint32),
        ("provider_index", ctypes.c_int32),
        ("is_discrete", ctypes.c_int32),
        ("temperature_celsius", ctypes.c_int32),
        ("used_bytes", ctypes.c_uint64),
        ("total_bytes", ctypes.c_uint64),
    ]


ABI_VERSION = 1
NATIVE_NA_TEMPERATURE = -(2**31)


def _bridge_path() -> Path:
    configured = os.environ.get("STREAMDECK_GPU_BRIDGE_DLL")
    if configured:
        return Path(configured)
    return (
        Path(__file__).parents[1]
        / "native"
        / "gpu_telemetry_bridge"
        / "bin"
        / "Release"
        / "net8.0"
        / "win-x64"
        / "publish"
        / "streamdeck_gpu_bridge.dll"
    )


def test_amd_bridge_exposes_versioned_read_only_abi() -> None:
    library_path = _bridge_path()
    assert library_path.is_file(), f"AMD bridge was not published: {library_path}"

    bridge = ctypes.WinDLL(str(library_path))
    abi_version = bridge.streamdeck_gpu_bridge_abi_version
    abi_version.argtypes = []
    abi_version.restype = ctypes.c_uint32
    assert abi_version() == ABI_VERSION

    read_gpus = bridge.streamdeck_read_amd_gpus
    read_gpus.argtypes = [
        ctypes.POINTER(AmdGpuTelemetryNative),
        ctypes.c_uint32,
    ]
    read_gpus.restype = ctypes.c_uint32

    required_count = read_gpus(None, 0)
    assert required_count >= 0
    buffer = (AmdGpuTelemetryNative * max(required_count, 1))()
    count = read_gpus(buffer, required_count)
    assert count <= required_count

    for item in buffer[:count]:
        assert item.abi_version == ABI_VERSION
        assert item.provider_index >= 0
        assert item.is_discrete in {-1, 0, 1}
        assert (
            item.temperature_celsius == NATIVE_NA_TEMPERATURE
            or 0 <= item.temperature_celsius <= 150
        )
        assert item.total_bytes == 0 or item.used_bytes <= item.total_bytes
