package br.com.gustavo.streamdeck.ui

import android.graphics.Color as AndroidColor
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.Apps
import androidx.compose.material.icons.outlined.Build
import androidx.compose.material.icons.outlined.Keyboard
import androidx.compose.material.icons.automirrored.outlined.MenuBook
import androidx.compose.material.icons.outlined.MusicNote
import androidx.compose.material.icons.outlined.PlayArrow
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.luminance
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.stateDescription
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import br.com.gustavo.streamdeck.R
import br.com.gustavo.streamdeck.network.StreamDeckButton
import br.com.gustavo.streamdeck.network.StreamDeckProfileSnapshot
import br.com.gustavo.streamdeck.ui.theme.CommandColors
import br.com.gustavo.streamdeck.ui.theme.CommandShapes
import br.com.gustavo.streamdeck.ui.theme.CommandSpacing

@Composable
fun ProfileEditorScreen(
    snapshot: StreamDeckProfileSnapshot,
    draft: ProfileEditorDraft,
    saving: Boolean,
    errorMessage: String?,
    hasChangesToRevert: Boolean,
    onDraftChange: (ProfileEditorDraft) -> Unit,
    onSave: () -> Unit,
    onCancel: () -> Unit,
    onRevert: () -> Unit,
) {
    var actionMenuExpanded by remember { mutableStateOf(false) }
    var iconMenuExpanded by remember { mutableStateOf(false) }
    val mediaCommands = listOf(
        "play_pause",
        "next",
        "previous",
        "stop",
        "volume_up",
        "volume_down",
        "mute",
    )
    val selectedButton = snapshot.activePage.buttons
        .singleOrNull { it.id == draft.selectedButtonId }
    val actionLabel = actionTypeLabel(draft.actionType)
    val previewColor = draft.color.takeIf { it.isNotBlank() }
        ?.let { runCatching { Color(AndroidColor.parseColor(it)) }.getOrNull() }
        ?: CommandColors.Slate
    val previewContentColor = if (previewColor.luminance() > 0.58f) {
        CommandColors.Obsidian
    } else {
        CommandColors.Mist
    }

    Box(modifier = Modifier.fillMaxSize()) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .verticalScroll(rememberScrollState())
                .padding(horizontal = CommandSpacing.md, vertical = CommandSpacing.sm)
                .padding(bottom = 92.dp),
            verticalArrangement = Arrangement.spacedBy(CommandSpacing.sm),
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Column(modifier = Modifier.weight(1f)) {
                    Text("Editar deck", style = MaterialTheme.typography.headlineSmall)
                    Text(
                        "Revisão ${snapshot.revision} · ${snapshot.activePage.title}",
                        style = MaterialTheme.typography.labelMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                Text(
                    text = "ESC",
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }

            CommandButtonPreview(
                title = draft.title,
                icon = draft.icon,
                color = previewColor,
                contentColor = previewContentColor,
                actionLabel = actionLabel,
            )

            EditorCard(title = "Perfil e página") {
                OutlinedTextField(
                    modifier = Modifier.fillMaxWidth(),
                    value = draft.profileName,
                    onValueChange = { onDraftChange(draft.copy(profileName = it)) },
                    label = { Text("Nome do perfil") },
                    singleLine = true,
                    enabled = !saving,
                )
                OutlinedTextField(
                    modifier = Modifier.fillMaxWidth(),
                    value = draft.pageTitle,
                    onValueChange = { onDraftChange(draft.copy(pageTitle = it)) },
                    label = { Text("Título da página ativa") },
                    singleLine = true,
                    enabled = !saving,
                )
            }

            EditorCard(title = "Tecla selecionada") {
                Row(
                    modifier = Modifier.horizontalScroll(rememberScrollState()),
                    horizontalArrangement = Arrangement.spacedBy(CommandSpacing.xs),
                ) {
                    snapshot.activePage.buttons.forEach { button ->
                        ButtonSelector(
                            button = button,
                            selected = button.id == draft.selectedButtonId,
                            enabled = !saving,
                            onClick = { onDraftChange(draft.selectButton(snapshot, button.id)) },
                        )
                    }
                }
                Text(
                    text = selectedButton?.let { "Posição atual: linha ${it.row + 1}, coluna ${it.column + 1}" }
                        ?: "Selecione uma tecla para editar",
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }

            EditorCard(title = "Aparência") {
                OutlinedTextField(
                    modifier = Modifier.fillMaxWidth(),
                    value = draft.title,
                    onValueChange = { onDraftChange(draft.copy(title = it)) },
                    label = { Text("Título da tecla") },
                    singleLine = true,
                    enabled = !saving,
                )
                Box {
                    OutlinedButton(
                        modifier = Modifier.fillMaxWidth(),
                        onClick = { iconMenuExpanded = true },
                        enabled = !saving,
                    ) {
                        Icon(iconFor(draft.icon), contentDescription = null)
                        Spacer(modifier = Modifier.size(CommandSpacing.xs))
                        Text("Ícone: ${draft.icon.ifBlank { "comando" }}")
                    }
                    DropdownMenu(
                        expanded = iconMenuExpanded,
                        onDismissRequest = { iconMenuExpanded = false },
                    ) {
                        listOf(
                            "keyboard" to "Teclado",
                            "play_pause" to "Reprodução",
                            "book" to "Painel",
                            "media" to "Mídia",
                            "application" to "Aplicativo",
                            "build" to "Comando",
                        ).forEach { (id, label) ->
                            DropdownMenuItem(
                                text = { Text(label) },
                                leadingIcon = { Icon(iconFor(id), contentDescription = null) },
                                onClick = {
                                    iconMenuExpanded = false
                                    onDraftChange(draft.copy(icon = id))
                                },
                            )
                        }
                    }
                }
                Text("Cor sugerida", style = MaterialTheme.typography.labelMedium)
                Row(horizontalArrangement = Arrangement.spacedBy(CommandSpacing.xs)) {
                    listOf(
                        "#182131" to "Grafite",
                        "#38D9C5" to "Pulse",
                        "#5AA7FF" to "Info",
                        "#42D17B" to "Sucesso",
                        "#FFB648" to "Atenção",
                        "#FF5D73" to "Erro",
                    ).forEach { (hex, label) ->
                        val swatch = Color(AndroidColor.parseColor(hex))
                        Surface(
                            modifier = Modifier
                                .size(48.dp)
                                .clip(CommandShapes.pill)
                                .clickable(enabled = !saving) {
                                    onDraftChange(draft.copy(color = hex))
                                }
                                .semantics { contentDescription = "Usar cor $label" },
                            shape = CommandShapes.pill,
                            color = swatch,
                            border = if (draft.color.equals(hex, ignoreCase = true)) {
                                androidx.compose.foundation.BorderStroke(2.dp, MaterialTheme.colorScheme.onSurface)
                            } else {
                                null
                            },
                        ) {}
                    }
                }
                OutlinedTextField(
                    modifier = Modifier.fillMaxWidth(),
                    value = draft.color,
                    onValueChange = { onDraftChange(draft.copy(color = it)) },
                    label = { Text("HEX personalizado, opcional") },
                    supportingText = { Text("Use #RRGGBB ou #RRGGBBAA") },
                    singleLine = true,
                    enabled = !saving,
                )
            }

            EditorCard(title = "Ação") {
                Box {
                    OutlinedButton(
                        modifier = Modifier.fillMaxWidth(),
                        onClick = { actionMenuExpanded = true },
                        enabled = !saving,
                    ) {
                        Text("Tipo: $actionLabel")
                    }
                    DropdownMenu(
                        expanded = actionMenuExpanded,
                        onDismissRequest = { actionMenuExpanded = false },
                    ) {
                        EditorActionType.entries.forEach { type ->
                            DropdownMenuItem(
                                text = { Text(actionTypeLabel(type)) },
                                onClick = {
                                    actionMenuExpanded = false
                                    onDraftChange(draft.withActionType(type))
                                },
                            )
                        }
                    }
                }
                when (draft.actionType) {
                    EditorActionType.HOTKEY -> {
                        OutlinedTextField(
                            modifier = Modifier.fillMaxWidth(),
                            value = draft.modifiers,
                            onValueChange = { onDraftChange(draft.copy(modifiers = it)) },
                            label = { Text("Modificadores") },
                            supportingText = { Text("ctrl, alt, shift ou win, separados por vírgula") },
                            singleLine = true,
                            enabled = !saving,
                        )
                        ActionValueField(
                            value = draft.actionValue,
                            label = "Tecla",
                            enabled = !saving,
                            onValueChange = { onDraftChange(draft.copy(actionValue = it)) },
                        )
                    }
                    EditorActionType.KEY -> ActionValueField(
                        value = draft.actionValue,
                        label = "Tecla",
                        enabled = !saving,
                        onValueChange = { onDraftChange(draft.copy(actionValue = it)) },
                    )
                    EditorActionType.MEDIA -> {
                        val mediaLabel = mediaCommandLabel(draft.actionValue)
                        OutlinedButton(
                            modifier = Modifier.fillMaxWidth(),
                            onClick = {
                                val index = mediaCommands.indexOf(draft.actionValue).coerceAtLeast(0)
                                onDraftChange(draft.copy(actionValue = mediaCommands[(index + 1) % mediaCommands.size]))
                            },
                            enabled = !saving,
                        ) {
                            Icon(Icons.Outlined.MusicNote, contentDescription = null)
                            Spacer(modifier = Modifier.size(CommandSpacing.xs))
                            Text("Comando de mídia: $mediaLabel")
                        }
                    }
                    EditorActionType.TEXT -> ActionValueField(
                        value = draft.actionValue,
                        label = "Texto a digitar",
                        enabled = !saving,
                        singleLine = false,
                        onValueChange = { onDraftChange(draft.copy(actionValue = it)) },
                    )
                    EditorActionType.URL -> ActionValueField(
                        value = draft.actionValue,
                        label = "URL HTTPS",
                        enabled = !saving,
                        onValueChange = { onDraftChange(draft.copy(actionValue = it)) },
                    )
                    EditorActionType.APPLICATION -> ActionValueField(
                        value = draft.actionValue,
                        label = "ID da aplicação do catálogo",
                        enabled = !saving,
                        onValueChange = { onDraftChange(draft.copy(actionValue = it)) },
                    )
                }
            }

            EditorCard(title = "Posição avançada") {
                Row(horizontalArrangement = Arrangement.spacedBy(CommandSpacing.xs)) {
                    OutlinedTextField(
                        modifier = Modifier.weight(1f),
                        value = draft.row,
                        onValueChange = { onDraftChange(draft.copy(row = it)) },
                        label = { Text("Linha") },
                        singleLine = true,
                        enabled = !saving,
                    )
                    OutlinedTextField(
                        modifier = Modifier.weight(1f),
                        value = draft.column,
                        onValueChange = { onDraftChange(draft.copy(column = it)) },
                        label = { Text("Coluna") },
                        singleLine = true,
                        enabled = !saving,
                    )
                }
            }

            errorMessage?.let { message ->
                Text(
                    text = message,
                    color = MaterialTheme.colorScheme.error,
                    modifier = Modifier.semantics { liveRegion = LiveRegionMode.Polite },
                )
            }
            if (hasChangesToRevert) {
                OutlinedButton(
                    modifier = Modifier.fillMaxWidth(),
                    onClick = onRevert,
                    enabled = !saving,
                ) {
                    Text("Reverter alterações")
                }
            }
        }

        Surface(
            modifier = Modifier
                .align(Alignment.BottomCenter)
                .fillMaxWidth()
                .navigationBarsPadding(),
            color = MaterialTheme.colorScheme.surface,
            tonalElevation = 4.dp,
        ) {
            Row(
                modifier = Modifier.padding(CommandSpacing.sm),
                horizontalArrangement = Arrangement.spacedBy(CommandSpacing.xs),
            ) {
                OutlinedButton(
                    modifier = Modifier.weight(1f),
                    onClick = onCancel,
                    enabled = !saving,
                ) {
                    Text("Cancelar")
                }
                Button(
                    modifier = Modifier.weight(1f),
                    onClick = onSave,
                    enabled = !saving,
                ) {
                    if (saving) {
                        LinearProgressIndicator(modifier = Modifier.fillMaxWidth())
                    } else {
                        Text("Salvar alterações")
                    }
                }
            }
        }
    }
}

@Composable
private fun EditorCard(
    title: String,
    content: @Composable () -> Unit,
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = CommandShapes.card,
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
    ) {
        Column(
            modifier = Modifier.padding(CommandSpacing.md),
            verticalArrangement = Arrangement.spacedBy(CommandSpacing.sm),
        ) {
            Text(title, style = MaterialTheme.typography.titleMedium)
            content()
        }
    }
}

@Composable
private fun CommandButtonPreview(
    title: String,
    icon: String,
    color: Color,
    contentColor: Color,
    actionLabel: String,
) {
    Surface(
        modifier = Modifier
            .fillMaxWidth()
            .height(150.dp),
        shape = CommandShapes.card,
        color = MaterialTheme.colorScheme.surfaceVariant,
    ) {
        Box(contentAlignment = Alignment.Center) {
            Surface(
                modifier = Modifier.size(118.dp),
                shape = CommandShapes.key,
                color = color,
                contentColor = contentColor,
                tonalElevation = 3.dp,
            ) {
                Column(
                    modifier = Modifier.padding(CommandSpacing.sm),
                    horizontalAlignment = Alignment.CenterHorizontally,
                    verticalArrangement = Arrangement.Center,
                ) {
                    Icon(iconFor(icon), contentDescription = null, modifier = Modifier.size(28.dp))
                    Text(
                        title.ifBlank { "Comando" },
                        maxLines = 2,
                        overflow = TextOverflow.Ellipsis,
                        textAlign = TextAlign.Center,
                        style = MaterialTheme.typography.labelLarge,
                    )
                    Text(actionLabel, style = MaterialTheme.typography.labelSmall)
                }
            }
        }
    }
}

@Composable
private fun ButtonSelector(
    button: StreamDeckButton,
    selected: Boolean,
    enabled: Boolean,
    onClick: () -> Unit,
) {
    val selectedText = stringResource(R.string.a11y_button_selected)
    val description = if (selected) {
        "${button.title}. $selectedText"
    } else {
        stringResource(R.string.a11y_button_select, button.title)
    }
    Surface(
        modifier = Modifier
            .clip(CommandShapes.pill)
            .clickable(enabled = enabled, onClick = onClick)
            .semantics {
                contentDescription = description
                stateDescription = if (selected) selectedText else "Não selecionado"
            },
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
            text = button.title,
            modifier = Modifier.padding(horizontal = CommandSpacing.md, vertical = 10.dp),
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
            style = MaterialTheme.typography.labelMedium,
        )
    }
}

@Composable
private fun ActionValueField(
    value: String,
    label: String,
    enabled: Boolean,
    singleLine: Boolean = true,
    onValueChange: (String) -> Unit,
) {
    OutlinedTextField(
        modifier = Modifier.fillMaxWidth(),
        value = value,
        onValueChange = onValueChange,
        label = { Text(label) },
        singleLine = singleLine,
        enabled = enabled,
        minLines = if (singleLine) 1 else 3,
        maxLines = if (singleLine) 1 else 6,
    )
}

private fun actionTypeLabel(type: EditorActionType): String = when (type) {
    EditorActionType.HOTKEY -> "Atalho"
    EditorActionType.KEY -> "Tecla"
    EditorActionType.MEDIA -> "Mídia"
    EditorActionType.TEXT -> "Texto"
    EditorActionType.URL -> "URL HTTPS"
    EditorActionType.APPLICATION -> "Aplicativo"
}

private fun mediaCommandLabel(command: String): String = when (command) {
    "play_pause" -> "Reproduzir / pausar"
    "next" -> "Próxima faixa"
    "previous" -> "Faixa anterior"
    "stop" -> "Parar"
    "volume_up" -> "Aumentar volume"
    "volume_down" -> "Diminuir volume"
    "mute" -> "Silenciar"
    else -> command
}

private fun iconFor(icon: String?): ImageVector = when (icon) {
    "keyboard" -> Icons.Outlined.Keyboard
    "play_pause" -> Icons.Outlined.PlayArrow
    "book" -> Icons.AutoMirrored.Outlined.MenuBook
    "media" -> Icons.Outlined.MusicNote
    "application" -> Icons.Outlined.Apps
    else -> Icons.Outlined.Build
}
