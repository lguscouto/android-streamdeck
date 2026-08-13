from __future__ import annotations

import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest

import app.actions as actions_module
from app.actions import (
    ActionExecutionRejected,
    ActionRegistry,
    RecordingActionExecutor,
    WindowsHotkeyAdapter,
    WindowsKeyAdapter,
    WindowsMediaAdapter,
    WindowsTextAdapter,
    WindowsUrlAdapter,
)
from app.schemas import (
    ApplicationAction,
    HotkeyAction,
    KeyAction,
    MediaAction,
    SystemInfoAction,
    TextAction,
    UrlAction,
)


class RecordingKeyEmitter:
    def __init__(self) -> None:
        self.events: list[tuple[int, bool]] = []

    def __call__(self, virtual_key: int, key_up: bool) -> None:
        self.events.append((virtual_key, key_up))


def test_recording_action_executor_records_without_emitting_desktop_input() -> None:
    executor = RecordingActionExecutor()
    action = ApplicationAction(type="application", app_id="chrome")

    result = executor.execute(action)

    assert result.status == "completed"
    assert result.message == "Recorded application/chrome"
    assert executor.actions == [action]


def test_windows_key_adapter_emits_one_allowed_key_without_modifier() -> None:
    emitter = RecordingKeyEmitter()
    adapter = WindowsKeyAdapter(emit_key=emitter)

    adapter.execute(KeyAction(type="key", key="A"))

    assert emitter.events == [
        (0x41, False),  # A down
        (0x41, True),  # A up
    ]


def test_windows_key_adapter_emits_printscreen_down_and_up() -> None:
    emitter = RecordingKeyEmitter()
    adapter = WindowsKeyAdapter(emit_key=emitter)

    adapter.execute(KeyAction(type="key", key="PRINTSCREEN"))

    assert emitter.events == [
        (0x2C, False),  # VK_SNAPSHOT down
        (0x2C, True),  # VK_SNAPSHOT up
    ]


def test_windows_key_adapter_rejects_unknown_named_key() -> None:
    adapter = WindowsKeyAdapter(emit_key=RecordingKeyEmitter())

    with pytest.raises(ActionExecutionRejected) as error:
        adapter.execute(KeyAction(type="key", key="NOT_A_REAL_KEY"))

    assert error.value.public_message == "Key is not supported"


def test_windows_media_adapter_emits_one_allowed_media_command() -> None:
    emitter = RecordingKeyEmitter()
    adapter = WindowsMediaAdapter(emit_key=emitter)

    adapter.execute(MediaAction(type="media", command="play_pause"))

    assert emitter.events == [
        (0xB3, False),  # Play/pause down
        (0xB3, True),  # Play/pause up
    ]


def test_windows_text_adapter_emits_only_validated_text() -> None:
    emitted: list[str] = []
    adapter = WindowsTextAdapter(emit_text=emitted.append)

    adapter.execute(TextAction(type="text", text="Olá Stream Deck"))

    assert emitted == ["Olá Stream Deck"]


def test_windows_url_adapter_opens_only_validated_https_url() -> None:
    opened: list[str] = []
    adapter = WindowsUrlAdapter(open_url=opened.append)

    adapter.execute(UrlAction(type="url", url="https://example.com/docs"))

    assert opened == ["https://example.com/docs"]


def test_action_registry_executes_text_and_url_adapters() -> None:
    emitted: list[str] = []
    opened: list[str] = []
    registry = ActionRegistry(
        text_adapter=WindowsTextAdapter(emit_text=emitted.append),
        url_adapter=WindowsUrlAdapter(open_url=opened.append),
    )

    text_result = registry.execute(TextAction(type="text", text="hello"))
    url_result = registry.execute(UrlAction(type="url", url="https://example.com"))

    assert text_result.status == "completed"
    assert url_result.status == "completed"
    assert emitted == ["hello"]
    assert opened == ["https://example.com"]


def test_windows_hotkey_adapter_emits_closed_modifier_and_key_sequence() -> None:
    emitter = RecordingKeyEmitter()
    adapter = WindowsHotkeyAdapter(emit_key=emitter)

    adapter.execute(
        HotkeyAction(
            type="hotkey",
            modifiers=["ctrl", "shift"],
            key="S",
        )
    )

    assert emitter.events == [
        (0x11, False),  # Ctrl down
        (0x10, False),  # Shift down
        (0x53, False),  # S down
        (0x53, True),  # S up
        (0x10, True),  # Shift up
        (0x11, True),  # Ctrl up
    ]


def test_action_registry_executes_only_hotkey_adapter() -> None:
    emitter = RecordingKeyEmitter()
    registry = ActionRegistry(hotkey_adapter=WindowsHotkeyAdapter(emit_key=emitter))

    result = registry.execute(HotkeyAction(type="hotkey", modifiers=["ctrl"], key="S"))

    assert result.status == "completed"
    assert result.message == "Action completed"
    assert emitter.events == [
        (0x11, False),
        (0x53, False),
        (0x53, True),
        (0x11, True),
    ]


def test_action_registry_executes_key_adapter() -> None:
    emitter = RecordingKeyEmitter()
    registry = ActionRegistry(key_adapter=WindowsKeyAdapter(emit_key=emitter))

    result = registry.execute(KeyAction(type="key", key="ENTER"))

    assert result.status == "completed"
    assert result.message == "Action completed"
    assert emitter.events == [
        (0x0D, False),
        (0x0D, True),
    ]


def test_action_registry_executes_media_adapter() -> None:
    emitter = RecordingKeyEmitter()
    registry = ActionRegistry(media_adapter=WindowsMediaAdapter(emit_key=emitter))

    result = registry.execute(MediaAction(type="media", command="mute"))

    assert result.status == "completed"
    assert result.message == "Action completed"
    assert emitter.events == [
        (0xAD, False),
        (0xAD, True),
    ]


def test_action_registry_rejects_action_without_an_explicit_adapter() -> None:
    registry = ActionRegistry()

    # The default catalog contains only the fixed Chrome entry; an unknown
    # application id is still rejected with the adapter's user-facing message.
    with pytest.raises(ActionExecutionRejected) as error:
        registry.execute(ApplicationAction(type="application", app_id="not-enabled"))

    assert error.value.public_message == "Application is not enabled"


def test_windows_hotkey_adapter_rejects_key_outside_closed_virtual_key_map() -> None:
    adapter = WindowsHotkeyAdapter(emit_key=RecordingKeyEmitter())

    with pytest.raises(ActionExecutionRejected) as error:
        adapter.execute(
            HotkeyAction(type="hotkey", modifiers=["ctrl"], key="NotConfigured")
        )

    assert error.value.public_message == "Hotkey is not supported"


def test_windows_system_info_adapter_formats_cpu_temperature_and_memory() -> None:
    system_times = iter(
        [
            (100, 200, 300),
            (120, 260, 380),
        ]
    )
    gibibyte = 1024**3
    adapter = actions_module.WindowsSystemInfoAdapter(
        read_system_times=lambda: next(system_times),
        # The third field is available physical memory, not used memory.
        read_memory_status=lambda: (47, 16 * gibibyte, int(8.5 * gibibyte)),
        read_thermal_zone_temperatures=lambda: [3_082, 3_182],
        sleep=lambda _seconds: None,
    )

    cpu = adapter.execute(SystemInfoAction(type="system_info", target="cpu"))
    memory = adapter.execute(SystemInfoAction(type="system_info", target="memory"))

    assert cpu == "CPU: 86% | 45°C"
    assert memory == "RAM: 47% (8.5/16.0 GB)"


def test_windows_system_info_adapter_rejects_when_telemetry_is_already_running() -> (
    None
):
    execution_started = threading.Event()
    release_execution = threading.Event()
    system_times = iter(
        [
            (100, 200, 300),
            (150, 250, 350),
        ]
    )

    def blocking_sleep(_seconds: float) -> None:
        execution_started.set()
        assert release_execution.wait(timeout=2)

    adapter = actions_module.WindowsSystemInfoAdapter(
        read_system_times=lambda: next(system_times),
        read_memory_status=lambda: (47, 16 * 1024**3, 8 * 1024**3),
        read_thermal_zone_temperatures=lambda: [],
        sleep=blocking_sleep,
        max_concurrent_executions=1,
    )

    with ThreadPoolExecutor(max_workers=1) as executor:
        running = executor.submit(
            adapter.execute,
            SystemInfoAction(type="system_info", target="cpu"),
        )
        assert execution_started.wait(timeout=2)

        with pytest.raises(ActionExecutionRejected) as error:
            adapter.execute(SystemInfoAction(type="system_info", target="memory"))

        assert error.value.public_message == "System information is busy"
        release_execution.set()
        assert running.result(timeout=2) == "CPU: 50% | N/A"


def test_windows_system_info_adapter_uses_na_when_no_thermal_zone_is_exposed() -> None:
    system_times = iter(
        [
            (100, 200, 300),
            (150, 250, 350),
        ]
    )
    adapter = actions_module.WindowsSystemInfoAdapter(
        read_system_times=lambda: next(system_times),
        read_memory_status=lambda: (0, 1, 1),
        read_thermal_zone_temperatures=lambda: [],
        sleep=lambda _seconds: None,
    )

    cpu = adapter.execute(SystemInfoAction(type="system_info", target="cpu"))

    assert cpu == "CPU: 50% | N/A"


def test_windows_system_info_adapter_ignores_invalid_thermal_values() -> None:
    system_times = iter(
        [
            (100, 200, 300),
            (150, 250, 350),
        ]
    )
    adapter = actions_module.WindowsSystemInfoAdapter(
        read_system_times=lambda: next(system_times),
        read_memory_status=lambda: (0, 1, 1),
        read_thermal_zone_temperatures=lambda: [float("nan"), float("inf"), 0, -1],
        sleep=lambda _seconds: None,
    )

    cpu = adapter.execute(SystemInfoAction(type="system_info", target="cpu"))

    assert cpu == "CPU: 50% | N/A"


def test_windows_system_info_adapter_ignores_implausible_thermal_values() -> None:
    system_times = iter(
        [
            (100, 200, 300),
            (150, 250, 350),
        ]
    )
    adapter = actions_module.WindowsSystemInfoAdapter(
        read_system_times=lambda: next(system_times),
        read_memory_status=lambda: (0, 1, 1),
        # 5000 tenths Kelvin is about 227 °C and is not credible host telemetry.
        read_thermal_zone_temperatures=lambda: [5_000],
        sleep=lambda _seconds: None,
    )

    cpu = adapter.execute(SystemInfoAction(type="system_info", target="cpu"))

    assert cpu == "CPU: 50% | N/A"


def test_windows_thermal_reader_initializes_com_inside_worker_thread(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, str]] = []
    com_state = threading.local()

    def co_initialize() -> None:
        com_state.initialized = True
        calls.append(("com", "initialize"))

    def co_uninitialize() -> None:
        assert getattr(com_state, "initialized", False)
        calls.append(("com", "uninitialize"))
        com_state.initialized = False

    def query(_module: object) -> list[int]:
        assert getattr(com_state, "initialized", False)
        calls.append(("wmi", "query"))
        return [3_182]

    monkeypatch.setattr(actions_module.sys, "platform", "win32")
    monkeypatch.setitem(
        sys.modules,
        "pythoncom",
        SimpleNamespace(CoInitialize=co_initialize, CoUninitialize=co_uninitialize),
    )
    client_module = SimpleNamespace()
    monkeypatch.setitem(
        sys.modules,
        "win32com",
        SimpleNamespace(client=client_module),
    )
    monkeypatch.setitem(sys.modules, "win32com.client", client_module)
    monkeypatch.setattr(
        actions_module,
        "_query_windows_thermal_zone_temperatures",
        query,
    )
    monkeypatch.setattr(
        actions_module.gc,
        "collect",
        lambda: calls.append(("gc", "collect")),
    )

    with ThreadPoolExecutor(max_workers=1) as executor:
        result = executor.submit(
            actions_module._read_windows_thermal_zone_temperatures
        ).result()

    assert result == [3_182]
    assert calls == [
        ("com", "initialize"),
        ("wmi", "query"),
        ("gc", "collect"),
        ("com", "uninitialize"),
    ]


def test_windows_thermal_query_uses_only_fixed_acpi_namespace_and_class() -> None:
    calls: list[tuple[str, str]] = []

    class FixedWmiConnection:
        def ExecQuery(self, query: str) -> list[SimpleNamespace]:
            calls.append(("query", query))
            return [SimpleNamespace(CurrentTemperature=3_182)]

    def connect(moniker: str) -> FixedWmiConnection:
        calls.append(("moniker", moniker))
        return FixedWmiConnection()

    result = actions_module._query_windows_thermal_zone_temperatures(
        SimpleNamespace(GetObject=connect)
    )

    assert result == [3_182]
    assert calls == [
        (
            "moniker",
            r"winmgmts:{impersonationLevel=impersonate}!\\.\root\WMI",
        ),
        (
            "query",
            "SELECT CurrentTemperature FROM MSAcpi_ThermalZoneTemperature",
        ),
    ]


def test_windows_thermal_reader_balances_com_when_query_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def fail_query(_module: object) -> list[int]:
        calls.append("query")
        raise RuntimeError("synthetic WMI failure")

    monkeypatch.setattr(actions_module.sys, "platform", "win32")
    monkeypatch.setitem(
        sys.modules,
        "pythoncom",
        SimpleNamespace(
            CoInitialize=lambda: calls.append("initialize"),
            CoUninitialize=lambda: calls.append("uninitialize"),
        ),
    )
    client_module = SimpleNamespace()
    monkeypatch.setitem(
        sys.modules,
        "win32com",
        SimpleNamespace(client=client_module),
    )
    monkeypatch.setitem(sys.modules, "win32com.client", client_module)
    monkeypatch.setattr(
        actions_module,
        "_query_windows_thermal_zone_temperatures",
        fail_query,
    )

    with pytest.raises(RuntimeError, match="synthetic WMI failure"):
        actions_module._read_windows_thermal_zone_temperatures()

    assert calls == ["initialize", "query", "uninitialize"]


def test_action_registry_returns_formatted_system_info_message() -> None:
    class RecordingSystemInfoAdapter:
        def __init__(self) -> None:
            self.actions: list[object] = []

        def execute(self, action: object) -> str:
            self.actions.append(action)
            return "RAM: 47% (8.5/16.0 GB)"

    adapter = RecordingSystemInfoAdapter()
    registry = ActionRegistry(system_info_adapter=adapter)
    action = SystemInfoAction(type="system_info", target="memory")

    result = registry.execute(action)

    assert result.status == "completed"
    assert result.message == "RAM: 47% (8.5/16.0 GB)"
    assert adapter.actions == [action]


@pytest.mark.parametrize(
    ("telemetry", "expected"),
    [
        (
            actions_module.GpuTelemetry(
                "nvidia", 0, True, 61, 2 * 1024**3, 8 * 1024**3
            ),
            "GPU: 61°C | VRAM: 2.0/8.0 GB (25%)",
        ),
        (
            actions_module.GpuTelemetry("amd", 0, None, None, 2 * 1024**3, 8 * 1024**3),
            "GPU: N/A | VRAM: 2.0/8.0 GB (25%)",
        ),
        (
            actions_module.GpuTelemetry("amd", 0, None, None, None, None),
            "GPU: N/A | VRAM: N/A",
        ),
    ],
)
def test_windows_system_info_adapter_formats_gpu_temperature_and_vram(
    telemetry: object,
    expected: str,
) -> None:
    adapter = actions_module.WindowsSystemInfoAdapter(
        read_gpu_telemetry=lambda: telemetry,
    )

    result = adapter.execute(SystemInfoAction(type="system_info", target="gpu"))

    assert result == expected


@pytest.mark.parametrize(
    ("telemetry", "expected"),
    [
        (
            actions_module.GpuTelemetry("nvidia", 0, True, -1, 1, 2),
            "GPU: N/A | VRAM: 0.0/0.0 GB (50%)",
        ),
        (
            actions_module.GpuTelemetry("nvidia", 0, True, 151, 1, 2),
            "GPU: N/A | VRAM: 0.0/0.0 GB (50%)",
        ),
        (
            actions_module.GpuTelemetry("nvidia", 0, True, 61, -1, 2),
            "GPU: 61°C | VRAM: N/A",
        ),
        (
            actions_module.GpuTelemetry("nvidia", 0, True, 61, 3, 2),
            "GPU: 61°C | VRAM: N/A",
        ),
        (
            actions_module.GpuTelemetry("nvidia", 0, True, 61, 1, 0),
            "GPU: 61°C | VRAM: N/A",
        ),
    ],
)
def test_windows_system_info_adapter_sanitizes_invalid_gpu_values(
    telemetry: object,
    expected: str,
) -> None:
    adapter = actions_module.WindowsSystemInfoAdapter(
        read_gpu_telemetry=lambda: telemetry
    )

    result = adapter.execute(SystemInfoAction(type="system_info", target="gpu"))

    assert result == expected
