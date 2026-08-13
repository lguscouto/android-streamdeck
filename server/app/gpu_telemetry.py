from __future__ import annotations

import ctypes
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Literal, Protocol

GpuVendor = Literal["nvidia", "amd"]
NATIVE_NA_TEMPERATURE = -(2**31)
AMD_BRIDGE_ABI_VERSION = 1


@dataclass(frozen=True, slots=True)
class GpuTelemetry:
    vendor: GpuVendor
    provider_index: int
    is_discrete: bool | None
    temperature_celsius: int | None
    used_bytes: int | None
    total_bytes: int | None


class GpuTelemetryProvider(Protocol):
    def read_candidates(self) -> tuple[GpuTelemetry, ...]: ...


class AmdGpuTelemetryNative(ctypes.Structure):
    _fields_ = [
        ("abi_version", ctypes.c_uint32),
        ("provider_index", ctypes.c_int32),
        ("is_discrete", ctypes.c_int32),
        ("temperature_celsius", ctypes.c_int32),
        ("used_bytes", ctypes.c_uint64),
        ("total_bytes", ctypes.c_uint64),
    ]


_NVIDIA_LOCK = Lock()
_AMD_LOCK = Lock()


def _safe_memory(used: int | None, total: int | None) -> tuple[int | None, int | None]:
    if used is None or total is None or total <= 0 or not 0 <= used <= total:
        return None, None
    return used, total


def _safe_temperature(value: int | None) -> int | None:
    if value is None or not 0 <= value <= 150:
        return None
    return value


def read_nvidia_gpus() -> tuple[GpuTelemetry, ...]:
    """Read NVIDIA telemetry through NVML, never through a command process."""
    try:
        import pynvml
    except Exception:
        return ()

    with _NVIDIA_LOCK:
        initialized = False
        try:
            pynvml.nvmlInit()
            initialized = True
            count = int(pynvml.nvmlDeviceGetCount())
            candidates: list[GpuTelemetry] = []
            for index in range(max(0, count)):
                handle = pynvml.nvmlDeviceGetHandleByIndex(index)
                memory = pynvml.nvmlDeviceGetMemoryInfo(handle)
                try:
                    temperature = int(
                        pynvml.nvmlDeviceGetTemperature(
                            handle, pynvml.NVML_TEMPERATURE_GPU
                        )
                    )
                except Exception:
                    temperature = None
                used, total = _safe_memory(
                    int(getattr(memory, "used", 0)),
                    int(getattr(memory, "total", 0)),
                )
                candidates.append(
                    GpuTelemetry(
                        vendor="nvidia",
                        provider_index=index,
                        is_discrete=True,
                        temperature_celsius=_safe_temperature(temperature),
                        used_bytes=used,
                        total_bytes=total,
                    )
                )
            return tuple(candidates)
        except Exception:
            return ()
        finally:
            if initialized:
                try:
                    pynvml.nvmlShutdown()
                except Exception:
                    pass


def _default_amd_bridge_path() -> Path:
    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root:
        return Path(bundle_root) / "app" / "native" / "streamdeck_gpu_bridge.dll"
    return (
        Path(__file__).resolve().parents[1]
        / "native"
        / "gpu_telemetry_bridge"
        / "bin"
        / "Release"
        / "net8.0"
        / "win-x64"
        / "publish"
        / "streamdeck_gpu_bridge.dll"
    )


def _default_amd_loader(path: str) -> object:
    if not hasattr(ctypes, "WinDLL"):
        raise OSError("AMD bridge requires Windows")
    return ctypes.WinDLL(path)  # type: ignore[attr-defined]


def read_amd_gpus(
    *,
    bridge_path: str | Path | None = None,
    loader: Callable[[str], object] | None = None,
    platform: str | None = None,
) -> tuple[GpuTelemetry, ...]:
    """Read Radeon telemetry from the fixed, in-process NativeAOT bridge.

    ``bridge_path`` and ``loader`` are dependency-injection seams for tests;
    production calls use the bundled path and ``ctypes.WinDLL`` only.
    """
    if (platform or sys.platform) != "win32":
        return ()

    path = Path(bridge_path) if bridge_path is not None else _default_amd_bridge_path()
    load = loader or _default_amd_loader

    with _AMD_LOCK:
        try:
            bridge = load(str(path))
            version = bridge.streamdeck_gpu_bridge_abi_version
            version.argtypes = []
            version.restype = ctypes.c_uint32
            if int(version()) != AMD_BRIDGE_ABI_VERSION:
                return ()

            read = bridge.streamdeck_read_amd_gpus
            read.argtypes = [
                ctypes.POINTER(AmdGpuTelemetryNative),
                ctypes.c_uint32,
            ]
            read.restype = ctypes.c_uint32
            required = int(read(None, 0))
            if required <= 0:
                return ()
            buffer = (AmdGpuTelemetryNative * required)()
            count = min(required, int(read(buffer, required)))
            result: list[GpuTelemetry] = []
            for record in buffer[:count]:
                if int(record.abi_version) != AMD_BRIDGE_ABI_VERSION:
                    continue
                is_discrete = (
                    True
                    if record.is_discrete == 1
                    else False
                    if record.is_discrete == 0
                    else None
                )
                temperature = (
                    None
                    if record.temperature_celsius == NATIVE_NA_TEMPERATURE
                    else _safe_temperature(int(record.temperature_celsius))
                )
                used, total = _safe_memory(
                    int(record.used_bytes), int(record.total_bytes)
                )
                result.append(
                    GpuTelemetry(
                        vendor="amd",
                        provider_index=int(record.provider_index),
                        is_discrete=is_discrete,
                        temperature_celsius=temperature,
                        used_bytes=used,
                        total_bytes=total,
                    )
                )
            return tuple(result)
        except Exception:
            return ()


@dataclass(frozen=True, slots=True)
class _FunctionGpuProvider:
    reader: Callable[[], tuple[GpuTelemetry, ...]]

    def read_candidates(self) -> tuple[GpuTelemetry, ...]:
        return self.reader()


DEFAULT_PROVIDERS: tuple[GpuTelemetryProvider, ...] = (
    _FunctionGpuProvider(read_nvidia_gpus),
    _FunctionGpuProvider(read_amd_gpus),
)


def select_primary_gpu(
    candidates: Sequence[GpuTelemetry],
) -> GpuTelemetry | None:
    def ranking(item: GpuTelemetry) -> tuple[int, int, int, str, int]:
        complete_memory = int(
            item.used_bytes is not None and item.total_bytes is not None
        )
        discrete = int(item.is_discrete is True)
        total = item.total_bytes if item.total_bytes is not None else -1
        return complete_memory, discrete, total, item.vendor, -item.provider_index

    return max(candidates, key=ranking, default=None)


def read_primary_gpu(
    providers: Sequence[GpuTelemetryProvider] = DEFAULT_PROVIDERS,
) -> GpuTelemetry | None:
    candidates: list[GpuTelemetry] = []
    for provider in providers:
        try:
            candidates.extend(provider.read_candidates())
        except Exception:
            continue
    return select_primary_gpu(candidates)


__all__ = [
    "AMD_BRIDGE_ABI_VERSION",
    "AmdGpuTelemetryNative",
    "GpuTelemetry",
    "GpuTelemetryProvider",
    "DEFAULT_PROVIDERS",
    "NATIVE_NA_TEMPERATURE",
    "read_amd_gpus",
    "read_nvidia_gpus",
    "read_primary_gpu",
    "select_primary_gpu",
]
