package br.com.gustavo.streamdeck.ui

import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.TextButton
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.Close
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import br.com.gustavo.streamdeck.network.RemoteProfileSummary
import br.com.gustavo.streamdeck.network.ProfileSnapshotParser
import br.com.gustavo.streamdeck.network.StreamDeckProfileSnapshot
import br.com.gustavo.streamdeck.ui.theme.CommandColors
import br.com.gustavo.streamdeck.ui.theme.CommandShapes
import br.com.gustavo.streamdeck.ui.theme.CommandSpacing

/** Administration surface for profiles, pages, conflict recovery and transfer. */
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
    val context = LocalContext.current
    var exportTarget by remember { mutableStateOf<Uri?>(null) }
    var exportConfirmationVisible by remember { mutableStateOf(false) }
    var importConfirmationVisible by remember { mutableStateOf(false) }
    var previewVisible by remember { mutableStateOf(false) }
    var previewTitle by remember { mutableStateOf("") }
    var previewJson by remember { mutableStateOf("") }
    var fileError by remember { mutableStateOf<String?>(null) }
    var fileMessage by remember { mutableStateOf<String?>(null) }
    val exportLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.CreateDocument("application/json"),
    ) { uri ->
        exportTarget = uri
        exportConfirmationVisible = uri != null
        fileError = null
        fileMessage = null
    }
    val importLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.OpenDocument(),
    ) { uri ->
        if (uri != null) {
            fileError = null
            fileMessage = null
            val importedTextResult = runCatching {
                context.contentResolver.openInputStream(uri)?.bufferedReader()?.use { it.readText() }
                    ?: throw IllegalArgumentException("Não foi possível ler o arquivo selecionado")
            }
            val importedText = importedTextResult.getOrNull()
            if (importedText == null) {
                fileError = importedTextResult.exceptionOrNull()?.message
                    ?: "Não foi possível ler o arquivo selecionado"
            } else {
                onImportJsonChange(importedText)
                previewTitle = "Prévia do arquivo importado"
                previewJson = importedText
                previewVisible = true
            }
        }
    }
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
            .padding(horizontal = CommandSpacing.md, vertical = CommandSpacing.sm),
        verticalArrangement = Arrangement.spacedBy(CommandSpacing.sm),
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = androidx.compose.ui.Alignment.CenterVertically,
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text("Gerenciar workspace", style = MaterialTheme.typography.headlineSmall)
                Text(
                    "Perfis, páginas e transferência segura",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            IconButton(onClick = onClose, enabled = !loading) {
                Icon(Icons.Outlined.Close, contentDescription = "Voltar para o deck")
            }
        }

        if (loading) LinearProgressIndicator(modifier = Modifier.fillMaxWidth())
        successMessage?.let { message ->
            FeedbackBanner(message, isError = false)
        }
        errorMessage?.let { message ->
            FeedbackBanner(message, isError = true)
        }

        conflictCode?.let { code ->
            ManagementCard(title = "Conflito de revisão") {
                Text("Proteção: $code", color = MaterialTheme.colorScheme.error)
                conflictMessage?.let { Text(it) }
                Text(
                    "A alteração remota mudou. Escolha explicitamente como continuar.",
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Row(horizontalArrangement = Arrangement.spacedBy(CommandSpacing.xs)) {
                    Button(onClick = { onConflictResolution(ConflictResolution.RETRY) }) {
                        Text("Tentar novamente")
                    }
                    OutlinedButton(onClick = { onConflictResolution(ConflictResolution.RELOAD) }) {
                        Text("Recarregar")
                    }
                    OutlinedButton(onClick = { onConflictResolution(ConflictResolution.CANCEL) }) {
                        Text("Cancelar")
                    }
                }
            }
        }

        ManagementCard(title = "Perfis") {
            if (profiles.isEmpty() && !loading) {
                Text("Nenhum perfil disponível", color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            profiles.forEach { profile ->
                val selected = profile.profileId == selectedProfileId
                Surface(
                    modifier = Modifier.fillMaxWidth(),
                    shape = CommandShapes.card,
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
                    onClick = { onSelectProfile(profile.profileId) },
                    enabled = !loading,
                ) {
                    Column(modifier = Modifier.padding(CommandSpacing.sm)) {
                        Text(
                            text = if (profile.isActive) "●  ${profile.profileName}" else profile.profileName,
                            style = MaterialTheme.typography.titleSmall,
                        )
                        Text(
                            text = "${profile.profileId}  ·  revisão ${profile.revision}",
                            style = MaterialTheme.typography.labelMedium,
                        )
                    }
                }
            }
        }

        ManagementCard(title = "Criar ou duplicar") {
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
            HorizontalDivider()
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
            OutlinedButton(
                modifier = Modifier.fillMaxWidth(),
                onClick = { onDuplicateProfile(duplicateProfileId, duplicateProfileName) },
                enabled = !loading && snapshot != null,
            ) { Text("Duplicar perfil") }
        }

        ManagementCard(title = "Perfil selecionado") {
            OutlinedTextField(
                modifier = Modifier.fillMaxWidth(),
                value = renameProfileName,
                onValueChange = { renameProfileName = it },
                label = { Text("Nome do perfil") },
                singleLine = true,
                enabled = !loading && snapshot != null,
            )
            Button(
                modifier = Modifier.fillMaxWidth(),
                onClick = { onRenameProfile(renameProfileName) },
                enabled = !loading && snapshot != null,
            ) { Text("Renomear perfil") }
            Button(
                modifier = Modifier.fillMaxWidth(),
                onClick = onActivateProfile,
                enabled = !loading && snapshot != null,
            ) { Text("Ativar este perfil") }
            HorizontalDivider()
            Text(
                "Excluir é uma operação permanente. O perfil ativo exige um substituto.",
                color = MaterialTheme.colorScheme.error,
                style = MaterialTheme.typography.bodySmall,
            )
            OutlinedTextField(
                modifier = Modifier.fillMaxWidth(),
                value = replacementProfileId,
                onValueChange = { replacementProfileId = it },
                label = { Text("ID substituto ao excluir") },
                singleLine = true,
                enabled = !loading && snapshot != null,
            )
            OutlinedButton(
                modifier = Modifier.fillMaxWidth(),
                onClick = { onDeleteProfile(replacementProfileId.trim().ifEmpty { null }) },
                enabled = !loading && snapshot != null,
            ) { Text("Excluir perfil selecionado") }
        }

        ManagementCard(title = "Transferência") {
            Text(
                "O JSON permanece em memória até você confirmar uma prévia e escolher um destino.",
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                style = MaterialTheme.typography.bodySmall,
            )
            fileError?.let { error ->
                FeedbackBanner(error, isError = true)
            }
            fileMessage?.let { message ->
                FeedbackBanner(message, isError = false)
            }
            Row(horizontalArrangement = Arrangement.spacedBy(CommandSpacing.xs)) {
                Button(onClick = onExport, enabled = !loading && snapshot != null) {
                    Text("Exportar JSON")
                }
                OutlinedButton(
                    onClick = {
                        previewTitle = "Prévia completa da exportação"
                        previewJson = exportJson
                        previewVisible = true
                    },
                    enabled = !loading && exportJson.isNotBlank(),
                ) {
                    Text("Ver prévia")
                }
            }
            OutlinedButton(
                onClick = { exportLauncher.launch("streamdeck-profile.json") },
                enabled = !loading && exportJson.isNotBlank(),
            ) {
                Text("Escolher arquivo para salvar")
            }
            OutlinedButton(
                modifier = Modifier.fillMaxWidth(),
                onClick = { importLauncher.launch(arrayOf("application/json", "text/plain")) },
                enabled = !loading && snapshot != null,
            ) {
                Text("Selecionar arquivo JSON")
            }
            OutlinedTextField(
                modifier = Modifier.fillMaxWidth(),
                value = exportJson,
                onValueChange = {},
                label = { Text("JSON exportado em memória") },
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
            Row(horizontalArrangement = Arrangement.spacedBy(CommandSpacing.xs)) {
                OutlinedButton(
                    onClick = {
                        previewTitle = "Prévia completa da importação"
                        previewJson = importJson
                        previewVisible = true
                    },
                    enabled = !loading && importJson.isNotBlank(),
                ) { Text("Ver importação") }
                Button(
                    onClick = { importConfirmationVisible = true },
                    enabled = !loading && snapshot != null && importJson.isNotBlank(),
                ) {
                    Text("Confirmar importação")
                }
            }
        }

        snapshot?.let { current ->
            ManagementCard(title = "Páginas de ${current.profileName}") {
                current.pages.sortedBy { it.order }.forEach { page ->
                    Surface(
                        modifier = Modifier.fillMaxWidth(),
                        shape = CommandShapes.card,
                        color = if (page.id == current.activePage.id) {
                            MaterialTheme.colorScheme.primaryContainer
                        } else {
                            MaterialTheme.colorScheme.surfaceVariant
                        },
                    ) {
                        Column(modifier = Modifier.padding(CommandSpacing.sm)) {
                            Text(
                                if (page.id == current.activePage.id) "●  ${page.title}" else page.title,
                                style = MaterialTheme.typography.titleSmall,
                            )
                            Text(
                                "ordem ${page.order}  ·  ${page.rows} × ${page.columns}  ·  ${page.id}",
                                style = MaterialTheme.typography.labelMedium,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                    }
                }
                HorizontalDivider()
                Text("Nova página", style = MaterialTheme.typography.titleSmall)
                OutlinedTextField(
                    modifier = Modifier.fillMaxWidth(),
                    value = newPageId,
                    onValueChange = { newPageId = it },
                    label = { Text("ID") },
                    singleLine = true,
                    enabled = !loading,
                )
                OutlinedTextField(
                    modifier = Modifier.fillMaxWidth(),
                    value = newPageTitle,
                    onValueChange = { newPageTitle = it },
                    label = { Text("Título") },
                    singleLine = true,
                    enabled = !loading,
                )
                NumberField("Ordem", newPageOrder, { newPageOrder = it }, !loading)
                Button(
                    modifier = Modifier.fillMaxWidth(),
                    onClick = { onCreatePage(newPageId, newPageTitle, newPageOrder.toIntOrNull() ?: -1) },
                    enabled = !loading,
                ) { Text("Criar página") }

                HorizontalDivider()
                Text("Renomear ou reordenar", style = MaterialTheme.typography.titleSmall)
                OutlinedTextField(
                    modifier = Modifier.fillMaxWidth(),
                    value = renamePageId,
                    onValueChange = { renamePageId = it },
                    label = { Text("ID da página") },
                    singleLine = true,
                    enabled = !loading,
                )
                OutlinedTextField(
                    modifier = Modifier.fillMaxWidth(),
                    value = renamePageTitle,
                    onValueChange = { renamePageTitle = it },
                    label = { Text("Novo título") },
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
                    label = { Text("ID para reordenar") },
                    singleLine = true,
                    enabled = !loading,
                )
                NumberField("Nova ordem", reorderPageOrder, { reorderPageOrder = it }, !loading)
                OutlinedButton(
                    modifier = Modifier.fillMaxWidth(),
                    onClick = { onReorderPage(reorderPageId, reorderPageOrder.toIntOrNull() ?: -1) },
                    enabled = !loading,
                ) { Text("Reordenar página") }

                HorizontalDivider()
                Text("Excluir página", style = MaterialTheme.typography.titleSmall)
                OutlinedTextField(
                    modifier = Modifier.fillMaxWidth(),
                    value = deletePageId,
                    onValueChange = { deletePageId = it },
                    label = { Text("ID da página") },
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
                    onClick = { onDeletePage(deletePageId, replacementPageId.trim().ifEmpty { null }) },
                    enabled = !loading,
                ) { Text("Excluir página") }
            }
        }
    }

    if (previewVisible) {
        val parsedPreview = runCatching {
            ProfileSnapshotParser.parseWireProfile(previewJson)
        }.getOrNull()
        AlertDialog(
            onDismissRequest = { previewVisible = false },
            title = { Text(previewTitle) },
            text = {
                Column(
                    modifier = Modifier
                        .heightIn(max = 480.dp)
                        .verticalScroll(rememberScrollState()),
                    verticalArrangement = Arrangement.spacedBy(CommandSpacing.xs),
                ) {
                    if (parsedPreview != null) {
                        Text(
                            "Perfil: ${parsedPreview.profileName} (${parsedPreview.profileId})",
                            style = MaterialTheme.typography.titleSmall,
                        )
                        Text(
                            "Revisão ${parsedPreview.revision}  ·  página ativa: ${parsedPreview.activePage.title}",
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                        parsedPreview.pages.sortedBy { it.order }.forEach { page ->
                            Text(
                                "${page.order}. ${page.title} — ${page.buttons.size} teclas",
                                style = MaterialTheme.typography.bodySmall,
                            )
                        }
                        HorizontalDivider()
                    } else {
                        Text(
                            "JSON inválido ou incompatível com o contrato atual.",
                            color = MaterialTheme.colorScheme.error,
                        )
                    }
                    SelectionContainer {
                        Text(previewJson, style = MaterialTheme.typography.bodySmall)
                    }
                }
            },
            confirmButton = {
                TextButton(onClick = { previewVisible = false }) { Text("Fechar") }
            },
        )
    }

    if (exportConfirmationVisible) {
        AlertDialog(
            onDismissRequest = {
                exportConfirmationVisible = false
                exportTarget = null
            },
            title = { Text("Confirmar gravação") },
            text = {
                Text(
                    "O conteúdo exportado será gravado no arquivo escolhido. " +
                        "Se ele já existir, o provedor de arquivos poderá substituí-lo.",
                )
            },
            dismissButton = {
                TextButton(onClick = {
                    exportConfirmationVisible = false
                    exportTarget = null
                }) { Text("Cancelar") }
            },
            confirmButton = {
                TextButton(onClick = {
                    val target = exportTarget
                    val result = runCatching {
                        require(target != null) { "Nenhum destino de arquivo foi selecionado" }
                        require(exportJson.isNotBlank()) { "Não há JSON exportado para salvar" }
                        context.contentResolver.openOutputStream(target)?.bufferedWriter()?.use {
                            it.write(exportJson)
                        } ?: error("O provedor não permitiu gravar o arquivo")
                    }
                    result.onSuccess {
                        fileMessage = "Arquivo exportado com confirmação"
                        fileError = null
                    }.onFailure { error ->
                        fileError = error.message ?: "Não foi possível gravar o arquivo"
                        fileMessage = null
                    }
                    exportConfirmationVisible = false
                    exportTarget = null
                }) { Text("Gravar arquivo") }
            },
        )
    }

    if (importConfirmationVisible) {
        val importedProfile = runCatching {
            ProfileSnapshotParser.parseWireProfile(importJson)
        }.getOrNull()
        AlertDialog(
            onDismissRequest = { importConfirmationVisible = false },
            title = { Text("Confirmar sobrescrita do perfil") },
            text = {
                Text(
                    if (importedProfile == null) {
                        "O JSON não pode ser aplicado porque não corresponde ao contrato do servidor."
                    } else {
                        "A importação substituirá o conteúdo do perfil " +
                            "${importedProfile.profileName} na revisão atual. " +
                            "Essa alteração será enviada ao servidor e poderá gerar uma nova revisão."
                    },
                )
            },
            dismissButton = {
                TextButton(onClick = { importConfirmationVisible = false }) {
                    Text("Cancelar")
                }
            },
            confirmButton = {
                TextButton(
                    enabled = importedProfile != null,
                    onClick = {
                        importConfirmationVisible = false
                        previewVisible = false
                        onImport()
                    },
                ) { Text("Sobrescrever e importar") }
            },
        )
    }
}

@Composable
private fun ManagementCard(
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
private fun FeedbackBanner(message: String, isError: Boolean) {
    Surface(
        modifier = Modifier
            .fillMaxWidth()
            .semantics { liveRegion = LiveRegionMode.Polite },
        shape = CommandShapes.card,
        color = if (isError) {
            CommandColors.Danger.copy(alpha = 0.14f)
        } else {
            CommandColors.Success.copy(alpha = 0.14f)
        },
        contentColor = if (isError) CommandColors.Danger else CommandColors.Success,
    ) {
        Text(message, modifier = Modifier.padding(CommandSpacing.sm))
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
