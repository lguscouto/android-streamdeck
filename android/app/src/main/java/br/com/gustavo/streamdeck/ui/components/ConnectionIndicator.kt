package br.com.gustavo.streamdeck.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import br.com.gustavo.streamdeck.R
import br.com.gustavo.streamdeck.ui.theme.CommandColors
import br.com.gustavo.streamdeck.ui.theme.CommandShapes
import br.com.gustavo.streamdeck.ui.theme.CommandSpacing

enum class ConnectionStatus {
    DISCONNECTED,
    CONNECTING,
    CONNECTED,
    ERROR,
}

@Composable
fun ConnectionPill(
    status: ConnectionStatus,
    modifier: Modifier = Modifier,
) {
    val label = when (status) {
        ConnectionStatus.DISCONNECTED -> stringResource(R.string.status_disconnected)
        ConnectionStatus.CONNECTING -> stringResource(R.string.status_connecting)
        ConnectionStatus.CONNECTED -> stringResource(R.string.status_connected)
        ConnectionStatus.ERROR -> stringResource(R.string.status_error)
    }
    val color = when (status) {
        ConnectionStatus.DISCONNECTED -> CommandColors.Ash
        ConnectionStatus.CONNECTING -> CommandColors.Warning
        ConnectionStatus.CONNECTED -> CommandColors.Success
        ConnectionStatus.ERROR -> CommandColors.Danger
    }
    Surface(
        modifier = modifier,
        shape = CommandShapes.pill,
        color = color.copy(alpha = 0.14f),
        contentColor = color,
    ) {
        Row(
            modifier = Modifier.padding(horizontal = CommandSpacing.sm, vertical = 6.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(CommandSpacing.xs),
        ) {
            androidx.compose.foundation.layout.Box(
                modifier = Modifier
                    .size(7.dp)
                    .background(color, CircleShape),
            )
            Text(
                text = label,
                style = androidx.compose.material3.MaterialTheme.typography.labelMedium,
            )
        }
    }
}
