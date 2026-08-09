from __future__ import annotations

from typing import Annotated, Literal, TypeAlias
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, field_validator

StableId: TypeAlias = Annotated[
    str,
    Field(
        min_length=1,
        max_length=64,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$",
    ),
]
KeyName: TypeAlias = Annotated[
    str,
    Field(
        min_length=1,
        max_length=32,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._+\-]{0,31}$",
    ),
]
Title: TypeAlias = Annotated[str, Field(min_length=1, max_length=120)]
VersionString: TypeAlias = Annotated[str, Field(min_length=1, max_length=64)]
RequestId: TypeAlias = Annotated[
    str,
    Field(
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$",
    ),
]

NonNegativeInt: TypeAlias = Annotated[int, Field(ge=0)]
PositiveInt: TypeAlias = Annotated[int, Field(ge=1)]
GridDimension: TypeAlias = Annotated[int, Field(ge=1, le=64)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


Modifier = Literal["ctrl", "alt", "shift", "win"]
MediaCommand = Literal[
    "play_pause",
    "next",
    "previous",
    "stop",
    "volume_up",
    "volume_down",
    "mute",
]


class HotkeyAction(StrictModel):
    type: Literal["hotkey"]
    modifiers: list[Modifier] = Field(min_length=1, max_length=4)
    key: KeyName

    @field_validator("modifiers")
    @classmethod
    def modifiers_must_be_unique(cls, modifiers: list[Modifier]) -> list[Modifier]:
        if len(modifiers) != len(set(modifiers)):
            raise ValueError("hotkey modifiers must be unique")
        return modifiers


class KeyAction(StrictModel):
    type: Literal["key"]
    key: KeyName


class MediaAction(StrictModel):
    type: Literal["media"]
    command: MediaCommand


class TextAction(StrictModel):
    type: Literal["text"]
    text: Annotated[str, Field(min_length=1, max_length=2000)]


class UrlAction(StrictModel):
    type: Literal["url"]
    url: Annotated[str, Field(min_length=1, max_length=2048)]

    @field_validator("url")
    @classmethod
    def require_https_url(cls, url: str) -> str:
        if not url.startswith("https://"):
            raise ValueError("url must use https")
        if any(character.isspace() for character in url):
            raise ValueError("url must not contain whitespace")
        try:
            parsed = urlsplit(url)
        except ValueError as exc:
            raise ValueError("url must be a valid HTTPS URL") from exc
        if parsed.scheme != "https" or not parsed.netloc or parsed.hostname is None:
            raise ValueError("url must be a valid HTTPS URL")
        return url


class ApplicationAction(StrictModel):
    type: Literal["application"]
    app_id: StableId


Action: TypeAlias = Annotated[
    HotkeyAction
    | KeyAction
    | MediaAction
    | TextAction
    | UrlAction
    | ApplicationAction,
    Field(discriminator="type"),
]


class Button(StrictModel):
    id: StableId
    row: NonNegativeInt
    column: NonNegativeInt
    title: Title
    icon: Annotated[str, Field(min_length=1, max_length=120)] | None = None
    color: Annotated[
        str,
        Field(pattern=r"^#(?:[0-9A-Fa-f]{6}|[0-9A-Fa-f]{8})$"),
    ] | None = None
    action: Action


class Page(StrictModel):
    id: StableId
    title: Title
    order: NonNegativeInt
    rows: GridDimension
    columns: GridDimension
    buttons: list[Button] = Field(min_length=1)

    @field_validator("buttons")
    @classmethod
    def validate_button_layout(
        cls, buttons: list[Button], info: object
    ) -> list[Button]:
        button_ids = [button.id for button in buttons]
        if len(button_ids) != len(set(button_ids)):
            raise ValueError("button IDs must be unique within a page")

        positions = [(button.row, button.column) for button in buttons]
        if len(positions) != len(set(positions)):
            raise ValueError("button position (row, column) must be unique")

        rows = info.data.get("rows")
        columns = info.data.get("columns")
        if rows is not None:
            for button in buttons:
                if button.row >= rows:
                    raise ValueError("button row must be less than page rows")
        if columns is not None:
            for button in buttons:
                if button.column >= columns:
                    raise ValueError("button column must be less than page columns")
        return buttons


class Profile(StrictModel):
    protocol_version: Literal[1]
    id: StableId
    name: Title
    revision: PositiveInt
    active_page_id: StableId
    pages: list[Page] = Field(min_length=1)

    @field_validator("pages")
    @classmethod
    def validate_page_relationships(cls, pages: list[Page], info: object) -> list[Page]:
        page_ids = [page.id for page in pages]
        if len(page_ids) != len(set(page_ids)):
            raise ValueError("page IDs must be unique")

        page_orders = [page.order for page in pages]
        if len(page_orders) != len(set(page_orders)):
            raise ValueError("page order values must be unique")

        active_page_id = info.data.get("active_page_id")
        if active_page_id is not None and active_page_id not in page_ids:
            raise ValueError("active_page_id must refer to an existing page")

        button_ids: list[str] = []
        for page in pages:
            button_ids.extend(button.id for button in page.buttons)
        if len(button_ids) != len(set(button_ids)):
            raise ValueError("button IDs must be unique across the profile")
        return pages


class HelloPayload(StrictModel):
    client_id: StableId
    client_version: VersionString
    supported_protocol_versions: list[Literal[1]] = Field(min_length=1)
    requested_profile_id: StableId | None = None

    @field_validator("supported_protocol_versions")
    @classmethod
    def supported_versions_must_be_unique(
        cls, versions: list[Literal[1]]
    ) -> list[Literal[1]]:
        if len(versions) != len(set(versions)):
            raise ValueError("supported protocol versions must be unique")
        return versions


class WelcomePayload(StrictModel):
    server_id: StableId
    server_version: VersionString
    profile_id: StableId
    revision: PositiveInt


class PressPayload(StrictModel):
    request_id: RequestId
    profile_id: StableId
    page_id: StableId
    button_id: StableId
    revision: PositiveInt


class AckPayload(StrictModel):
    request_id: RequestId
    status: Literal["accepted", "completed", "rejected"]
    message: Annotated[str, Field(min_length=1, max_length=500)] | None = None


class ErrorPayload(StrictModel):
    request_id: RequestId | None = None
    code: Annotated[
        str,
        Field(
            min_length=1,
            max_length=64,
            pattern=r"^[A-Z0-9][A-Z0-9._-]{0,63}$",
        ),
    ]
    message: Annotated[str, Field(min_length=1, max_length=500)]
    retryable: bool | None = None


class NoncePayload(StrictModel):
    nonce: Annotated[str, Field(min_length=1, max_length=128)]


class ProfileSnapshotPayload(StrictModel):
    profile: Profile


class ProfileChangedPayload(StrictModel):
    profile_id: StableId
    revision: PositiveInt
    reason: Literal["created", "updated", "deleted"] | None = None


class HelloMessage(StrictModel):
    protocol_version: Literal[1]
    type: Literal["hello"]
    payload: HelloPayload


class WelcomeMessage(StrictModel):
    protocol_version: Literal[1]
    type: Literal["welcome"]
    payload: WelcomePayload


class PressMessage(StrictModel):
    protocol_version: Literal[1]
    type: Literal["press"]
    payload: PressPayload


class AckMessage(StrictModel):
    protocol_version: Literal[1]
    type: Literal["ack"]
    payload: AckPayload


class ErrorMessage(StrictModel):
    protocol_version: Literal[1]
    type: Literal["error"]
    payload: ErrorPayload


class PingMessage(StrictModel):
    protocol_version: Literal[1]
    type: Literal["ping"]
    payload: NoncePayload


class PongMessage(StrictModel):
    protocol_version: Literal[1]
    type: Literal["pong"]
    payload: NoncePayload


class ProfileSnapshotMessage(StrictModel):
    protocol_version: Literal[1]
    type: Literal["profile_snapshot"]
    payload: ProfileSnapshotPayload


class ProfileChangedMessage(StrictModel):
    protocol_version: Literal[1]
    type: Literal["profile_changed"]
    payload: ProfileChangedPayload


Message: TypeAlias = Annotated[
    HelloMessage
    | WelcomeMessage
    | PressMessage
    | AckMessage
    | ErrorMessage
    | PingMessage
    | PongMessage
    | ProfileSnapshotMessage
    | ProfileChangedMessage,
    Field(discriminator="type"),
]
MessageAdapter = TypeAdapter(Message)

__all__ = [
    "AckMessage",
    "AckPayload",
    "Action",
    "ApplicationAction",
    "Button",
    "ErrorMessage",
    "ErrorPayload",
    "HelloMessage",
    "HelloPayload",
    "HotkeyAction",
    "KeyAction",
    "MediaAction",
    "Message",
    "MessageAdapter",
    "NoncePayload",
    "Page",
    "PingMessage",
    "PongMessage",
    "PressMessage",
    "PressPayload",
    "Profile",
    "ProfileChangedMessage",
    "ProfileChangedPayload",
    "ProfileSnapshotMessage",
    "ProfileSnapshotPayload",
    "TextAction",
    "UrlAction",
    "WelcomeMessage",
    "WelcomePayload",
]
