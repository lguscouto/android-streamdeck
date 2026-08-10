package com.antigravity.streamdeck.data.model

import com.google.gson.annotations.SerializedName

data class WebSocketMessage<T>(
    @SerializedName("event") val event: String,
    @SerializedName("payload") val payload: T
)

object EventTypes {
    const val PRESS_BUTTON = "PRESS_BUTTON"
    const val RELEASE_BUTTON = "RELEASE_BUTTON"
    const val SWITCH_PAGE = "SWITCH_PAGE"
    const val SWITCH_PROFILE = "SWITCH_PROFILE"
    const val OPEN_FOLDER = "OPEN_FOLDER"
    const val GO_BACK_FOLDER = "GO_BACK_FOLDER"
    const val PING = "PING"
    const val PONG = "PONG"
    const val GRID_SYNC = "GRID_SYNC"
    const val BUTTON_STATE_CHANGE = "BUTTON_STATE_CHANGE"
    const val HARDWARE_SYNC = "HARDWARE_SYNC"
    const val SPOTIFY_SYNC = "SPOTIFY_SYNC"
}

data class PressButtonPayload(
    @SerializedName("profileId") val profileId: String,
    @SerializedName("pageIndex") val pageIndex: Int,
    @SerializedName("row") val row: Int,
    @SerializedName("col") val col: Int,
    @SerializedName("buttonId") val buttonId: String,
    @SerializedName("actionType") val actionType: String? = null
)

data class ButtonModel(
    @SerializedName("id") val id: String,
    @SerializedName("row") val row: Int,
    @SerializedName("col") val col: Int,
    @SerializedName("rowSpan") val rowSpan: Int? = 1,
    @SerializedName("colSpan") val colSpan: Int? = 1,
    @SerializedName("label") val label: String,
    @SerializedName("labelColor") val labelColor: String? = "#FFFFFF",
    @SerializedName("backgroundColor") val backgroundColor: String? = "#1E1E2E",
    @SerializedName("iconUrl") val iconUrl: String? = null,
    @SerializedName("state") val state: String? = "OFF",
    @SerializedName("states") val states: Map<String, ButtonStateModel>? = null,
    @SerializedName("actionType") val actionType: String? = null,
    @SerializedName("folderButtons") val folderButtons: List<ButtonModel>? = null
)

data class ButtonStateModel(
    @SerializedName("label") val label: String,
    @SerializedName("iconUrl") val iconUrl: String? = null,
    @SerializedName("backgroundColor") val backgroundColor: String? = "#1E1E2E"
)

data class GridSyncPayload(
    @SerializedName("activeProfileId") val activeProfileId: String,
    @SerializedName("activePageIndex") val activePageIndex: Int,
    @SerializedName("currentFolderId") val currentFolderId: String? = null,
    @SerializedName("folderPath") val folderPath: List<String>? = null,
    @SerializedName("gridConfig") val gridConfig: GridConfig,
    @SerializedName("buttons") val buttons: List<ButtonModel>
)

data class GridConfig(
    @SerializedName("rows") val rows: Int,
    @SerializedName("cols") val cols: Int
)

data class ButtonStateChangePayload(
    @SerializedName("buttonId") val buttonId: String,
    @SerializedName("newState") val newState: String
)

data class HardwareMetricsPayload(
    @SerializedName("cpuUsage") val cpuUsage: Int,
    @SerializedName("cpuTemp") val cpuTemp: Int,
    @SerializedName("ramUsage") val ramUsage: Int,
    @SerializedName("ramUsedGb") val ramUsedGb: String,
    @SerializedName("ramTotalGb") val ramTotalGb: String,
    @SerializedName("gpuUsage") val gpuUsage: Int
)

data class SpotifyTrackPayload(
    @SerializedName("title") val title: String,
    @SerializedName("artist") val artist: String,
    @SerializedName("isPlaying") val isPlaying: Boolean
)
