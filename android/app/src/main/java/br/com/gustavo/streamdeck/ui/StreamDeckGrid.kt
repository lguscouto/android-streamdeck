package br.com.gustavo.streamdeck.ui

import android.graphics.Color as AndroidColor
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.spring
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.interaction.collectIsPressedAsState
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.sizeIn
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.graphics.lerp
import androidx.compose.ui.graphics.luminance
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.role
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.stateDescription
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import br.com.gustavo.streamdeck.R
import br.com.gustavo.streamdeck.network.StreamDeckButton
import br.com.gustavo.streamdeck.network.StreamDeckPage
import br.com.gustavo.streamdeck.ui.ButtonExecutionState
import br.com.gustavo.streamdeck.ui.theme.CommandColors
import br.com.gustavo.streamdeck.ui.theme.CommandShapes
import br.com.gustavo.streamdeck.ui.theme.CommandSpacing
import br.com.gustavo.streamdeck.ui.settings.DeckDensity
import br.com.gustavo.streamdeck.ui.icons.CommandIconRegistry

/** Renders the server-defined logical grid as a full-screen command surface. */
@Composable
fun StreamDeckGrid(
    page: StreamDeckPage,
    buttonStates: Map<String, ButtonExecutionState>,
    onButtonPress: (StreamDeckButton) -> Unit,
    modifier: Modifier = Modifier,
    density: DeckDensity = DeckDensity.COMFORTABLE,
    reduceMotion: Boolean = false,
    hapticsEnabled: Boolean = true,
) {
    val metrics = density.metrics()
    val cells = GridLayout.cells(page)
    LazyVerticalGrid(
        columns = GridCells.Fixed(page.columns.coerceAtLeast(1)),
        modifier = modifier,
        contentPadding = PaddingValues(metrics.gap),
        horizontalArrangement = Arrangement.spacedBy(metrics.gap),
        verticalArrangement = Arrangement.spacedBy(metrics.gap),
    ) {
        items(
            items = cells,
            key = { cell -> "${cell.row}-${cell.column}" },
        ) { cell ->
            val button = cell.button
            if (button == null) {
                EmptyGridCell()
            } else {
                ActionGridButton(
                    button = button,
                    executionState = buttonStates[button.id] ?: ButtonExecutionState.IDLE,
                    onClick = { onButtonPress(button) },
                    metrics = metrics,
                    reduceMotion = reduceMotion,
                    hapticsEnabled = hapticsEnabled,
                )
            }
        }
    }
}

@Composable
private fun EmptyGridCell() {
    val description = stringResource(R.string.empty_grid_cell)
    Box(
        modifier = Modifier
            .aspectRatio(1f)
            .semantics { contentDescription = description },
    )
}

@Composable
private fun ActionGridButton(
    button: StreamDeckButton,
    executionState: ButtonExecutionState,
    onClick: () -> Unit,
    metrics: DeckLayoutMetrics,
    reduceMotion: Boolean,
    hapticsEnabled: Boolean,
) {
    val statusText = executionState.label()
    val hapticFeedback = LocalHapticFeedback.current
    val accessibleTitle = if (button.icon == "spotify") {
        stringResource(R.string.spotify_active_session_a11y)
    } else {
        button.title
    }
    val description = stringResource(
        R.string.action_button_description,
        accessibleTitle,
        statusText,
    )
    val interactionSource = remember { MutableInteractionSource() }
    val pressed by interactionSource.collectIsPressedAsState()
    val targetScale = if (pressed) 0.96f else 1f
    val animatedScale by animateFloatAsState(
        targetValue = targetScale,
        animationSpec = spring(stiffness = 700f),
        label = "command-key-scale",
    )
    val scale = if (reduceMotion) 1f else animatedScale
    val baseColor = buttonColor(button)
    val containerColor = when (executionState) {
        ButtonExecutionState.IDLE -> MaterialTheme.colorScheme.surfaceVariant
        ButtonExecutionState.EXECUTING -> lerp(MaterialTheme.colorScheme.surfaceVariant, baseColor, 0.28f)
        ButtonExecutionState.COMPLETED -> lerp(MaterialTheme.colorScheme.surfaceVariant, CommandColors.Success, 0.32f)
        ButtonExecutionState.REJECTED -> lerp(MaterialTheme.colorScheme.surfaceVariant, CommandColors.Danger, 0.32f)
    }
    val contentColor = if (containerColor.luminance() > 0.58f) {
        CommandColors.Obsidian
    } else {
        CommandColors.Mist
    }
    val accentColor = when (executionState) {
        ButtonExecutionState.IDLE,
        ButtonExecutionState.EXECUTING,
        -> baseColor
        ButtonExecutionState.COMPLETED -> CommandColors.Success
        ButtonExecutionState.REJECTED -> CommandColors.Danger
    }
    val iconColor = if (contrastRatio(accentColor, containerColor) >= 3f) {
        accentColor
    } else {
        contentColor
    }

    Surface(
        modifier = Modifier
            .aspectRatio(1f)
            .sizeIn(minWidth = 48.dp, minHeight = 48.dp)
            .graphicsScale(scale)
            .clip(CommandShapes.key)
            .clickable(
                interactionSource = interactionSource,
                indication = null,
                enabled = executionState != ButtonExecutionState.EXECUTING,
                role = Role.Button,
                onClick = {
                    if (hapticsEnabled) {
                        hapticFeedback.performHapticFeedback(HapticFeedbackType.LongPress)
                    }
                    onClick()
                },
            )
            .semantics {
                contentDescription = description
                stateDescription = statusText
                liveRegion = LiveRegionMode.Polite
                role = Role.Button
            },
        shape = CommandShapes.key,
        color = containerColor,
        contentColor = contentColor,
        border = BorderStroke(1.5.dp, accentColor.copy(alpha = if (pressed) 1f else 0.72f)),
        tonalElevation = 2.dp,
        shadowElevation = if (pressed) 0.dp else 3.dp,
    ) {
        Box(modifier = Modifier.fillMaxSize()) {
            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(metrics.innerPadding),
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.Center,
            ) {
                Icon(
                    imageVector = CommandIconRegistry.iconFor(button.icon),
                    contentDescription = null,
                    modifier = Modifier.size(metrics.iconSize),
                    tint = iconColor,
                )
                Text(
                    text = button.title.ifBlank { "Comando" },
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(top = CommandSpacing.xs),
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis,
                    style = MaterialTheme.typography.labelLarge,
                    textAlign = TextAlign.Center,
                )
            }
            if (executionState == ButtonExecutionState.EXECUTING) {
                CircularProgressIndicator(
                    modifier = Modifier
                        .align(Alignment.TopEnd)
                        .padding(CommandSpacing.xs)
                        .size(18.dp),
                    color = contentColor,
                    strokeWidth = 2.dp,
                )
            }
            if (executionState != ButtonExecutionState.IDLE) {
                Surface(
                    modifier = Modifier
                        .align(Alignment.BottomCenter)
                        .padding(bottom = CommandSpacing.xs),
                    shape = CommandShapes.pill,
                    color = contentColor.copy(alpha = 0.16f),
                    contentColor = contentColor,
                ) {
                    Text(
                        text = statusText,
                        modifier = Modifier.padding(horizontal = CommandSpacing.xs, vertical = 2.dp),
                        style = MaterialTheme.typography.labelSmall,
                    )
                }
            }
        }
    }
}

private fun Modifier.graphicsScale(scale: Float): Modifier =
    this.graphicsLayer {
        scaleX = scale
        scaleY = scale
    }

@Composable
private fun ButtonExecutionState.label(): String = when (this) {
    ButtonExecutionState.IDLE -> stringResource(R.string.action_state_ready)
    ButtonExecutionState.EXECUTING -> stringResource(R.string.action_state_executing)
    ButtonExecutionState.COMPLETED -> stringResource(R.string.action_state_completed)
    ButtonExecutionState.REJECTED -> stringResource(R.string.action_state_rejected)
}

private data class DeckLayoutMetrics(
    val gap: Dp,
    val innerPadding: Dp,
    val iconSize: Dp,
)

private fun DeckDensity.metrics(): DeckLayoutMetrics = when (this) {
    DeckDensity.COMPACT -> DeckLayoutMetrics(
        gap = 4.dp,
        innerPadding = 8.dp,
        iconSize = 24.dp,
    )
    DeckDensity.COMFORTABLE -> DeckLayoutMetrics(
        gap = CommandSpacing.xs,
        innerPadding = CommandSpacing.sm,
        iconSize = 30.dp,
    )
    DeckDensity.SPACIOUS -> DeckLayoutMetrics(
        gap = CommandSpacing.sm,
        innerPadding = CommandSpacing.md,
        iconSize = 36.dp,
    )
}

private fun contrastRatio(foreground: Color, background: Color): Float {
    val foregroundLuminance = foreground.luminance()
    val backgroundLuminance = background.luminance()
    val lighter = maxOf(foregroundLuminance, backgroundLuminance)
    val darker = minOf(foregroundLuminance, backgroundLuminance)
    return (lighter + 0.05f) / (darker + 0.05f)
}

private fun buttonColor(button: StreamDeckButton): Color {
    val parsed = button.color?.let { raw ->
        runCatching { Color(AndroidColor.parseColor(raw)) }.getOrNull()
    }
    return parsed ?: CommandColors.Slate
}
