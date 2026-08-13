from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

from app.schemas import Profile

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "shared" / "fixtures" / "essential-controls-profile.json"
SCHEMA_PATH = REPO_ROOT / "shared" / "protocol" / "v1-profile.schema.json"

EXPECTED_BUTTONS = [
    (
        "media-play-pause",
        0,
        0,
        "Play/Pause",
        "play_pause",
        "#8B5CF6",
        {"type": "media", "command": "play_pause"},
    ),
    (
        "media-next",
        0,
        1,
        "Próxima",
        "skip_next",
        "#8B5CF6",
        {"type": "media", "command": "next"},
    ),
    (
        "media-mute",
        0,
        2,
        "Mute",
        "volume_off",
        "#5AA7FF",
        {"type": "media", "command": "mute"},
    ),
    (
        "spotify-play-pause",
        1,
        0,
        "Spotify",
        "spotify",
        "#1ED760",
        {"type": "media", "command": "play_pause"},
    ),
    (
        "open-chrome",
        1,
        1,
        "Chrome",
        "chrome",
        "#FFB648",
        {"type": "application", "app_id": "chrome"},
    ),
    (
        "volume-up",
        1,
        2,
        "Volume +",
        "volume_up",
        "#38D9C5",
        {"type": "media", "command": "volume_up"},
    ),
    (
        "system-gpu",
        1,
        3,
        "GPU & VRAM",
        "gpu",
        "#8B5CF6",
        {"type": "system_info", "target": "gpu"},
    ),
    (
        "volume-down",
        2,
        0,
        "Volume −",
        "volume_down",
        "#38D9C5",
        {"type": "media", "command": "volume_down"},
    ),
    (
        "print-screen",
        2,
        1,
        "Print Screen",
        "screenshot",
        "#FF5D73",
        {"type": "key", "key": "PRINTSCREEN"},
    ),
    (
        "system-cpu",
        2,
        2,
        "CPU & Temp",
        "cpu",
        "#5AA7FF",
        {"type": "system_info", "target": "cpu"},
    ),
    (
        "system-memory",
        2,
        3,
        "Memória",
        "memory",
        "#38D9C5",
        {"type": "system_info", "target": "memory"},
    ),
]


def test_essential_controls_fixture_is_a_valid_closed_profile() -> None:
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    profile = Profile.model_validate(payload)
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    assert profile.id == "essential-controls"
    assert profile.name == "Controles essenciais"
    assert profile.revision == 1
    assert profile.active_page_id == "main"
    assert len(profile.pages) == 1

    page = profile.pages[0]
    assert (page.id, page.title, page.order, page.rows, page.columns) == (
        "main",
        "Principal",
        0,
        3,
        4,
    )
    assert [
        (
            button.id,
            button.row,
            button.column,
            button.title,
            button.icon,
            button.color,
            button.action.to_wire(),
        )
        for button in page.buttons
    ] == EXPECTED_BUTTONS
    assert set((button.row, button.column) for button in page.buttons) == {
        (0, 0),
        (0, 1),
        (0, 2),
        (1, 0),
        (1, 1),
        (1, 2),
        (1, 3),
        (2, 0),
        (2, 1),
        (2, 2),
        (2, 3),
    }

    assert not list(Draft202012Validator(schema).iter_errors(payload))
    assert all(
        "command" not in button["action"] or button["action"]["type"] == "media"
        for button in payload["pages"][0]["buttons"]
    )
