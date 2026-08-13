from __future__ import annotations

import ctypes
import gc
import math
import os
import sys
import time
from collections.abc import Callable
from ctypes import wintypes
from dataclasses import dataclass
from pathlib import Path
from threading import BoundedSemaphore
from typing import Literal, Protocol

from app.catalog import ApplicationCatalog
from app.gpu_telemetry import GpuTelemetry, read_primary_gpu
from app.schemas import (
    Action,
    ApplicationAction,
    HotkeyAction,
    KeyAction,
    MediaAction,
    SystemInfoAction,
    TextAction,
    UrlAction,
)

KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
INPUT_KEYBOARD = 1
_MODIFIER_VIRTUAL_KEYS = {
    "ctrl": 0x11,
    "alt": 0x12,
    "shift": 0x10,
    "win": 0x5B,
}
_NAMED_VIRTUAL_KEYS = {
    "BACKSPACE": 0x08,
    "TAB": 0x09,
    "ENTER": 0x0D,
    "ESC": 0x1B,
    "SPACE": 0x20,
    "PAGEUP": 0x21,
    "PAGEDOWN": 0x22,
    "END": 0x23,
    "HOME": 0x24,
    "LEFT": 0x25,
    "UP": 0x26,
    "RIGHT": 0x27,
    "DOWN": 0x28,
    "INSERT": 0x2D,
    "PRINTSCREEN": 0x2C,
    "DELETE": 0x2E,
}
_ALPHANUMERIC_VIRTUAL_KEYS = {
    character: ord(character) for character in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
}
_FUNCTION_VIRTUAL_KEYS = {f"F{number}": 0x6F + number for number in range(1, 25)}
_VIRTUAL_KEYS = {
    **_ALPHANUMERIC_VIRTUAL_KEYS,
    **_FUNCTION_VIRTUAL_KEYS,
    **_NAMED_VIRTUAL_KEYS,
}
_MEDIA_VIRTUAL_KEYS = {
    "play_pause": 0xB3,
    "next": 0xB0,
    "previous": 0xB1,
    "stop": 0xB2,
    "volume_up": 0xAF,
    "volume_down": 0xAE,
    "mute": 0xAD,
}


@dataclass(frozen=True, slots=True)
class ActionExecutionResult:
    status: Literal["completed", "rejected"]
    message: str


class ActionExecutionRejected(RuntimeError):
    """A safe, user-facing reason why a closed action was not executed."""

    def __init__(self, public_message: str) -> None:
        super().__init__(public_message)
        self.public_message = public_message


class RecordingActionExecutor:
    """Deterministic executor for isolated protocol/UI tests.

    It validates the same Pydantic action objects as production but never emits
    keyboard input, opens an application, or touches the clipboard. The
    recorded labels are intentionally limited to the closed action vocabulary.
    """

    def __init__(self) -> None:
        self.actions: list[Action] = []

    def execute(self, action: Action) -> ActionExecutionResult:
        self.actions.append(action)
        return ActionExecutionResult(
            "completed",
            f"Recorded {_recording_label(action)}",
        )


def _recording_label(action: Action) -> str:
    if isinstance(action, MediaAction):
        return f"media/{action.command}"
    if isinstance(action, KeyAction):
        return f"key/{action.key}"
    if isinstance(action, ApplicationAction):
        return f"application/{action.app_id}"
    if isinstance(action, SystemInfoAction):
        return f"system_info/{action.target}"
    if isinstance(action, HotkeyAction):
        return "hotkey/closed"
    if isinstance(action, TextAction):
        return "text/closed"
    if isinstance(action, UrlAction):
        return "url/https"
    return "action/closed"


class HotkeyAdapter(Protocol):
    def execute(self, action: HotkeyAction) -> None: ...


class KeyAdapter(Protocol):
    def execute(self, action: KeyAction) -> None: ...


class MediaAdapter(Protocol):
    def execute(self, action: MediaAction) -> None: ...


class TextAdapter(Protocol):
    def execute(self, action: TextAction) -> None: ...


class UrlAdapter(Protocol):
    def execute(self, action: UrlAction) -> None: ...


class SystemInfoAdapter(Protocol):
    def execute(self, action: SystemInfoAction) -> str: ...


class ActionExecutor(Protocol):
    def execute(self, action: Action) -> ActionExecutionResult: ...


class WindowsHotkeyAdapter:
    """Send a closed, validated virtual-key sequence without invoking a shell."""

    def __init__(self, *, emit_key: Callable[[int, bool], None] | None = None) -> None:
        self._emit_key = emit_key or _emit_windows_key

    def execute(self, action: HotkeyAction) -> None:
        modifier_keys = tuple(
            _MODIFIER_VIRTUAL_KEYS[modifier] for modifier in action.modifiers
        )
        virtual_key = _virtual_key_for(action.key)
        pressed_modifiers: list[int] = []
        primary_pressed = False
        try:
            for modifier_key in modifier_keys:
                self._emit_key(modifier_key, False)
                pressed_modifiers.append(modifier_key)
            self._emit_key(virtual_key, False)
            primary_pressed = True
        except Exception as exc:
            raise ActionExecutionRejected("Action could not be completed") from exc
        finally:
            if primary_pressed:
                _release_key_safely(self._emit_key, virtual_key)
            for modifier_key in reversed(pressed_modifiers):
                _release_key_safely(self._emit_key, modifier_key)


class WindowsKeyAdapter:
    """Send one closed, validated virtual-key tap without modifiers."""

    def __init__(self, *, emit_key: Callable[[int, bool], None] | None = None) -> None:
        self._emit_key = emit_key or _emit_windows_key

    def execute(self, action: KeyAction) -> None:
        virtual_key = _key_virtual_key_for(action.key)
        primary_pressed = False
        try:
            self._emit_key(virtual_key, False)
            primary_pressed = True
        except Exception as exc:
            raise ActionExecutionRejected("Action could not be completed") from exc
        finally:
            if primary_pressed:
                _release_key_safely(self._emit_key, virtual_key)


class WindowsMediaAdapter:
    """Send one closed, validated media-key tap without arbitrary payloads."""

    def __init__(self, *, emit_key: Callable[[int, bool], None] | None = None) -> None:
        self._emit_key = emit_key or _emit_windows_key

    def execute(self, action: MediaAction) -> None:
        virtual_key = _media_virtual_key_for(action.command)
        primary_pressed = False
        try:
            self._emit_key(virtual_key, False)
            primary_pressed = True
        except Exception as exc:
            raise ActionExecutionRejected("Action could not be completed") from exc
        finally:
            if primary_pressed:
                _release_key_safely(self._emit_key, virtual_key)


class _MemoryStatusEx(ctypes.Structure):
    """Win32 ``MEMORYSTATUSEX`` with 64-bit physical-memory counters."""

    _fields_ = [
        ("dwLength", ctypes.c_ulong),
        ("dwMemoryLoad", ctypes.c_ulong),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


class WindowsSystemInfoAdapter:
    """Read a small, closed set of Windows telemetry without shell access.

    ``system_info`` is deliberately not a generic diagnostics capability: the
    validated action selects only CPU or physical-memory telemetry. CPU usage is
    sampled from two ``GetSystemTimes`` snapshots; temperature is best-effort
    WMI data and is reported as ``N/A`` when firmware does not expose a thermal
    zone. Values outside a conservative -50..150 °C plausibility range are also
    reported as unavailable. ACPI zones do not necessarily represent the CPU
    package. No client-supplied command, WMI query, path, or process is accepted.
    """

    _BYTES_PER_GIBIBYTE = 1024**3

    def __init__(
        self,
        *,
        read_system_times: Callable[[], tuple[int, int, int]] | None = None,
        read_memory_status: Callable[[], tuple[int, int, int]] | None = None,
        read_thermal_zone_temperatures: Callable[[], list[int | float]] | None = None,
        read_gpu_telemetry: Callable[[], GpuTelemetry | None] | None = None,
        sleep: Callable[[float], None] | None = None,
        sample_interval_seconds: float = 0.1,
        max_concurrent_executions: int = 2,
    ) -> None:
        if sample_interval_seconds < 0:
            raise ValueError("sample_interval_seconds must not be negative")
        if max_concurrent_executions < 1:
            raise ValueError("max_concurrent_executions must be positive")
        self._read_system_times = read_system_times or _read_windows_system_times
        self._read_memory_status = read_memory_status or _read_windows_memory_status
        self._read_thermal_zone_temperatures = (
            read_thermal_zone_temperatures or _read_windows_thermal_zone_temperatures
        )
        self._read_gpu_telemetry = read_gpu_telemetry or read_primary_gpu
        self._sleep = sleep or time.sleep
        self._sample_interval_seconds = sample_interval_seconds
        self._execution_slots = BoundedSemaphore(max_concurrent_executions)

    def execute(self, action: SystemInfoAction) -> str:
        if not self._execution_slots.acquire(blocking=False):
            raise ActionExecutionRejected("System information is busy")
        try:
            try:
                if action.target == "cpu":
                    return self._cpu_message()
                if action.target == "memory":
                    return self._memory_message()
                if action.target == "gpu":
                    return self._gpu_message()
            except ActionExecutionRejected:
                raise
            except Exception as exc:
                raise ActionExecutionRejected(
                    "System information could not be read"
                ) from exc
            raise ActionExecutionRejected("System information target is not supported")
        finally:
            self._execution_slots.release()

    def _cpu_message(self) -> str:
        first_idle, first_kernel, first_user = self._read_system_times()
        self._sleep(self._sample_interval_seconds)
        second_idle, second_kernel, second_user = self._read_system_times()

        first_total = first_kernel + first_user
        second_total = second_kernel + second_user
        total_delta = second_total - first_total
        idle_delta = second_idle - first_idle
        if total_delta <= 0 or idle_delta < 0:
            raise ActionExecutionRejected("System information could not be read")

        busy_delta = min(total_delta, max(0, total_delta - idle_delta))
        cpu_percent = round((busy_delta * 100) / total_delta)
        temperature = self._best_effort_temperature_celsius()
        temperature_label = f"{temperature}°C" if temperature is not None else "N/A"
        return f"CPU: {cpu_percent}% | {temperature_label}"

    def _memory_message(self) -> str:
        memory_percent, total_bytes, available_bytes = self._read_memory_status()
        if total_bytes <= 0 or not 0 <= available_bytes <= total_bytes:
            raise ActionExecutionRejected("System information could not be read")
        memory_percent = min(100, max(0, memory_percent))
        available_gib = available_bytes / self._BYTES_PER_GIBIBYTE
        total_gib = total_bytes / self._BYTES_PER_GIBIBYTE
        return f"RAM: {memory_percent}% ({available_gib:.1f}/{total_gib:.1f} GB)"

    def _gpu_message(self) -> str:
        telemetry = self._read_gpu_telemetry()
        if telemetry is None:
            return "GPU: N/A | VRAM: N/A"

        temperature = telemetry.temperature_celsius
        temperature_label = (
            f"{temperature}°C"
            if temperature is not None and 0 <= temperature <= 150
            else "N/A"
        )
        used = telemetry.used_bytes
        total = telemetry.total_bytes
        if used is None or total is None or total <= 0 or not 0 <= used <= total:
            vram_label = "N/A"
        else:
            percent = min(100, max(0, round(used * 100 / total)))
            vram_label = (
                f"{used / self._BYTES_PER_GIBIBYTE:.1f}/"
                f"{total / self._BYTES_PER_GIBIBYTE:.1f} GB ({percent}%)"
            )
        return f"GPU: {temperature_label} | VRAM: {vram_label}"

    def _best_effort_temperature_celsius(self) -> int | None:
        try:
            raw_temperatures = self._read_thermal_zone_temperatures()
        except Exception:
            return None

        celsius_values = [
            celsius
            for temperature in raw_temperatures
            if isinstance(temperature, (int, float))
            and math.isfinite(temperature)
            and temperature > 0
            and -50 <= (celsius := round(temperature / 10 - 273.15)) <= 150
        ]
        return max(celsius_values, default=None)


def _read_windows_system_times() -> tuple[int, int, int]:
    """Return idle, kernel, and user time in 100-nanosecond Win32 ticks."""

    if sys.platform != "win32":
        raise ActionExecutionRejected("System telemetry requires Windows")

    idle = wintypes.FILETIME()
    kernel = wintypes.FILETIME()
    user = wintypes.FILETIME()
    kernel32 = ctypes.windll.kernel32
    kernel32.GetSystemTimes.argtypes = [
        ctypes.POINTER(wintypes.FILETIME),
        ctypes.POINTER(wintypes.FILETIME),
        ctypes.POINTER(wintypes.FILETIME),
    ]
    kernel32.GetSystemTimes.restype = wintypes.BOOL
    if not kernel32.GetSystemTimes(
        ctypes.byref(idle),
        ctypes.byref(kernel),
        ctypes.byref(user),
    ):
        raise OSError(ctypes.get_last_error(), "GetSystemTimes failed")
    return tuple(
        (file_time.dwHighDateTime << 32) | file_time.dwLowDateTime
        for file_time in (idle, kernel, user)
    )


def _read_windows_memory_status() -> tuple[int, int, int]:
    """Return percentage used, total physical bytes, and available physical bytes."""

    if sys.platform != "win32":
        raise ActionExecutionRejected("System telemetry requires Windows")

    status = _MemoryStatusEx()
    status.dwLength = ctypes.sizeof(_MemoryStatusEx)
    kernel32 = ctypes.windll.kernel32
    kernel32.GlobalMemoryStatusEx.argtypes = [ctypes.POINTER(_MemoryStatusEx)]
    kernel32.GlobalMemoryStatusEx.restype = wintypes.BOOL
    if not kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        raise OSError(ctypes.get_last_error(), "GlobalMemoryStatusEx failed")
    total_bytes = int(status.ullTotalPhys)
    available_bytes = int(status.ullAvailPhys)
    return int(status.dwMemoryLoad), total_bytes, available_bytes


def _read_windows_thermal_zone_temperatures() -> list[int | float]:
    """Read fixed WMI thermal-zone values in tenths of Kelvin when available."""

    if sys.platform != "win32":
        return []
    try:
        import pythoncom
        import win32com.client
    except Exception:
        return []

    # Starlette runs action execution in a worker thread. COM must be
    # initialized in that same thread before the WMI client is created.
    pythoncom.CoInitialize()
    try:
        temperatures = _query_windows_thermal_zone_temperatures(win32com.client)
        # On unsupported firmware, WMI can leave cyclic exception wrappers
        # holding COM references. Collect them before balancing CoInitialize.
        gc.collect()
        return temperatures
    finally:
        pythoncom.CoUninitialize()


def _query_windows_thermal_zone_temperatures(wmi_module: object) -> list[int | float]:
    """Keep WMI exceptions scoped so COM wrappers die before CoUninitialize."""

    try:
        get_object = getattr(wmi_module, "GetObject")
        connection = get_object(
            r"winmgmts:{impersonationLevel=impersonate}!\\.\root\WMI"
        )
        zones = connection.ExecQuery(
            "SELECT CurrentTemperature FROM MSAcpi_ThermalZoneTemperature"
        )
        return [
            temperature
            for zone in zones
            if (temperature := getattr(zone, "CurrentTemperature", None)) is not None
        ]
    except Exception:
        return []


class WindowsTextAdapter:
    """Type validated text through Win32 Unicode input, without a shell."""

    def __init__(self, *, emit_text: Callable[[str], None] | None = None) -> None:
        self._emit_text = emit_text or _emit_windows_text

    def execute(self, action: TextAction) -> None:
        try:
            self._emit_text(action.text)
        except ActionExecutionRejected:
            raise
        except Exception as exc:
            raise ActionExecutionRejected("Action could not be completed") from exc


class WindowsUrlAdapter:
    """Open a validated HTTPS URL through the Windows default browser."""

    def __init__(self, *, open_url: Callable[[str], None] | None = None) -> None:
        self._open_url = open_url or _open_windows_url

    def execute(self, action: UrlAction) -> None:
        try:
            self._open_url(action.url)
        except ActionExecutionRejected:
            raise
        except Exception as exc:
            raise ActionExecutionRejected("Action could not be completed") from exc


def default_application_catalog() -> ApplicationCatalog:
    """Catalog of applications the server may launch for ``application`` actions.

    Entries are fixed at build time and never read from the client. Only the
    executable named here can be launched; unknown ids are rejected.
    """
    return ApplicationCatalog(
        {
            "chrome": {
                "display_name": "Google Chrome",
                "executable": "chrome.exe",
            },
        }
    )


# Keep the private name available to older internal callers while exposing the
# stable public factory used by tests and the production registry.
_default_application_catalog = default_application_catalog


def _open_windows_application(executable: str) -> None:
    if sys.platform != "win32":
        raise ActionExecutionRejected("Application execution requires Windows")
    if Path(executable).name.lower() != executable.lower():
        raise ActionExecutionRejected("Application executable is not available")
    candidates_by_name = {
        "chrome.exe": (
            Path(os.environ.get("PROGRAMFILES", ""))
            / "Google/Chrome/Application/chrome.exe",
            Path(os.environ.get("PROGRAMFILES(X86)", ""))
            / "Google/Chrome/Application/chrome.exe",
            Path(os.environ.get("LOCALAPPDATA", ""))
            / "Google/Chrome/Application/chrome.exe",
        ),
    }
    executable_path = next(
        (
            candidate.resolve()
            for candidate in candidates_by_name.get(executable.lower(), ())
            if candidate.is_absolute() and candidate.is_file()
        ),
        None,
    )
    if executable_path is None:
        raise ActionExecutionRejected("Application executable is not available")
    result = ctypes.windll.shell32.ShellExecuteW(
        None,
        "open",
        str(executable_path),
        None,
        None,
        1,
    )
    if result <= 32:
        raise ActionExecutionRejected("Application could not be started")


class WindowsApplicationAdapter:
    """Launch a Windows application by id resolved through a closed catalog."""

    def __init__(
        self,
        catalog: ApplicationCatalog | None = None,
        *,
        launcher: Callable[[str], None] | None = None,
    ) -> None:
        self._catalog = catalog or default_application_catalog()
        self._launcher = launcher or _open_windows_application

    def execute(self, action: ApplicationAction) -> None:
        entry = self._catalog.get(action.app_id)
        if entry is None:
            raise ActionExecutionRejected("Application is not enabled")
        try:
            self._launcher(entry.executable)
        except ActionExecutionRejected:
            raise
        except Exception as exc:
            raise ActionExecutionRejected("Action could not be completed") from exc


class _KeyboardInput(ctypes.Structure):
    _fields_ = [
        ("wVk", ctypes.c_ushort),
        ("wScan", ctypes.c_ushort),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.c_void_p),
    ]


class _InputUnion(ctypes.Union):
    _fields_ = [
        ("ki", _KeyboardInput),
        (
            "_reserved",
            ctypes.c_ubyte * (32 if ctypes.sizeof(ctypes.c_void_p) == 8 else 24),
        ),
    ]


class _Input(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_ulong),
        ("union", _InputUnion),
    ]


def _emit_windows_text(text: str) -> None:
    if sys.platform != "win32":
        raise ActionExecutionRejected("Text execution requires Windows")
    encoded_text = text.encode("utf-16-le", errors="surrogatepass")
    code_units = [
        int.from_bytes(encoded_text[index : index + 2], byteorder="little")
        for index in range(0, len(encoded_text), 2)
    ]
    inputs = (_Input * (len(code_units) * 2))()
    for index, code_unit in enumerate(code_units):
        down = inputs[index * 2]
        down.type = INPUT_KEYBOARD
        down.union.ki = _KeyboardInput(
            wVk=0,
            wScan=code_unit,
            dwFlags=KEYEVENTF_UNICODE,
            time=0,
            dwExtraInfo=None,
        )
        up = inputs[index * 2 + 1]
        up.type = INPUT_KEYBOARD
        up.union.ki = _KeyboardInput(
            wVk=0,
            wScan=code_unit,
            dwFlags=KEYEVENTF_UNICODE | KEYEVENTF_KEYUP,
            time=0,
            dwExtraInfo=None,
        )
    sent = ctypes.windll.user32.SendInput(
        len(inputs),
        ctypes.byref(inputs),
        ctypes.sizeof(_Input),
    )
    if sent != len(inputs):
        raise ActionExecutionRejected("Text input was not accepted")


def _open_windows_url(url: str) -> None:
    if sys.platform != "win32":
        raise ActionExecutionRejected("URL execution requires Windows")
    result = ctypes.windll.shell32.ShellExecuteW(
        None,
        "open",
        url,
        None,
        None,
        1,
    )
    if result <= 32:
        raise ActionExecutionRejected("URL could not be opened")


def _virtual_key_for(key: str) -> int:
    virtual_key = _VIRTUAL_KEYS.get(key.upper())
    if virtual_key is None:
        raise ActionExecutionRejected("Hotkey is not supported")
    return virtual_key


def _key_virtual_key_for(key: str) -> int:
    virtual_key = _VIRTUAL_KEYS.get(key.upper())
    if virtual_key is None:
        raise ActionExecutionRejected("Key is not supported")
    return virtual_key


def _media_virtual_key_for(command: str) -> int:
    virtual_key = _MEDIA_VIRTUAL_KEYS.get(command)
    if virtual_key is None:
        raise ActionExecutionRejected("Media command is not supported")
    return virtual_key


def _emit_windows_key(virtual_key: int, key_up: bool) -> None:
    if sys.platform != "win32":
        raise ActionExecutionRejected("Hotkey execution requires Windows")
    flags = KEYEVENTF_KEYUP if key_up else 0
    ctypes.windll.user32.keybd_event(virtual_key, 0, flags, 0)


def _release_key_safely(
    emit_key: Callable[[int, bool], None], virtual_key: int
) -> None:
    try:
        emit_key(virtual_key, True)
    except Exception:
        # A best-effort release cannot expose adapter internals to the client.
        return


class ActionRegistry:
    """Registry of explicitly enabled action types for this server version."""

    def __init__(
        self,
        *,
        hotkey_adapter: HotkeyAdapter | None = None,
        key_adapter: KeyAdapter | None = None,
        media_adapter: MediaAdapter | None = None,
        text_adapter: TextAdapter | None = None,
        url_adapter: UrlAdapter | None = None,
        system_info_adapter: SystemInfoAdapter | None = None,
        application_catalog: ApplicationCatalog | None = None,
        application_adapter: WindowsApplicationAdapter | None = None,
    ) -> None:
        self._hotkey_adapter = hotkey_adapter or WindowsHotkeyAdapter()
        self._key_adapter = key_adapter or WindowsKeyAdapter()
        self._media_adapter = media_adapter or WindowsMediaAdapter()
        self._text_adapter = text_adapter or WindowsTextAdapter()
        self._url_adapter = url_adapter or WindowsUrlAdapter()
        self._system_info_adapter = system_info_adapter or WindowsSystemInfoAdapter()
        self._application_adapter = application_adapter or WindowsApplicationAdapter(
            catalog=application_catalog
        )

    def execute(self, action: Action) -> ActionExecutionResult:
        if isinstance(action, HotkeyAction):
            self._hotkey_adapter.execute(action)
            return ActionExecutionResult(status="completed", message="Action completed")
        if isinstance(action, KeyAction):
            self._key_adapter.execute(action)
            return ActionExecutionResult(status="completed", message="Action completed")
        if isinstance(action, MediaAction):
            self._media_adapter.execute(action)
            return ActionExecutionResult(status="completed", message="Action completed")
        if isinstance(action, TextAction):
            self._text_adapter.execute(action)
            return ActionExecutionResult(status="completed", message="Action completed")
        if isinstance(action, UrlAction):
            self._url_adapter.execute(action)
            return ActionExecutionResult(status="completed", message="Action completed")
        if isinstance(action, ApplicationAction):
            self._application_adapter.execute(action)
            return ActionExecutionResult(status="completed", message="Action completed")
        if isinstance(action, SystemInfoAction):
            return ActionExecutionResult(
                status="completed",
                message=self._system_info_adapter.execute(action),
            )
        raise ActionExecutionRejected("Action type is not enabled")


__all__ = [
    "ActionExecutionRejected",
    "ActionExecutionResult",
    "ActionExecutor",
    "ActionRegistry",
    "RecordingActionExecutor",
    "KeyAdapter",
    "MediaAdapter",
    "SystemInfoAdapter",
    "TextAdapter",
    "UrlAdapter",
    "WindowsApplicationAdapter",
    "WindowsHotkeyAdapter",
    "WindowsKeyAdapter",
    "WindowsMediaAdapter",
    "WindowsSystemInfoAdapter",
    "WindowsTextAdapter",
    "WindowsUrlAdapter",
]
