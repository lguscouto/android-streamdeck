package br.com.gustavo.streamdeck.network

import org.json.JSONArray
import org.json.JSONObject

sealed interface StreamDeckAction {
    fun toJson(): JSONObject
}

data class StreamDeckHotkeyAction(
    val modifiers: List<String>,
    val key: String,
) : StreamDeckAction {
    override fun toJson(): JSONObject = JSONObject()
        .put("type", "hotkey")
        .put("modifiers", JSONArray(modifiers))
        .put("key", key)
}

data class StreamDeckKeyAction(
    val key: String,
) : StreamDeckAction {
    override fun toJson(): JSONObject = JSONObject()
        .put("type", "key")
        .put("key", key)
}

data class StreamDeckMediaAction(
    val command: String,
) : StreamDeckAction {
    override fun toJson(): JSONObject = JSONObject()
        .put("type", "media")
        .put("command", command)
}

data class StreamDeckTextAction(
    val text: String,
) : StreamDeckAction {
    override fun toJson(): JSONObject = JSONObject()
        .put("type", "text")
        .put("text", text)
}

data class StreamDeckUrlAction(
    val url: String,
) : StreamDeckAction {
    override fun toJson(): JSONObject = JSONObject()
        .put("type", "url")
        .put("url", url)
}

data class StreamDeckApplicationAction(
    val appId: String,
) : StreamDeckAction {
    override fun toJson(): JSONObject = JSONObject()
        .put("type", "application")
        .put("app_id", appId)
}

data class StreamDeckProfileSnapshot(
    val profileId: String,
    val profileName: String,
    val revision: Int,
    val activePage: StreamDeckPage,
    val pages: List<StreamDeckPage> = listOf(activePage),
)

data class StreamDeckPage(
    val id: String,
    val title: String,
    val rows: Int,
    val columns: Int,
    val buttons: List<StreamDeckButton>,
    val order: Int = 0,
)

data class StreamDeckButton(
    val id: String,
    val row: Int,
    val column: Int,
    val title: String,
    val icon: String?,
    val color: String?,
    val action: StreamDeckAction? = null,
)

object ProfileSnapshotParser {
    fun parse(rawMessage: String): StreamDeckProfileSnapshot = try {
        val envelope = JSONObject(rawMessage)
        requireExactKeys(
            envelope,
            required = setOf("protocol_version", "type", "payload"),
        )
        require(envelope.getInt("protocol_version") == PROTOCOL_VERSION) {
            "Unsupported profile snapshot protocol"
        }
        require(envelope.getString("type") == "profile_snapshot") {
            "Expected profile snapshot"
        }
        val payload = envelope.getJSONObject("payload")
        requireExactKeys(payload, required = setOf("profile"))
        parseProfile(payload.getJSONObject("profile"))
    } catch (error: IllegalArgumentException) {
        throw error
    } catch (error: Exception) {
        throw IllegalArgumentException("Invalid profile snapshot", error)
    }

    fun parseWireProfile(rawProfile: String): StreamDeckProfileSnapshot = try {
        parseProfile(JSONObject(rawProfile))
    } catch (error: IllegalArgumentException) {
        throw error
    } catch (error: Exception) {
        throw IllegalArgumentException("Invalid profile response", error)
    }

    private fun parseProfile(profile: JSONObject): StreamDeckProfileSnapshot {
        requireExactKeys(
            profile,
            required = setOf(
                "protocol_version",
                "id",
                "name",
                "revision",
                "active_page_id",
                "pages",
            ),
        )
        require(profile.getInt("protocol_version") == PROTOCOL_VERSION) {
            "Unsupported profile protocol"
        }
        val profileId = requiredStableId(profile, "id")
        val profileName = requiredString(profile, "name")
        val revision = profile.getInt("revision")
        require(revision >= 1) { "Profile revision must be positive" }
        val activePageId = requiredStableId(profile, "active_page_id")
        val pages = parsePages(profile.getJSONArray("pages"))
        require(pages.isNotEmpty()) { "Profile must have at least one page" }
        val activePage = pages.singleOrNull { it.id == activePageId }
            ?: throw IllegalArgumentException("Profile active page is missing")
        return StreamDeckProfileSnapshot(
            profileId = profileId,
            profileName = profileName,
            revision = revision,
            activePage = activePage,
            pages = pages,
        )
    }

    private fun parsePages(rawPages: JSONArray): List<StreamDeckPage> {
        val pageIds = mutableSetOf<String>()
        val pageOrders = mutableSetOf<Int>()
        return buildList {
            for (index in 0 until rawPages.length()) {
                val page = rawPages.getJSONObject(index)
                requireExactKeys(
                    page,
                    required = setOf("id", "title", "order", "rows", "columns", "buttons"),
                )
                val pageId = requiredStableId(page, "id")
                require(pageIds.add(pageId)) { "Profile page identifiers must be unique" }
                val order = page.getInt("order")
                require(order >= 0 && pageOrders.add(order)) {
                    "Profile page orders must be unique and non-negative"
                }
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
                        order = order,
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
                requireExactKeys(
                    button,
                    required = setOf("id", "row", "column", "title", "action"),
                    optional = setOf("icon", "color"),
                )
                val buttonId = requiredStableId(button, "id")
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
                        action = parseAction(button.getJSONObject("action")),
                    ),
                )
            }
        }
    }

    private fun parseAction(action: JSONObject): StreamDeckAction {
        val type = requiredString(action, "type")
        return when (type) {
            "hotkey" -> {
                requireExactKeys(action, required = setOf("type", "modifiers", "key"))
                val rawModifiers = action.getJSONArray("modifiers")
                require(rawModifiers.length() in 1..4) {
                    "Hotkey modifiers are outside allowed range"
                }
                val modifiers = buildList {
                    for (index in 0 until rawModifiers.length()) {
                        add(requiredString(rawModifiers, index))
                    }
                }
                require(modifiers.size == modifiers.toSet().size) {
                    "Hotkey modifiers must be unique"
                }
                require(modifiers.all { it in ALLOWED_MODIFIERS }) {
                    "Hotkey modifier is not supported"
                }
                StreamDeckHotkeyAction(modifiers, requiredKey(action, "key"))
            }
            "key" -> {
                requireExactKeys(action, required = setOf("type", "key"))
                StreamDeckKeyAction(requiredKey(action, "key"))
            }
            "media" -> {
                requireExactKeys(action, required = setOf("type", "command"))
                val command = requiredString(action, "command")
                require(command in ALLOWED_MEDIA_COMMANDS) { "Media command is not supported" }
                StreamDeckMediaAction(command)
            }
            "text" -> {
                requireExactKeys(action, required = setOf("type", "text"))
                val text = requiredString(action, "text")
                require(text.length <= MAX_TEXT_LENGTH) { "Text action is too long" }
                StreamDeckTextAction(text)
            }
            "url" -> {
                requireExactKeys(action, required = setOf("type", "url"))
                val url = requiredString(action, "url")
                require(isSafeHttpsUrl(url)) { "URL action must be a safe HTTPS URL" }
                StreamDeckUrlAction(url)
            }
            "application" -> {
                requireExactKeys(action, required = setOf("type", "app_id"))
                StreamDeckApplicationAction(requiredStableId(action, "app_id"))
            }
            else -> throw IllegalArgumentException("Unsupported action type")
        }
    }

    private fun optionalColor(source: JSONObject): String? {
        val color = optionalString(source, "color") ?: return null
        require(HEX_COLOR.matches(color)) { "Button color must be a hexadecimal RGB value" }
        return color
    }

    private fun requiredKey(source: JSONObject, name: String): String {
        val value = requiredString(source, name)
        require(value.length <= MAX_KEY_LENGTH) { "Key name is too long" }
        return value
    }

    private fun requiredStableId(source: JSONObject, name: String): String {
        val value = requiredString(source, name)
        require(STABLE_ID.matches(value)) { "$name is not a stable identifier" }
        return value
    }

    private fun requiredString(source: JSONObject, name: String): String = source.getString(name)
        .trim()
        .also { value -> require(value.isNotEmpty()) { "$name must not be blank" } }

    private fun requiredString(source: JSONArray, index: Int): String = source.getString(index)
        .trim()
        .also { value -> require(value.isNotEmpty()) { "Array string must not be blank" } }

    private fun optionalString(source: JSONObject, name: String): String? {
        if (!source.has(name) || source.isNull(name)) {
            return null
        }
        return source.getString(name).trim().takeIf { it.isNotEmpty() }
    }

    private fun requireExactKeys(
        source: JSONObject,
        required: Set<String>,
        optional: Set<String> = emptySet(),
    ) {
        val actual = buildSet {
            val keys = source.keys()
            while (keys.hasNext()) {
                add(keys.next())
            }
        }
        require(actual == required || actual == required + actual.intersect(optional)) {
            "Unexpected JSON fields"
        }
        require(required.all { source.has(it) && !source.isNull(it) }) {
            "Required JSON field is missing"
        }
    }

    private const val PROTOCOL_VERSION = 1
    private const val MAX_GRID_DIMENSION = 64
    private const val MAX_KEY_LENGTH = 32
    private const val MAX_TEXT_LENGTH = 2000
    private val STABLE_ID = Regex("^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
    private val HEX_COLOR = Regex("#[0-9A-Fa-f]{6}(?:[0-9A-Fa-f]{2})?")
    private val ALLOWED_MODIFIERS = setOf("ctrl", "alt", "shift", "win")
    private val ALLOWED_MEDIA_COMMANDS = setOf(
        "play_pause",
        "next",
        "previous",
        "stop",
        "volume_up",
        "volume_down",
        "mute",
    )
    private val HTTPS_URL = Regex("^https://[^\\s\\\\\\u0000-\\u001F\\u007F-\\u009F]+$")

    private fun isSafeHttpsUrl(url: String): Boolean {
        if (!HTTPS_URL.matches(url) || url.contains("@")) {
            return false
        }
        return runCatching {
            val uri = java.net.URI(url)
            uri.scheme == "https" && !uri.host.isNullOrBlank() && uri.userInfo == null
        }.getOrDefault(false)
    }
}

object ProfileSnapshotSerializer {
    fun toWire(snapshot: StreamDeckProfileSnapshot, revision: Int = snapshot.revision): String {
        require(revision >= 1) { "Profile revision must be positive" }
        val pages = JSONArray()
        snapshot.pages.forEach { page ->
            val buttons = JSONArray()
            page.buttons.forEach { button ->
                val action = button.action
                    ?: throw IllegalArgumentException("Button action is missing")
                val wireButton = JSONObject()
                    .put("id", button.id)
                    .put("row", button.row)
                    .put("column", button.column)
                    .put("title", button.title)
                    .put("action", action.toJson())
                button.icon?.let { wireButton.put("icon", it) }
                button.color?.let { wireButton.put("color", it) }
                buttons.put(wireButton)
            }
            pages.put(
                JSONObject()
                    .put("id", page.id)
                    .put("title", page.title)
                    .put("order", page.order)
                    .put("rows", page.rows)
                    .put("columns", page.columns)
                    .put("buttons", buttons),
            )
        }
        return JSONObject()
            .put("protocol_version", 1)
            .put("id", snapshot.profileId)
            .put("name", snapshot.profileName)
            .put("revision", revision)
            .put("active_page_id", snapshot.activePage.id)
            .put("pages", pages)
            .toString()
    }
}
