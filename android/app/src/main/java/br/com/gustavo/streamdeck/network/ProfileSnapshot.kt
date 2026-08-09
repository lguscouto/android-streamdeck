package br.com.gustavo.streamdeck.network

import org.json.JSONArray
import org.json.JSONObject

data class StreamDeckProfileSnapshot(
    val profileId: String,
    val profileName: String,
    val revision: Int,
    val activePage: StreamDeckPage,
)

data class StreamDeckPage(
    val id: String,
    val title: String,
    val rows: Int,
    val columns: Int,
    val buttons: List<StreamDeckButton>,
)

data class StreamDeckButton(
    val id: String,
    val row: Int,
    val column: Int,
    val title: String,
    val icon: String?,
    val color: String?,
)

object ProfileSnapshotParser {
    fun parse(rawMessage: String): StreamDeckProfileSnapshot = try {
        val envelope = JSONObject(rawMessage)
        require(envelope.getInt("protocol_version") == PROTOCOL_VERSION) {
            "Unsupported profile snapshot protocol"
        }
        require(envelope.getString("type") == "profile_snapshot") {
            "Expected profile snapshot"
        }
        parseProfile(envelope.getJSONObject("payload").getJSONObject("profile"))
    } catch (error: IllegalArgumentException) {
        throw error
    } catch (error: Exception) {
        throw IllegalArgumentException("Invalid profile snapshot", error)
    }

    private fun parseProfile(profile: JSONObject): StreamDeckProfileSnapshot {
        require(profile.getInt("protocol_version") == PROTOCOL_VERSION) {
            "Unsupported profile protocol"
        }
        val profileId = requiredString(profile, "id")
        val profileName = requiredString(profile, "name")
        val revision = profile.getInt("revision")
        require(revision >= 1) { "Profile revision must be positive" }
        val activePageId = requiredString(profile, "active_page_id")
        val pages = parsePages(profile.getJSONArray("pages"))
        require(pages.isNotEmpty()) { "Profile must have at least one page" }
        val activePage = pages.singleOrNull { it.id == activePageId }
            ?: throw IllegalArgumentException("Profile active page is missing")
        return StreamDeckProfileSnapshot(
            profileId = profileId,
            profileName = profileName,
            revision = revision,
            activePage = activePage,
        )
    }

    private fun parsePages(rawPages: JSONArray): List<StreamDeckPage> {
        val pageIds = mutableSetOf<String>()
        return buildList {
            for (index in 0 until rawPages.length()) {
                val page = rawPages.getJSONObject(index)
                val pageId = requiredString(page, "id")
                require(pageIds.add(pageId)) { "Profile page identifiers must be unique" }
                val rows = page.getInt("rows")
                val columns = page.getInt("columns")
                require(rows in 1..MAX_GRID_DIMENSION) { "Page rows are outside allowed range" }
                require(columns in 1..MAX_GRID_DIMENSION) {
                    "Page columns are outside allowed range"
                }
                add(
                    StreamDeckPage(
                        id = pageId,
                        title = requiredString(page, "title"),
                        rows = rows,
                        columns = columns,
                        buttons = parseButtons(
                            rawButtons = page.getJSONArray("buttons"),
                            rows = rows,
                            columns = columns,
                        ),
                    ),
                )
            }
        }
    }

    private fun parseButtons(
        rawButtons: JSONArray,
        rows: Int,
        columns: Int,
    ): List<StreamDeckButton> {
        val buttonIds = mutableSetOf<String>()
        val occupiedCells = mutableSetOf<Pair<Int, Int>>()
        return buildList {
            for (index in 0 until rawButtons.length()) {
                val button = rawButtons.getJSONObject(index)
                val buttonId = requiredString(button, "id")
                val row = button.getInt("row")
                val column = button.getInt("column")
                require(row in 0 until rows && column in 0 until columns) {
                    "Button is outside configured grid"
                }
                require(buttonIds.add(buttonId)) { "Page button identifiers must be unique" }
                require(occupiedCells.add(row to column)) {
                    "Grid button positions must be unique"
                }
                add(
                    StreamDeckButton(
                        id = buttonId,
                        row = row,
                        column = column,
                        title = requiredString(button, "title"),
                        icon = optionalString(button, "icon"),
                        color = optionalColor(button),
                    ),
                )
            }
        }
    }

    private fun optionalColor(source: JSONObject): String? {
        val color = optionalString(source, "color") ?: return null
        require(HEX_COLOR.matches(color)) { "Button color must be a hexadecimal RGB value" }
        return color
    }

    private fun requiredString(source: JSONObject, name: String): String = source.getString(name)
        .trim()
        .also { value -> require(value.isNotEmpty()) { "$name must not be blank" } }

    private fun optionalString(source: JSONObject, name: String): String? {
        if (!source.has(name) || source.isNull(name)) {
            return null
        }
        return source.getString(name).trim().takeIf { it.isNotEmpty() }
    }

    private const val PROTOCOL_VERSION = 1
    private const val MAX_GRID_DIMENSION = 64
    private val HEX_COLOR = Regex("#[0-9A-Fa-f]{6}")
}
