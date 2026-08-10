package com.antigravity.streamdeck.ui.components

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.GridItemSpan
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.antigravity.streamdeck.data.model.ButtonModel
import com.antigravity.streamdeck.data.model.GridConfig

@Composable
fun DeckGrid(
    gridConfig: GridConfig,
    buttons: List<ButtonModel>,
    serverIp: String,
    onButtonClick: (ButtonModel) -> Unit,
    modifier: Modifier = Modifier
) {
    val cols = if (gridConfig.cols > 0) gridConfig.cols else 4

    LazyVerticalGrid(
        columns = GridCells.Fixed(cols),
        modifier = modifier
            .fillMaxSize()
            .padding(12.dp),
        horizontalArrangement = Arrangement.spacedBy(10.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp)
    ) {
        items(
            items = buttons,
            key = { it.id },
            span = { button ->
                val spanVal = (button.colSpan ?: 1).coerceAtMost(cols)
                GridItemSpan(spanVal)
            }
        ) { button ->
            DeckButton(
                button = button,
                serverIp = serverIp,
                onClick = { onButtonClick(button) }
            )
        }
    }
}
