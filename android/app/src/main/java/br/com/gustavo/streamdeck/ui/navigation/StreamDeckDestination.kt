package br.com.gustavo.streamdeck.ui.navigation

/** Top-level product destinations. Transient network state remains in AppState. */
sealed interface StreamDeckDestination {
    data object Deck : StreamDeckDestination
    data object Editor : StreamDeckDestination
    data object Profiles : StreamDeckDestination
    data object Settings : StreamDeckDestination
}
