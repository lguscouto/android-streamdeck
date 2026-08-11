package br.com.gustavo.streamdeck

import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.safeDrawing
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import br.com.gustavo.streamdeck.ui.settings.StreamDeckPreferences
import br.com.gustavo.streamdeck.ui.settings.StreamDeckPreferencesStore
import br.com.gustavo.streamdeck.ui.shell.PairingScreen
import br.com.gustavo.streamdeck.ui.theme.StreamDeckTheme

@Composable
fun StreamDeckApp() {
    val context = LocalContext.current
    val preferencesStore = remember(context) { StreamDeckPreferencesStore(context) }
    var preferences by remember(preferencesStore) {
        mutableStateOf<StreamDeckPreferences>(preferencesStore.load())
    }
    StreamDeckTheme(themePreference = preferences.theme) {
        Surface(
            modifier = Modifier
                .fillMaxSize()
                .windowInsetsPadding(WindowInsets.safeDrawing),
            color = MaterialTheme.colorScheme.background,
        ) {
            PairingScreen(
                preferences = preferences,
                onPreferencesChange = { updated ->
                    preferences = updated
                    preferencesStore.save(updated)
                },
            )
        }
    }
}
