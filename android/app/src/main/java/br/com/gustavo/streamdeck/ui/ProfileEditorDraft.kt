package br.com.gustavo.streamdeck.ui

import br.com.gustavo.streamdeck.network.StreamDeckAction
import br.com.gustavo.streamdeck.network.StreamDeckApplicationAction
import br.com.gustavo.streamdeck.network.StreamDeckButton
import br.com.gustavo.streamdeck.network.StreamDeckHotkeyAction
import br.com.gustavo.streamdeck.network.StreamDeckKeyAction
import br.com.gustavo.streamdeck.network.StreamDeckMediaAction
import br.com.gustavo.streamdeck.network.StreamDeckPage
import br.com.gustavo.streamdeck.network.StreamDeckProfileSnapshot
import br.com.gustavo.streamdeck.network.StreamDeckSystemInfoAction
import br.com.gustavo.streamdeck.network.StreamDeckTextAction
import br.com.gustavo.streamdeck.network.StreamDeckUrlAction

enum class EditorActionType {
    HOTKEY,
    KEY,
    MEDIA,
    TEXT,
    URL,
    APPLICATION,
    SYSTEM_INFO,
}

data class ProfileEditorDraft(
    val profileName: String,
    val pageTitle: String,
    val selectedButtonId: String,
    val title: String,
    val row: String,
    val column: String,
    val icon: String,
    val color: String,
    val actionType: EditorActionType,
    val modifiers: String,
    val actionValue: String,
) {
    fun selectButton(snapshot: StreamDeckProfileSnapshot, buttonId: String): ProfileEditorDraft {
        return from(snapshot, buttonId).copy(
            profileName = profileName,
            pageTitle = pageTitle,
        )
    }

    fun withActionType(nextType: EditorActionType): ProfileEditorDraft {
        val defaults = when (nextType) {
            EditorActionType.HOTKEY -> "ctrl" to "A"
            EditorActionType.KEY -> "" to "A"
            EditorActionType.MEDIA -> "" to "play_pause"
            EditorActionType.TEXT -> "" to "Texto"
            EditorActionType.URL -> "" to "https://example.com"
            EditorActionType.APPLICATION -> "" to "app"
            EditorActionType.SYSTEM_INFO -> "" to "cpu"
        }
        return copy(
            actionType = nextType,
            modifiers = defaults.first,
            actionValue = defaults.second,
        )
    }

    fun applyTo(snapshot: StreamDeckProfileSnapshot): StreamDeckProfileSnapshot {
        val profileName = profileName.trim()
        val pageTitle = pageTitle.trim()
        val title = title.trim()
        require(profileName.isNotEmpty()) { "Profile name must not be blank" }
        require(pageTitle.isNotEmpty()) { "Page title must not be blank" }
        require(title.isNotEmpty()) { "Button title must not be blank" }

        val activePage = snapshot.activePage
        val rowValue = row.trim().toIntOrNull()
        val columnValue = column.trim().toIntOrNull()
        require(rowValue != null && rowValue in 0 until activePage.rows) {
            "Button row is outside configured grid"
        }
        require(columnValue != null && columnValue in 0 until activePage.columns) {
            "Button column is outside configured grid"
        }
        val action = buildAction()
        val optionalColor = color.trim().takeIf { it.isNotEmpty() }
        require(optionalColor == null || HEX_COLOR.matches(optionalColor)) {
            "Button color must be a hexadecimal RGB value"
        }

        var matched = false
        val updatedPages = snapshot.pages.map { page ->
            val updatedButtons = page.buttons.map { button ->
                if (button.id != selectedButtonId) {
                    button
                } else {
                    matched = true
                    button.copy(
                        row = rowValue,
                        column = columnValue,
                        title = title,
                        icon = icon.trim().takeIf { it.isNotEmpty() },
                        color = optionalColor,
                        action = action,
                    )
                }
            }
            if (page.id == activePage.id) {
                page.copy(title = pageTitle, buttons = updatedButtons)
            } else {
                page.copy(buttons = updatedButtons)
            }
        }
        require(matched) { "Selected button does not exist" }
        val updatedActivePage = updatedPages.single { it.id == snapshot.activePage.id }
        return snapshot.copy(
            profileName = profileName,
            activePage = updatedActivePage,
            pages = updatedPages,
        )
    }

    private fun buildAction(): StreamDeckAction {
        val value = actionValue.trim()
        return when (actionType) {
            EditorActionType.HOTKEY -> {
                val parsedModifiers = modifiers.split(',')
                    .map(String::trim)
                    .filter(String::isNotEmpty)
                require(parsedModifiers.isNotEmpty() && parsedModifiers.size <= 4) {
                    "Hotkey must contain one to four modifiers"
                }
                require(parsedModifiers.size == parsedModifiers.toSet().size) {
                    "Hotkey modifiers must be unique"
                }
                require(parsedModifiers.all { it in ALLOWED_MODIFIERS }) {
                    "Hotkey modifier is not supported"
                }
                StreamDeckHotkeyAction(parsedModifiers, validateKey(value))
            }
            EditorActionType.KEY -> StreamDeckKeyAction(validateKey(value))
            EditorActionType.MEDIA -> {
                require(value in ALLOWED_MEDIA_COMMANDS) { "Media command is not supported" }
                StreamDeckMediaAction(value)
            }
            EditorActionType.TEXT -> {
                require(value.isNotEmpty() && value.length <= MAX_TEXT_LENGTH) {
                    "Text action is invalid"
                }
                StreamDeckTextAction(value)
            }
            EditorActionType.URL -> {
                require(
                    value.startsWith("https://") &&
                        value.none { it.isWhitespace() || it.code in 0..31 } &&
                        !value.contains("@"),
                ) { "URL action must be a safe HTTPS URL" }
                StreamDeckUrlAction(value)
            }
            EditorActionType.APPLICATION -> {
                require(STABLE_ID.matches(value)) { "Application ID is invalid" }
                StreamDeckApplicationAction(value)
            }
            EditorActionType.SYSTEM_INFO -> {
                require(value in ALLOWED_SYSTEM_INFO_TARGETS) {
                    "System information target is not supported"
                }
                StreamDeckSystemInfoAction(value)
            }
        }
    }

    private fun validateKey(value: String): String {
        require(value.isNotEmpty() && value.length <= MAX_KEY_LENGTH) {
            "Key name is invalid"
        }
        return value
    }

    companion object {
        fun from(
            snapshot: StreamDeckProfileSnapshot,
            selectedButtonId: String = snapshot.activePage.buttons.first().id,
        ): ProfileEditorDraft {
            val button = snapshot.activePage.buttons.single { it.id == selectedButtonId }
            val action = button.action
            return ProfileEditorDraft(
                profileName = snapshot.profileName,
                pageTitle = snapshot.activePage.title,
                selectedButtonId = button.id,
                title = button.title,
                row = button.row.toString(),
                column = button.column.toString(),
                icon = button.icon.orEmpty(),
                color = button.color.orEmpty(),
                actionType = action?.editorType ?: EditorActionType.HOTKEY,
                modifiers = (action as? StreamDeckHotkeyAction)?.modifiers?.joinToString(", ")
                    ?: "ctrl",
                actionValue = action?.editorValue.orEmpty(),
            )
        }

        private val HEX_COLOR = Regex("#[0-9A-Fa-f]{6}(?:[0-9A-Fa-f]{2})?")
        private val STABLE_ID = Regex("^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
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
        private val ALLOWED_SYSTEM_INFO_TARGETS = setOf("cpu", "memory", "gpu")
        private const val MAX_KEY_LENGTH = 32
        private const val MAX_TEXT_LENGTH = 2000
    }
}

private val StreamDeckAction.editorType: EditorActionType
    get() = when (this) {
        is StreamDeckHotkeyAction -> EditorActionType.HOTKEY
        is StreamDeckKeyAction -> EditorActionType.KEY
        is StreamDeckMediaAction -> EditorActionType.MEDIA
        is StreamDeckTextAction -> EditorActionType.TEXT
        is StreamDeckUrlAction -> EditorActionType.URL
        is StreamDeckApplicationAction -> EditorActionType.APPLICATION
        is StreamDeckSystemInfoAction -> EditorActionType.SYSTEM_INFO
    }

private val StreamDeckAction.editorValue: String
    get() = when (this) {
        is StreamDeckHotkeyAction -> key
        is StreamDeckKeyAction -> key
        is StreamDeckMediaAction -> command
        is StreamDeckTextAction -> text
        is StreamDeckUrlAction -> url
        is StreamDeckApplicationAction -> appId
        is StreamDeckSystemInfoAction -> target
    }
