package br.com.gustavo.streamdeck.ui.settings

import androidx.test.core.app.ApplicationProvider
import org.junit.Assert.assertEquals
import org.junit.Test

class StreamDeckPreferencesInstrumentedTest {
    @Test
    fun preferencias_sobrevivem_ao_recarregamento_do_store() {
        val context = ApplicationProvider.getApplicationContext<android.content.Context>()
        val store = StreamDeckPreferencesStore(context)
        val original = store.load()
        val expected = StreamDeckPreferences(
            theme = ThemePreference.LIGHT,
            density = DeckDensity.COMPACT,
            reduceMotion = true,
            hapticsEnabled = false,
        )
        try {
            store.save(expected)
            assertEquals(expected, store.load())
        } finally {
            store.save(original)
        }
    }
}
