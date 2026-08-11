package br.com.gustavo.streamdeck.ui

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
