package br.com.gustavo.streamdeck.ui

import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import br.com.gustavo.streamdeck.network.StreamDeckProfileSnapshot

@Composable
fun ProfileEditorScreen(
    snapshot: StreamDeckProfileSnapshot,
    draft: ProfileEditorDraft,
    saving: Boolean,
    errorMessage: String?,
    onDraftChange: (ProfileEditorDraft) -> Unit,
    onSave: () -> Unit,
    onCancel: () -> Unit,
) {
    val mediaCommands = listOf(
        "play_pause",
        "next",
        "previous",
        "stop",
        "volume_up",
        "volume_down",
        "mute",
    )
    val actionTypes = EditorActionType.entries
    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        Text("Editor do perfil", style = MaterialTheme.typography.headlineSmall)
        Text("Revisão atual: ${snapshot.revision}")
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
        Text("Botão selecionado", style = MaterialTheme.typography.titleMedium)
        Row(
            modifier = Modifier.horizontalScroll(rememberScrollState()),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            snapshot.activePage.buttons.forEach { button ->
                val selected = button.id == draft.selectedButtonId
                if (selected) {
                    Button(
                        onClick = {},
                        enabled = !saving,
                    ) {
                        Text(button.title)
                    }
                } else {
                    OutlinedButton(
                        onClick = {
                            onDraftChange(draft.selectButton(snapshot, button.id))
                        },
                        enabled = !saving,
                    ) {
                        Text(button.title)
                    }
                }
            }
        }
        OutlinedTextField(
            modifier = Modifier.fillMaxWidth(),
            value = draft.title,
            onValueChange = { onDraftChange(draft.copy(title = it)) },
            label = { Text("Título do botão") },
            singleLine = true,
            enabled = !saving,
        )
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
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
        OutlinedTextField(
            modifier = Modifier.fillMaxWidth(),
            value = draft.icon,
            onValueChange = { onDraftChange(draft.copy(icon = it)) },
            label = { Text("Ícone (opcional)") },
            singleLine = true,
            enabled = !saving,
        )
        OutlinedTextField(
            modifier = Modifier.fillMaxWidth(),
            value = draft.color,
            onValueChange = { onDraftChange(draft.copy(color = it)) },
            label = { Text("Cor HEX (opcional)") },
            supportingText = { Text("Ex.: #4CAF50 ou #4CAF5080") },
            singleLine = true,
            enabled = !saving,
        )
        Button(
            modifier = Modifier.fillMaxWidth(),
            onClick = {
                val current = actionTypes.indexOf(draft.actionType)
                val next = actionTypes[(current + 1) % actionTypes.size]
                onDraftChange(draft.withActionType(next))
            },
            enabled = !saving,
        ) {
            Text("Tipo de ação: ${actionTypeLabel(draft.actionType)}")
        }
        when (draft.actionType) {
            EditorActionType.HOTKEY -> {
                OutlinedTextField(
                    modifier = Modifier.fillMaxWidth(),
                    value = draft.modifiers,
                    onValueChange = { onDraftChange(draft.copy(modifiers = it)) },
                    label = { Text("Modificadores (separados por vírgula)") },
                    supportingText = { Text("ctrl, alt, shift ou win") },
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
                val current = mediaCommands.indexOf(draft.actionValue).coerceAtLeast(0)
                Button(
                    modifier = Modifier.fillMaxWidth(),
                    onClick = {
                        val next = mediaCommands[(current + 1) % mediaCommands.size]
                        onDraftChange(draft.copy(actionValue = next))
                    },
                    enabled = !saving,
                ) {
                    Text("Comando de mídia: ${draft.actionValue}")
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
                label = "ID da aplicação",
                enabled = !saving,
                onValueChange = { onDraftChange(draft.copy(actionValue = it)) },
            )
        }
        errorMessage?.let { message ->
            Text(message, color = MaterialTheme.colorScheme.error)
        }
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
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
                Text(if (saving) "Salvando…" else "Salvar perfil")
            }
        }
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
    EditorActionType.HOTKEY -> "hotkey"
    EditorActionType.KEY -> "key"
    EditorActionType.MEDIA -> "media"
    EditorActionType.TEXT -> "text"
    EditorActionType.URL -> "url"
    EditorActionType.APPLICATION -> "application"
}
