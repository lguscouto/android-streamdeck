package br.com.gustavo.streamdeck.ui.settings

import android.content.Context
import androidx.compose.runtime.Immutable

/** User-facing theme policy. */
enum class ThemePreference {
    SYSTEM,
    DARK,
    LIGHT,
}

/** Deck spacing policy; compact is useful on small phones, spacious on tablets. */
enum class DeckDensity {
    COMPACT,
    COMFORTABLE,
    SPACIOUS,
}

@Immutable
data class StreamDeckPreferences(
    val theme: ThemePreference = ThemePreference.SYSTEM,
    val density: DeckDensity = DeckDensity.COMFORTABLE,
    val reduceMotion: Boolean = false,
    val hapticsEnabled: Boolean = true,
    val onboardingVersion: Int = 0,
)

/** Small, synchronous persistence boundary for settings that must survive restarts. */
class StreamDeckPreferencesStore(
    context: Context,
    storageNamespace: String? = null,
) {
    private val preferences = context.applicationContext.getSharedPreferences(
        storageNamespace?.let { "${FILE_NAME}_$it" } ?: FILE_NAME,
        Context.MODE_PRIVATE,
    )

    fun load(): StreamDeckPreferences = StreamDeckPreferences(
        theme = preferences.getString(KEY_THEME, null)
            ?.let { raw -> runCatching { ThemePreference.valueOf(raw) }.getOrNull() }
            ?: ThemePreference.SYSTEM,
        density = preferences.getString(KEY_DENSITY, null)
            ?.let { raw -> runCatching { DeckDensity.valueOf(raw) }.getOrNull() }
            ?: DeckDensity.COMFORTABLE,
        reduceMotion = preferences.getBoolean(KEY_REDUCE_MOTION, false),
        hapticsEnabled = preferences.getBoolean(KEY_HAPTICS, true),
        onboardingVersion = preferences.getInt(KEY_ONBOARDING_VERSION, 0),
    )

    fun save(value: StreamDeckPreferences) {
        preferences.edit()
            .putString(KEY_THEME, value.theme.name)
            .putString(KEY_DENSITY, value.density.name)
            .putBoolean(KEY_REDUCE_MOTION, value.reduceMotion)
            .putBoolean(KEY_HAPTICS, value.hapticsEnabled)
            .putInt(KEY_ONBOARDING_VERSION, value.onboardingVersion)
            .apply()
    }

    private companion object {
        const val FILE_NAME = "streamdeck_preferences"
        const val KEY_THEME = "theme"
        const val KEY_DENSITY = "density"
        const val KEY_REDUCE_MOTION = "reduce_motion"
        const val KEY_HAPTICS = "haptics_enabled"
        const val KEY_ONBOARDING_VERSION = "onboarding_version"
    }
}
