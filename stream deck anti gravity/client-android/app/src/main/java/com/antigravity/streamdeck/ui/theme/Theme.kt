package com.antigravity.streamdeck.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

enum class DeckTheme {
    CYBERPUNK,
    OLED_DARK,
    NORDIC_SLATE,
    GLASSMORPHISM
}

private val CyberpunkColorScheme = darkColorScheme(
    primary = NeonBlue,
    secondary = NeonPink,
    tertiary = NeonPurple,
    background = NeonDarkBg,
    surface = NeonPanelBg,
    onPrimary = Color.Black,
    onBackground = Color.White
)

private val OledColorScheme = darkColorScheme(
    primary = OledAccent,
    background = OledBg,
    surface = OledPanel,
    onPrimary = Color.Black,
    onBackground = Color.White
)

private val NordicColorScheme = darkColorScheme(
    primary = NordicAccent,
    background = NordicBg,
    surface = NordicPanel,
    onPrimary = Color.Black,
    onBackground = Color.White
)

private val GlassColorScheme = darkColorScheme(
    primary = Color(0xFF89B4FA),
    background = Color(0xFF11111B),
    surface = GlassBg,
    onPrimary = Color.Black,
    onBackground = Color.White
)

@Composable
fun AntiGravityTheme(
    theme: DeckTheme = DeckTheme.CYBERPUNK,
    content: @Composable () -> Unit
) {
    val colorScheme = when (theme) {
        DeckTheme.CYBERPUNK -> CyberpunkColorScheme
        DeckTheme.OLED_DARK -> OledColorScheme
        DeckTheme.NORDIC_SLATE -> NordicColorScheme
        DeckTheme.GLASSMORPHISM -> GlassColorScheme
    }

    MaterialTheme(
        colorScheme = colorScheme,
        content = content
    )
}
