package br.com.gustavo.streamdeck.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import br.com.gustavo.streamdeck.ui.settings.ThemePreference

private val CommandDarkColors = darkColorScheme(
    primary = CommandColors.Pulse,
    onPrimary = CommandColors.Obsidian,
    primaryContainer = CommandColors.PulseDark,
    onPrimaryContainer = CommandColors.Mist,
    secondary = CommandColors.Info,
    onSecondary = CommandColors.Obsidian,
    tertiary = CommandColors.Success,
    onTertiary = CommandColors.Obsidian,
    background = CommandColors.Obsidian,
    onBackground = CommandColors.Mist,
    surface = CommandColors.Graphite,
    onSurface = CommandColors.Mist,
    surfaceVariant = CommandColors.Slate,
    onSurfaceVariant = CommandColors.Ash,
    outline = CommandColors.Steel,
    error = CommandColors.Danger,
    onError = CommandColors.Mist,
)

private val CommandLightColors = lightColorScheme(
    primary = CommandColors.LightAccent,
    onPrimary = CommandColors.Mist,
    primaryContainer = CommandColors.Pulse,
    onPrimaryContainer = CommandColors.LightText,
    secondary = ColorTokens.LightInfo,
    onSecondary = CommandColors.LightText,
    tertiary = ColorTokens.LightSuccess,
    onTertiary = CommandColors.LightText,
    background = CommandColors.LightBackground,
    onBackground = CommandColors.LightText,
    surface = CommandColors.LightSurface,
    onSurface = CommandColors.LightText,
    surfaceVariant = CommandColors.LightElevated,
    onSurfaceVariant = ColorTokens.LightMuted,
    outline = CommandColors.LightBorder,
    error = ColorTokens.LightDanger,
    onError = CommandColors.Mist,
)

private object ColorTokens {
    val LightInfo = androidx.compose.ui.graphics.Color(0xFF2167B2)
    val LightSuccess = androidx.compose.ui.graphics.Color(0xFF167A46)
    val LightDanger = androidx.compose.ui.graphics.Color(0xFFB3263E)
    val LightMuted = androidx.compose.ui.graphics.Color(0xFF536174)
}

@Composable
fun StreamDeckTheme(
    themePreference: ThemePreference = ThemePreference.SYSTEM,
    content: @Composable () -> Unit,
) {
    val systemDark = isSystemInDarkTheme()
    val darkTheme = when (themePreference) {
        ThemePreference.SYSTEM -> systemDark
        ThemePreference.DARK -> true
        ThemePreference.LIGHT -> false
    }
    MaterialTheme(
        colorScheme = if (darkTheme) CommandDarkColors else CommandLightColors,
        typography = CommandTypography,
        shapes = CommandShapeScheme,
        content = content,
    )
}
