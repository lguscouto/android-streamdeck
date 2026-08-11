package br.com.gustavo.streamdeck.ui.components

import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.KeyboardArrowLeft
import androidx.compose.material.icons.automirrored.outlined.KeyboardArrowRight
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.role
import androidx.compose.ui.semantics.semantics
import br.com.gustavo.streamdeck.network.StreamDeckPage
import br.com.gustavo.streamdeck.ui.theme.CommandShapes
import br.com.gustavo.streamdeck.ui.theme.CommandSpacing

@Composable
fun PagePager(
    pages: List<StreamDeckPage>,
    activePageId: String,
    enabled: Boolean = true,
    onPageSelected: (StreamDeckPage) -> Unit,
) {
    if (pages.size <= 1) return
    val orderedPages = pages.sortedBy(StreamDeckPage::order)
    val activeIndex = orderedPages.indexOfFirst { it.id == activePageId }
        .takeIf { it >= 0 }
        ?: 0
    val previous = orderedPages.getOrNull(activeIndex - 1)
    val next = orderedPages.getOrNull(activeIndex + 1)

    Row(
        modifier = Modifier.fillMaxWidth(),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(CommandSpacing.xxs),
    ) {
        IconButton(
            onClick = { previous?.let(onPageSelected) },
            enabled = enabled && previous != null,
        ) {
            Icon(
                Icons.AutoMirrored.Outlined.KeyboardArrowLeft,
                contentDescription = "Página anterior",
            )
        }
        Row(
            modifier = Modifier
                .weight(1f)
                .horizontalScroll(rememberScrollState()),
            horizontalArrangement = Arrangement.spacedBy(CommandSpacing.xxs),
        ) {
            orderedPages.forEach { page ->
                val selected = page.id == activePageId
                Surface(
                    modifier = Modifier.semantics { role = Role.Tab },
                    onClick = { onPageSelected(page) },
                    enabled = enabled,
                    shape = CommandShapes.pill,
                    color = if (selected) {
                        MaterialTheme.colorScheme.primaryContainer
                    } else {
                        MaterialTheme.colorScheme.surfaceVariant
                    },
                    contentColor = if (selected) {
                        MaterialTheme.colorScheme.onPrimaryContainer
                    } else {
                        MaterialTheme.colorScheme.onSurfaceVariant
                    },
                ) {
                    Text(
                        text = page.title,
                        modifier = Modifier.padding(
                            horizontal = CommandSpacing.sm,
                            vertical = CommandSpacing.xs,
                        ),
                        style = MaterialTheme.typography.labelLarge,
                        maxLines = 1,
                    )
                }
            }
        }
        IconButton(
            onClick = { next?.let(onPageSelected) },
            enabled = enabled && next != null,
        ) {
            Icon(
                Icons.AutoMirrored.Outlined.KeyboardArrowRight,
                contentDescription = "Próxima página",
            )
        }
    }
}
