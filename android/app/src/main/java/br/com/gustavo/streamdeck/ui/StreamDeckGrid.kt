package br.com.gustavo.streamdeck.ui

import android.graphics.Color as AndroidColor
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import br.com.gustavo.streamdeck.R
import br.com.gustavo.streamdeck.network.StreamDeckButton
import br.com.gustavo.streamdeck.network.StreamDeckPage

enum class ButtonExecutionState {
    IDLE,
    EXECUTING,
    COMPLETED,
    REJECTED,
}

@Composable
fun StreamDeckGrid(
    page: StreamDeckPage,
    buttonStates: Map<String, ButtonExecutionState>,
    onButtonPress: (StreamDeckButton) -> Unit,
    modifier: Modifier = Modifier,
) {
    val cells = GridLayout.cells(page)
    LazyVerticalGrid(
        columns = GridCells.Fixed(page.columns),
        modifier = modifier,
        horizontalArrangement = Arrangement.spacedBy(10.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp),
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
            .background(MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.35f))
            .semantics { contentDescription = description },
    )
}

@Composable
private fun ActionGridButton(
    button: StreamDeckButton,
    executionState: ButtonExecutionState,
    onClick: () -> Unit,
) {
    val statusText = executionState.label()
    val description = stringResource(
        R.string.action_button_description,
        button.title,
        statusText,
    )
    val containerColor = buttonColor(button, executionState)
    Button(
        modifier = Modifier
            .aspectRatio(1f)
            .semantics { contentDescription = description },
        onClick = onClick,
        enabled = executionState != ButtonExecutionState.EXECUTING,
        colors = ButtonDefaults.buttonColors(
            containerColor = containerColor,
            contentColor = Color.White,
            disabledContainerColor = containerColor.copy(alpha = 0.72f),
            disabledContentColor = Color.White.copy(alpha = 0.92f),
        ),
    ) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(4.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center,
        ) {
            if (executionState == ButtonExecutionState.EXECUTING) {
                CircularProgressIndicator(
                    modifier = Modifier.size(30.dp),
                    color = Color.White,
                    strokeWidth = 3.dp,
                )
            } else {
                Text(
                    text = iconGlyph(button.icon),
                    style = MaterialTheme.typography.headlineMedium,
                )
            }
            Spacer(modifier = Modifier.size(6.dp))
            Text(
                text = button.title,
                maxLines = 3,
                overflow = TextOverflow.Ellipsis,
                style = MaterialTheme.typography.labelLarge,
                textAlign = TextAlign.Center,
            )
            if (executionState != ButtonExecutionState.IDLE) {
                Text(
                    text = statusText,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                    style = MaterialTheme.typography.labelSmall,
                    textAlign = TextAlign.Center,
                )
            }
        }
    }
}

@Composable
private fun ButtonExecutionState.label(): String = when (this) {
    ButtonExecutionState.IDLE -> stringResource(R.string.action_state_ready)
    ButtonExecutionState.EXECUTING -> stringResource(R.string.action_state_executing)
    ButtonExecutionState.COMPLETED -> stringResource(R.string.action_state_completed)
    ButtonExecutionState.REJECTED -> stringResource(R.string.action_state_rejected)
}

@Composable
private fun buttonColor(
    button: StreamDeckButton,
    executionState: ButtonExecutionState,
): Color = when (executionState) {
    ButtonExecutionState.COMPLETED -> MaterialTheme.colorScheme.tertiary
    ButtonExecutionState.REJECTED -> MaterialTheme.colorScheme.error
    ButtonExecutionState.EXECUTING -> MaterialTheme.colorScheme.secondary
    ButtonExecutionState.IDLE -> button.color?.let { color ->
        Color(AndroidColor.parseColor(color))
    } ?: MaterialTheme.colorScheme.primary
}

private fun iconGlyph(icon: String?): String = when (icon) {
    "keyboard" -> "⌨"
    "play_pause" -> "▶"
    "book" -> "▤"
    else -> "●"
}
