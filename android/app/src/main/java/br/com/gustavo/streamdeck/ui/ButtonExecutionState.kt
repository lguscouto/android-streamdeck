package br.com.gustavo.streamdeck.ui

import br.com.gustavo.streamdeck.network.StreamDeckButton
import br.com.gustavo.streamdeck.network.StreamDeckSystemInfoAction

/**
 * Visual lifecycle of a pressed command. The network acknowledgement remains
 * authoritative; this enum only describes the transient UI state.
 */
enum class ButtonExecutionState {
    IDLE,
    EXECUTING,
    COMPLETED,
    REJECTED,
}

internal fun completedActionMessage(
    button: StreamDeckButton?,
    acknowledgementMessage: String?,
    defaultMessage: String,
): String {
    val action = button?.action as? StreamDeckSystemInfoAction ?: return defaultMessage
    val expectedMessage = when (action.target) {
        "cpu" -> CPU_SYSTEM_INFO_MESSAGE
        "memory" -> MEMORY_SYSTEM_INFO_MESSAGE
        "gpu" -> GPU_SYSTEM_INFO_MESSAGE
        else -> return defaultMessage
    }
    return acknowledgementMessage?.takeIf(expectedMessage::matches) ?: defaultMessage
}

private val CPU_SYSTEM_INFO_MESSAGE = Regex(
    "^CPU: \\d{1,3}% \\| (?:N/A|-?\\d{1,3}°C)$",
)
private val MEMORY_SYSTEM_INFO_MESSAGE = Regex(
    "^RAM: \\d{1,3}% \\(\\d+(?:\\.\\d)/\\d+(?:\\.\\d) GB\\)$",
)
private val GPU_SYSTEM_INFO_MESSAGE = Regex(
    "^GPU: (?:N/A|-?\\d{1,3}°C) \\| VRAM: (?:N/A|\\d+(?:\\.\\d)?/\\d+(?:\\.\\d)? GB \\((?:\\d{1,3})%\\))$",
)
