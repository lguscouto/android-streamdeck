package br.com.gustavo.streamdeck.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import br.com.gustavo.streamdeck.network.RemoteProfileSummary
import br.com.gustavo.streamdeck.network.StreamDeckProfileSnapshot

/**
 * The management surface is deliberately callback-only: network and optimistic
 * concurrency state remain in App.kt, while this screen exposes only closed,
 * typed profile/page operations and JSON import/export text in memory.
 */
@Composable
fun ProfileManagementScreen(
    profiles: List<RemoteProfileSummary>,
    selectedProfileId: String?,
    snapshot: StreamDeckProfileSnapshot?,
    loading: Boolean,
    successMessage: String?,
    errorMessage: String?,
    conflictCode: String?,
    conflictMessage: String?,
    exportJson: String,
    importJson: String,
    onImportJsonChange: (String) -> Unit,
    onSelectProfile: (String) -> Unit,
    onCreateProfile: (String, String) -> Unit,
    onRenameProfile: (String) -> Unit,
    onDuplicateProfile: (String, String) -> Unit,
    onActivateProfile: () -> Unit,
    onDeleteProfile: (String?) -> Unit,
    onCreatePage: (String, String, Int) -> Unit,
    onRenamePage: (String, String) -> Unit,
    onReorderPage: (String, Int) -> Unit,
    onDeletePage: (String, String?) -> Unit,
    onExport: () -> Unit,
    onImport: () -> Unit,
    onConflictResolution: (ConflictResolution) -> Unit,
    onClose: () -> Unit,
) {
    var newProfileId by remember { mutableStateOf("") }
    var newProfileName by remember { mutableStateOf("") }
    var renameProfileName by remember(selectedProfileId) { mutableStateOf("") }
    var duplicateProfileId by remember { mutableStateOf("") }
    var duplicateProfileName by remember { mutableStateOf("") }
    var replacementProfileId by remember { mutableStateOf("") }
    var newPageId by remember { mutableStateOf("") }
    var newPageTitle by remember { mutableStateOf("") }
    var newPageOrder by remember { mutableStateOf("0") }
    var renamePageId by remember { mutableStateOf("") }
    var renamePageTitle by remember { mutableStateOf("") }
    var reorderPageId by remember { mutableStateOf("") }
    var reorderPageOrder by remember { mutableStateOf("0") }
    var deletePageId by remember { mutableStateOf("") }
    var replacementPageId by remember { mutableStateOf("") }

    LaunchedEffect(selectedProfileId, snapshot?.profileName) {
        renameProfileName = snapshot?.profileName.orEmpty()
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        Text("Gerenciar perfis", style = MaterialTheme.typography.headlineSmall)
        OutlinedButton(modifier = Modifier.fillMaxWidth(), onClick = onClose, enabled = !loading) {
            Text("Voltar para o deck")
        }
        if (loading) {
            Text("Carregando…")
        }
        successMessage?.let { Text(it, color = MaterialTheme.colorScheme.primary) }
        errorMessage?.let { Text(it, color = MaterialTheme.colorScheme.error) }

        if (conflictCode != null) {
            HorizontalDivider()
            Text("Conflito/proteção: $conflictCode", color = MaterialTheme.colorScheme.error)
            conflictMessage?.let { Text(it) }
            Text("Escolha explicitamente como continuar:")
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(onClick = { onConflictResolution(ConflictResolution.RETRY) }) {
                    Text("RETRY")
                }
                OutlinedButton(onClick = { onConflictResolution(ConflictResolution.RELOAD) }) {
                    Text("RELOAD")
                }
                OutlinedButton(onClick = { onConflictResolution(ConflictResolution.CANCEL) }) {
                    Text("CANCEL")
                }
            }
        }

        HorizontalDivider()
        Text("Perfis", style = MaterialTheme.typography.titleMedium)
        if (profiles.isEmpty() && !loading) {
            Text("Nenhum perfil disponível")
        }
        profiles.forEach { profile ->
            val selected = profile.profileId == selectedProfileId
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                OutlinedButton(
                    modifier = Modifier.weight(1f),
                    onClick = { onSelectProfile(profile.profileId) },
                    enabled = !loading,
                ) {
                    Text(
                        buildString {
                            append(if (selected) "• " else "")
                            append(profile.profileName)
                            append(" [${profile.profileId}] r${profile.revision}")
                            if (profile.isActive) append(" · ativo")
                        },
                    )
                }
            }
        }

        OutlinedTextField(
            modifier = Modifier.fillMaxWidth(),
            value = newProfileId,
            onValueChange = { newProfileId = it },
            label = { Text("ID do novo perfil") },
            singleLine = true,
            enabled = !loading,
        )
        OutlinedTextField(
            modifier = Modifier.fillMaxWidth(),
            value = newProfileName,
            onValueChange = { newProfileName = it },
            label = { Text("Nome do novo perfil") },
            singleLine = true,
            enabled = !loading,
        )
        Button(
            modifier = Modifier.fillMaxWidth(),
            onClick = { onCreateProfile(newProfileId, newProfileName) },
            enabled = !loading && snapshot != null,
        ) { Text("Criar perfil") }

        OutlinedTextField(
            modifier = Modifier.fillMaxWidth(),
            value = renameProfileName,
            onValueChange = { renameProfileName = it },
            label = { Text("Novo nome do perfil selecionado") },
            singleLine = true,
            enabled = !loading && snapshot != null,
        )
        Button(
            modifier = Modifier.fillMaxWidth(),
            onClick = { onRenameProfile(renameProfileName) },
            enabled = !loading && snapshot != null,
        ) { Text("Renomear perfil") }

        OutlinedTextField(
            modifier = Modifier.fillMaxWidth(),
            value = duplicateProfileId,
            onValueChange = { duplicateProfileId = it },
            label = { Text("ID da cópia") },
            singleLine = true,
            enabled = !loading && snapshot != null,
        )
        OutlinedTextField(
            modifier = Modifier.fillMaxWidth(),
            value = duplicateProfileName,
            onValueChange = { duplicateProfileName = it },
            label = { Text("Nome da cópia") },
            singleLine = true,
            enabled = !loading && snapshot != null,
        )
        Button(
            modifier = Modifier.fillMaxWidth(),
            onClick = { onDuplicateProfile(duplicateProfileId, duplicateProfileName) },
            enabled = !loading && snapshot != null,
        ) { Text("Duplicar perfil") }
        Button(
            modifier = Modifier.fillMaxWidth(),
            onClick = onActivateProfile,
            enabled = !loading && snapshot != null,
        ) { Text("Ativar perfil selecionado") }
        OutlinedTextField(
            modifier = Modifier.fillMaxWidth(),
            value = replacementProfileId,
            onValueChange = { replacementProfileId = it },
            label = { Text("ID substituto ao excluir perfil ativo") },
            singleLine = true,
            enabled = !loading && snapshot != null,
        )
        OutlinedButton(
            modifier = Modifier.fillMaxWidth(),
            onClick = { onDeleteProfile(replacementProfileId.trim().ifEmpty { null }) },
            enabled = !loading && snapshot != null,
        ) { Text("Excluir perfil selecionado") }

        HorizontalDivider()
        Text("Importar/exportar JSON", style = MaterialTheme.typography.titleMedium)
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Button(onClick = onExport, enabled = !loading && snapshot != null) {
                Text("Exportar JSON")
            }
            OutlinedButton(onClick = onImport, enabled = !loading && snapshot != null) {
                Text("Importar JSON")
            }
        }
        OutlinedTextField(
            modifier = Modifier.fillMaxWidth(),
            value = exportJson,
            onValueChange = {},
            label = { Text("JSON exportado (memória)") },
            minLines = 3,
            maxLines = 8,
            readOnly = true,
            enabled = !loading,
        )
        OutlinedTextField(
            modifier = Modifier.fillMaxWidth(),
            value = importJson,
            onValueChange = onImportJsonChange,
            label = { Text("JSON para importar") },
            minLines = 3,
            maxLines = 8,
            enabled = !loading,
        )

        snapshot?.let { current ->
            HorizontalDivider()
            Text("Páginas de ${current.profileName}", style = MaterialTheme.typography.titleMedium)
            current.pages.sortedBy { it.order }.forEach { page ->
                Text("${page.order}: ${page.title} [${page.id}]" +
                    if (page.id == current.activePage.id) " · ativa" else "")
            }
            OutlinedTextField(
                modifier = Modifier.fillMaxWidth(),
                value = newPageId,
                onValueChange = { newPageId = it },
                label = { Text("ID da nova página") },
                singleLine = true,
                enabled = !loading,
            )
            OutlinedTextField(
                modifier = Modifier.fillMaxWidth(),
                value = newPageTitle,
                onValueChange = { newPageTitle = it },
                label = { Text("Título da nova página") },
                singleLine = true,
                enabled = !loading,
            )
            NumberField("Ordem da nova página", newPageOrder, { newPageOrder = it }, !loading)
            Button(
                modifier = Modifier.fillMaxWidth(),
                onClick = {
                    onCreatePage(newPageId, newPageTitle, newPageOrder.toIntOrNull() ?: -1)
                },
                enabled = !loading,
            ) { Text("Criar página") }

            OutlinedTextField(
                modifier = Modifier.fillMaxWidth(),
                value = renamePageId,
                onValueChange = { renamePageId = it },
                label = { Text("ID da página para renomear") },
                singleLine = true,
                enabled = !loading,
            )
            OutlinedTextField(
                modifier = Modifier.fillMaxWidth(),
                value = renamePageTitle,
                onValueChange = { renamePageTitle = it },
                label = { Text("Novo título da página") },
                singleLine = true,
                enabled = !loading,
            )
            Button(
                modifier = Modifier.fillMaxWidth(),
                onClick = { onRenamePage(renamePageId, renamePageTitle) },
                enabled = !loading,
            ) { Text("Renomear página") }

            OutlinedTextField(
                modifier = Modifier.fillMaxWidth(),
                value = reorderPageId,
                onValueChange = { reorderPageId = it },
                label = { Text("ID da página para reordenar") },
                singleLine = true,
                enabled = !loading,
            )
            NumberField("Nova ordem", reorderPageOrder, { reorderPageOrder = it }, !loading)
            Button(
                modifier = Modifier.fillMaxWidth(),
                onClick = {
                    onReorderPage(reorderPageId, reorderPageOrder.toIntOrNull() ?: -1)
                },
                enabled = !loading,
            ) { Text("Reordenar página") }

            OutlinedTextField(
                modifier = Modifier.fillMaxWidth(),
                value = deletePageId,
                onValueChange = { deletePageId = it },
                label = { Text("ID da página para excluir") },
                singleLine = true,
                enabled = !loading,
            )
            OutlinedTextField(
                modifier = Modifier.fillMaxWidth(),
                value = replacementPageId,
                onValueChange = { replacementPageId = it },
                label = { Text("ID substituto da página ativa") },
                singleLine = true,
                enabled = !loading,
            )
            OutlinedButton(
                modifier = Modifier.fillMaxWidth(),
                onClick = {
                    onDeletePage(deletePageId, replacementPageId.trim().ifEmpty { null })
                },
                enabled = !loading,
            ) { Text("Excluir página") }
        }
    }
}

@Composable
private fun NumberField(
    label: String,
    value: String,
    onValueChange: (String) -> Unit,
    enabled: Boolean,
) {
    OutlinedTextField(
        modifier = Modifier.fillMaxWidth(),
        value = value,
        onValueChange = { updated ->
            if (updated.all { it.isDigit() }) onValueChange(updated)
        },
        label = { Text(label) },
        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
        singleLine = true,
        enabled = enabled,
    )
}
