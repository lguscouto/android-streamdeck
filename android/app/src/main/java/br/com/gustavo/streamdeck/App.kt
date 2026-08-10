package br.com.gustavo.streamdeck

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawing
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import br.com.gustavo.streamdeck.network.ActionAcknowledgementStatus
import br.com.gustavo.streamdeck.network.EncryptedPairingStore
import br.com.gustavo.streamdeck.network.PairingClient
import br.com.gustavo.streamdeck.network.PairingCredentials
import br.com.gustavo.streamdeck.network.PairingException
import br.com.gustavo.streamdeck.network.RemoteProfileSummary
import br.com.gustavo.streamdeck.network.ProfileSnapshotParser
import br.com.gustavo.streamdeck.network.ProfileSnapshotSerializer
import br.com.gustavo.streamdeck.network.ProtocolMessages
import br.com.gustavo.streamdeck.network.ServerEndpoint
import br.com.gustavo.streamdeck.network.StreamDeckButton
import br.com.gustavo.streamdeck.network.StreamDeckProfileSnapshot
import br.com.gustavo.streamdeck.network.StreamDeckSocketListener
import br.com.gustavo.streamdeck.network.StreamDeckWebSocketClient
import br.com.gustavo.streamdeck.network.TlsTrust
import br.com.gustavo.streamdeck.ui.ButtonExecutionState
import br.com.gustavo.streamdeck.ui.ProfileEditorDraft
import br.com.gustavo.streamdeck.ui.ProfileEditorScreen
import br.com.gustavo.streamdeck.ui.ProfileManagementScreen
import br.com.gustavo.streamdeck.ui.StreamDeckGrid
import java.util.UUID
import kotlinx.coroutines.launch
import okhttp3.WebSocket
import org.json.JSONObject

private enum class ConnectionStatus {
    DISCONNECTED,
    CONNECTING,
    CONNECTED,
    ERROR,
}

private fun safeManagementMessage(error: Throwable): String = when (error) {
    is PairingException -> error.message ?: "Operação recusada pelo servidor"
    is IllegalArgumentException -> error.message ?: "Dados inválidos"
    else -> "Não foi possível concluir a operação"
}

@Composable
fun StreamDeckApp() {
    MaterialTheme {
        Surface(
            modifier = Modifier
                .fillMaxSize()
                .windowInsetsPadding(WindowInsets.safeDrawing),
            color = MaterialTheme.colorScheme.background,
        ) {
            PairingScreen()
        }
    }
}

@Composable
private fun PairingScreen() {
    val context = LocalContext.current
    val pairingStore = remember(context) { EncryptedPairingStore(context) }
    val storedCredentials = remember(pairingStore) { pairingStore.load() }
    val scope = rememberCoroutineScope()
    val pairingClient = remember { PairingClient() }
    val websocketClient = remember { StreamDeckWebSocketClient() }
    val invalidProfileSnapshot = stringResource(R.string.invalid_profile_snapshot)
    val actionNotConnected = stringResource(R.string.action_not_connected)
    val actionSendFailed = stringResource(R.string.action_send_failed)
    var serverAddress by remember {
        mutableStateOf(storedCredentials?.serverBaseUrl.orEmpty())
    }
    var pairingCode by remember { mutableStateOf("") }
    var caCertificatePem by remember {
        mutableStateOf(storedCredentials?.tlsTrust?.caCertificatePem.orEmpty())
    }
    var trustCode by remember {
        mutableStateOf(storedCredentials?.tlsTrust?.trustCode.orEmpty())
    }
    var tlsTrust by remember { mutableStateOf(storedCredentials?.tlsTrust) }
    var clientId by remember {
        mutableStateOf(storedCredentials?.clientId ?: "android-emulator")
    }
    var accessToken by remember {
        mutableStateOf(storedCredentials?.accessToken)
    }
    var pairedClientId by remember { mutableStateOf(storedCredentials?.clientId) }
    var pairedServerBaseUrl by remember { mutableStateOf(storedCredentials?.serverBaseUrl) }
    var status by remember { mutableStateOf(ConnectionStatus.DISCONNECTED) }
    var statusMessage by remember { mutableStateOf<String?>(null) }
    var profileSnapshot by remember { mutableStateOf<StreamDeckProfileSnapshot?>(null) }
    var buttonStates by remember { mutableStateOf<Map<String, ButtonExecutionState>>(emptyMap()) }
    var pendingPresses by remember { mutableStateOf<Map<String, String>>(emptyMap()) }
    var editingProfile by remember { mutableStateOf(false) }
    var editorDraft by remember { mutableStateOf<ProfileEditorDraft?>(null) }
    var editorOriginalDraft by remember { mutableStateOf<ProfileEditorDraft?>(null) }
    var savingProfile by remember { mutableStateOf(false) }
    var editorError by remember { mutableStateOf<String?>(null) }
    var managingProfiles by remember { mutableStateOf(false) }
    var managedProfiles by remember { mutableStateOf<List<RemoteProfileSummary>>(emptyList()) }
    var managedSelectedId by remember { mutableStateOf<String?>(null) }
    var managedSnapshot by remember { mutableStateOf<StreamDeckProfileSnapshot?>(null) }
    var managementLoading by remember { mutableStateOf(false) }
    var managementSuccess by remember { mutableStateOf<String?>(null) }
    var managementError by remember { mutableStateOf<String?>(null) }
    var managementConflictCode by remember { mutableStateOf<String?>(null) }
    var managementConflictMessage by remember { mutableStateOf<String?>(null) }
    var managementExportJson by remember { mutableStateOf("") }
    var managementImportJson by remember { mutableStateOf("") }
    var managementRetry by remember { mutableStateOf<(() -> Unit)?>(null) }
    var socket by remember { mutableStateOf<WebSocket?>(null) }

    val socketForEffect = socket
    DisposableEffect(socketForEffect) {
        onDispose {
            socketForEffect?.close(1000, "screen closed")
        }
    }

    fun rejectPendingActions(message: String) {
        val pendingButtons = pendingPresses.values
        if (pendingButtons.isNotEmpty()) {
            buttonStates = buttonStates + pendingButtons.associateWith {
                ButtonExecutionState.REJECTED
            }
            pendingPresses = emptyMap()
        }
        statusMessage = message
    }

    fun connect() {
        scope.launch {
            status = ConnectionStatus.CONNECTING
            statusMessage = null
            profileSnapshot = null
            editingProfile = false
            editorDraft = null
            savingProfile = false
            editorError = null
            buttonStates = emptyMap()
            pendingPresses = emptyMap()
            try {
                val endpoint = ServerEndpoint.parse(serverAddress)
                var token = accessToken
                if (!token.isNullOrBlank() && pairedServerBaseUrl != endpoint.httpBaseUrl) {
                    accessToken = null
                    pairedClientId = null
                    pairedServerBaseUrl = null
                    tlsTrust = null
                    pairingStore.clear()
                    token = null
                }
                val activeTrust = tlsTrust ?: run {
                    if (caCertificatePem.isBlank() || trustCode.isBlank()) {
                        throw PairingException(
                            "TLS_TRUST_REQUIRED",
                            "Informe a CA PEM e o código de confiança exibido no Windows",
                        )
                    }
                    TlsTrust.fromPem(caCertificatePem, trustCode).also { tlsTrust = it }
                }
                pairingClient.configureTlsTrust(activeTrust)
                websocketClient.configureTlsTrust(activeTrust)
                if (token.isNullOrBlank()) {
                    if (pairingCode.isBlank()) {
                        throw PairingException(
                            "PAIRING_CODE_REQUIRED",
                            "Informe o código de pareamento",
                        )
                    }
                    val result = pairingClient.claim(
                        endpoint = endpoint,
                        clientId = clientId.trim(),
                        clientVersion = AppMetadata.VERSION_NAME,
                        pairingCode = pairingCode.trim(),
                    )
                    token = result.accessToken
                    accessToken = token
                    val credentials = PairingCredentials.fromStored(
                        serverBaseUrl = endpoint.httpBaseUrl,
                        clientId = result.clientId,
                        accessToken = token,
                        caCertificatePem = activeTrust.caCertificatePem,
                        trustCode = activeTrust.trustCode,
                    )
                        ?: throw PairingException("INVALID_RESPONSE", "Credencial inválida")
                    pairingStore.save(credentials)
                    pairedClientId = credentials.clientId
                    pairedServerBaseUrl = credentials.serverBaseUrl
                }
                socket?.cancel()
                val authenticatedToken = token
                    ?: throw PairingException("TOKEN_MISSING", "Token de pareamento ausente")
                socket = websocketClient.connect(
                    endpoint = endpoint,
                    clientId = clientId.trim(),
                    clientVersion = AppMetadata.VERSION_NAME,
                    accessToken = authenticatedToken,
                    listener = object : StreamDeckSocketListener {
                        override fun onMessage(type: String, rawMessage: String) {
                            when (type) {
                                "welcome" -> {
                                    status = ConnectionStatus.CONNECTED
                                    statusMessage = "Servidor autenticado"
                                }
                                "profile_snapshot" -> {
                                    runCatching { ProfileSnapshotParser.parse(rawMessage) }
                                        .onSuccess { snapshot ->
                                            if (!savingProfile) {
                                                profileSnapshot = snapshot
                                                if (!editingProfile) {
                                                    editorDraft = ProfileEditorDraft.from(snapshot)
                                                }
                                            }
                                        }
                                        .onFailure {
                                            status = ConnectionStatus.ERROR
                                            statusMessage = invalidProfileSnapshot
                                        }
                                }
                                "ack" -> {
                                    val acknowledgement = ProtocolMessages
                                        .actionAcknowledgement(rawMessage)
                                        ?: return
                                    val buttonId = pendingPresses[acknowledgement.requestId] ?: return
                                    when (acknowledgement.status) {
                                        ActionAcknowledgementStatus.ACCEPTED -> {
                                            buttonStates = buttonStates + (
                                                buttonId to ButtonExecutionState.EXECUTING
                                            )
                                        }
                                        ActionAcknowledgementStatus.COMPLETED -> {
                                            buttonStates = buttonStates + (
                                                buttonId to ButtonExecutionState.COMPLETED
                                            )
                                            pendingPresses = pendingPresses - acknowledgement.requestId
                                            statusMessage = acknowledgement.message ?: "Ação concluída"
                                        }
                                        ActionAcknowledgementStatus.REJECTED -> {
                                            buttonStates = buttonStates + (
                                                buttonId to ButtonExecutionState.REJECTED
                                            )
                                            pendingPresses = pendingPresses - acknowledgement.requestId
                                            statusMessage = acknowledgement.message ?: "Ação rejeitada"
                                        }
                                    }
                                }
                                "error" -> {
                                    val payload = JSONObject(rawMessage).optJSONObject("payload")
                                    val requestId = payload?.optString("request_id")
                                        ?.takeIf { it.isNotBlank() }
                                    val message = payload?.optString("message")
                                        ?.ifBlank { "Erro do servidor" }
                                        ?: "Erro do servidor"
                                    val buttonId = requestId?.let { pendingPresses[it] }
                                    if (buttonId == null) {
                                        status = ConnectionStatus.ERROR
                                        statusMessage = message
                                    } else {
                                        buttonStates = buttonStates + (
                                            buttonId to ButtonExecutionState.REJECTED
                                        )
                                        pendingPresses = pendingPresses - requestId
                                        statusMessage = message
                                    }
                                }
                            }
                        }

                        override fun onClosed() {
                            if (status == ConnectionStatus.CONNECTED) {
                                status = ConnectionStatus.DISCONNECTED
                                rejectPendingActions("Conexão encerrada")
                            }
                        }

                        override fun onFailure(message: String) {
                            status = ConnectionStatus.ERROR
                            rejectPendingActions(message)
                        }
                    },
                )
            } catch (error: Exception) {
                status = ConnectionStatus.ERROR
                statusMessage = error.message ?: "Não foi possível conectar"
            }
        }
    }

    fun pressButton(button: StreamDeckButton) {
        val snapshot = profileSnapshot ?: return
        if (buttonStates[button.id] == ButtonExecutionState.EXECUTING) {
            return
        }
        val activeSocket = socket
        if (status != ConnectionStatus.CONNECTED || activeSocket == null) {
            buttonStates = buttonStates + (button.id to ButtonExecutionState.REJECTED)
            statusMessage = actionNotConnected
            return
        }
        val requestId = UUID.randomUUID().toString()
        buttonStates = buttonStates + (button.id to ButtonExecutionState.EXECUTING)
        pendingPresses = pendingPresses + (requestId to button.id)
        val wasSent = activeSocket.send(
            ProtocolMessages.press(
                requestId = requestId,
                profileId = snapshot.profileId,
                pageId = snapshot.activePage.id,
                buttonId = button.id,
                revision = snapshot.revision,
            ),
        )
        if (!wasSent) {
            buttonStates = buttonStates + (button.id to ButtonExecutionState.REJECTED)
            pendingPresses = pendingPresses - requestId
            statusMessage = actionSendFailed
        }
    }

    fun startEditing() {
        val snapshot = profileSnapshot ?: return
        editorDraft = ProfileEditorDraft.from(snapshot)
        editorOriginalDraft = editorDraft
        editorError = null
        editingProfile = true
    }

    fun cancelEditing() {
        profileSnapshot?.let { snapshot ->
            editorDraft = ProfileEditorDraft.from(snapshot)
        }
        editorOriginalDraft = null
        editorError = null
        editingProfile = false
    }

    fun revertEditing() {
        val original = editorOriginalDraft ?: return
        editorDraft = original
        editorError = null
        statusMessage = "Alterações revertidas"
    }

    fun saveProfile() {
        val snapshot = profileSnapshot ?: return
        val draft = editorDraft ?: return
        val updated = runCatching { draft.applyTo(snapshot) }
            .getOrElse { error ->
                editorError = error.message ?: "Dados do perfil inválidos"
                return
            }
        val nextRevision = snapshot.revision + 1
        val wire = runCatching {
            ProfileSnapshotSerializer.toWire(updated, revision = nextRevision)
        }.getOrElse { error ->
            editorError = error.message ?: "Não foi possível preparar o perfil"
            return
        }
        savingProfile = true
        editorError = null
        profileSnapshot = updated.copy(revision = nextRevision)
        scope.launch {
            try {
                val endpoint = ServerEndpoint.parse(serverAddress)
                val token = accessToken
                    ?: throw PairingException("TOKEN_MISSING", "Token de pareamento ausente")
                val authenticatedClientId = pairedClientId ?: clientId.trim()
                val response = pairingClient.updateProfile(
                    endpoint = endpoint,
                    clientId = authenticatedClientId,
                    accessToken = token,
                    profileId = snapshot.profileId,
                    expectedRevision = snapshot.revision,
                    profileWire = wire,
                )
                val confirmed = ProfileSnapshotParser.parseWireProfile(response)
                profileSnapshot = confirmed
                editorDraft = ProfileEditorDraft.from(confirmed)
                editorOriginalDraft = null
                savingProfile = false
                editingProfile = false
                editorError = null
                statusMessage = "Perfil salvo na revisão ${confirmed.revision}"
            } catch (error: Exception) {
                profileSnapshot = snapshot
                savingProfile = false
                editorError = error.message ?: "Não foi possível salvar o perfil"
                statusMessage = "Falha ao salvar o perfil; revise e tente novamente"
            }
        }
    }

    fun loadManagedProfiles(targetProfileId: String? = managedSelectedId) {
        scope.launch {
            managementLoading = true
            managementError = null
            managementConflictCode = null
            managementConflictMessage = null
            try {
                val endpoint = ServerEndpoint.parse(serverAddress)
                val token = accessToken
                    ?: throw PairingException("TOKEN_MISSING", "Token de pareamento ausente")
                val authenticatedClientId = pairedClientId ?: clientId.trim()
                val profiles = pairingClient.listProfiles(
                    endpoint = endpoint,
                    clientId = authenticatedClientId,
                    accessToken = token,
                )
                managedProfiles = profiles
                val selected = targetProfileId
                    ?.takeIf { id -> profiles.any { it.profileId == id } }
                    ?: managedSelectedId?.takeIf { id -> profiles.any { it.profileId == id } }
                    ?: profiles.firstOrNull()?.profileId
                managedSelectedId = selected
                managedSnapshot = selected?.let { profileId ->
                    ProfileSnapshotParser.parseWireProfile(
                        pairingClient.getProfile(
                            endpoint = endpoint,
                            clientId = authenticatedClientId,
                            accessToken = token,
                            profileId = profileId,
                        ),
                    )
                }
                managedSnapshot?.let { loaded ->
                    if (loaded.profileId == profileSnapshot?.profileId) {
                        profileSnapshot = loaded
                        editorDraft = ProfileEditorDraft.from(loaded)
                    }
                }
            } catch (error: Exception) {
                managementError = safeManagementMessage(error)
            } finally {
                managementLoading = false
            }
        }
    }

    fun openProfileManagement() {
        managingProfiles = true
        managementSuccess = null
        managementError = null
        managementExportJson = ""
        managementImportJson = ""
        loadManagedProfiles()
    }

    fun runManagementMutation(
        profileId: String,
        expectedRevision: Int,
        operation: suspend (ServerEndpoint, String, String) -> String,
    ) {
        managementRetry = {
            runManagementMutation(profileId, expectedRevision, operation)
        }
        scope.launch {
            managementLoading = true
            managementSuccess = null
            managementError = null
            managementConflictCode = null
            managementConflictMessage = null
            try {
                val endpoint = ServerEndpoint.parse(serverAddress)
                val token = accessToken
                    ?: throw PairingException("TOKEN_MISSING", "Token de pareamento ausente")
                val authenticatedClientId = pairedClientId ?: clientId.trim()
                val response = operation(endpoint, authenticatedClientId, token)
                runCatching { ProfileSnapshotParser.parseWireProfile(response) }
                    .onSuccess { updated ->
                        managedSnapshot = updated
                        if (updated.profileId == profileSnapshot?.profileId) {
                            profileSnapshot = updated
                            editorDraft = ProfileEditorDraft.from(updated)
                        }
                    }
                managementSuccess = "Operação concluída na revisão retornada pelo servidor"
                managementRetry = null
                loadManagedProfiles(profileId)
            } catch (error: Exception) {
                if (error is PairingException && error.code in setOf(
                        "PROFILE_REVISION_CONFLICT",
                        "PROFILE_DELETE_PROTECTED",
                        "PAGE_DELETE_PROTECTED",
                    )
                ) {
                    managementConflictCode = error.code
                    managementConflictMessage = error.message
                } else {
                    managementError = safeManagementMessage(error)
                }
            } finally {
                managementLoading = false
            }
        }
    }

    fun selectedManagedProfile(): RemoteProfileSummary? = managedSelectedId?.let { selectedId ->
        managedProfiles.singleOrNull { it.profileId == selectedId }
    }

    fun managedRevision(): Int = managedSnapshot?.revision
        ?: selectedManagedProfile()?.revision
        ?: throw IllegalArgumentException("Perfil selecionado não está carregado")

    fun renameManagedProfile(name: String) {
        val selected = selectedManagedProfile() ?: return
        runManagementMutation(selected.profileId, managedRevision()) { endpoint, id, token ->
            pairingClient.renameProfile(endpoint, id, token, selected.profileId, managedRevision(), name)
        }
    }

    fun createManagedProfile(profileId: String, profileName: String) {
        val template = managedSnapshot ?: return
        runCatching {
            val normalizedId = profileId.trim()
            val normalizedName = profileName.trim()
            require(normalizedId.isNotEmpty()) { "ID do perfil é obrigatório" }
            require(normalizedName.isNotEmpty()) { "Nome do perfil é obrigatório" }
            val pages = template.pages.map { page ->
                page.copy(buttons = page.buttons.map { button ->
                    button.copy(id = "$normalizedId-${button.id}")
                })
            }
            template.copy(
                profileId = normalizedId,
                profileName = normalizedName,
                revision = 1,
                activePage = pages.single { it.id == template.activePage.id },
                pages = pages,
            )
        }.onSuccess { newSnapshot ->
            val wire = ProfileSnapshotSerializer.toWire(newSnapshot, revision = 1)
            runManagementMutation(newSnapshot.profileId, 1) { endpoint, id, token ->
                pairingClient.createProfile(endpoint, id, token, 1, wire)
            }
        }.onFailure { error -> managementError = safeManagementMessage(error) }
    }

    fun duplicateManagedProfile(newProfileId: String, newProfileName: String) {
        val selected = selectedManagedProfile() ?: return
        runManagementMutation(selected.profileId, managedRevision()) { endpoint, id, token ->
            pairingClient.duplicateProfile(
                endpoint,
                id,
                token,
                selected.profileId,
                managedRevision(),
                newProfileId.trim(),
                newProfileName.trim().ifEmpty { null },
            )
        }
    }

    fun activateManagedProfile() {
        val selected = selectedManagedProfile() ?: return
        runManagementMutation(selected.profileId, managedRevision()) { endpoint, id, token ->
            pairingClient.activateProfile(endpoint, id, token, selected.profileId, managedRevision())
        }
    }

    fun deleteManagedProfile(replacementProfileId: String?) {
        val selected = selectedManagedProfile() ?: return
        if (selected.isActive && replacementProfileId.isNullOrBlank()) {
            managementError = "Informe explicitamente um perfil substituto para o perfil ativo"
            return
        }
        runManagementMutation(selected.profileId, managedRevision()) { endpoint, id, token ->
            pairingClient.deleteProfile(
                endpoint,
                id,
                token,
                selected.profileId,
                managedRevision(),
                replacementProfileId?.trim()?.ifEmpty { null },
            )
        }
    }

    fun createManagedPage(pageId: String, title: String, order: Int) {
        val selected = selectedManagedProfile() ?: return
        val current = managedSnapshot ?: return
        runCatching {
            val normalizedId = pageId.trim()
            require(normalizedId.isNotEmpty()) { "ID da página é obrigatório" }
            require(title.trim().isNotEmpty()) { "Título da página é obrigatório" }
            require(order >= 0) { "A ordem deve ser não negativa" }
            current.activePage.copy(
                id = normalizedId,
                title = title.trim(),
                order = order,
                buttons = current.activePage.buttons.map { button ->
                    button.copy(id = "$normalizedId-${button.id}")
                },
            )
        }.onSuccess { page ->
            runManagementMutation(selected.profileId, current.revision) { endpoint, id, token ->
                pairingClient.createPage(endpoint, id, token, selected.profileId, current.revision, page)
            }
        }.onFailure { error -> managementError = safeManagementMessage(error) }
    }

    fun renameManagedPage(pageId: String, title: String) {
        val selected = selectedManagedProfile() ?: return
        val current = managedSnapshot ?: return
        runManagementMutation(selected.profileId, current.revision) { endpoint, id, token ->
            pairingClient.renamePage(
                endpoint,
                id,
                token,
                selected.profileId,
                pageId.trim(),
                current.revision,
                title,
            )
        }
    }

    fun reorderManagedPage(pageId: String, order: Int) {
        val selected = selectedManagedProfile() ?: return
        val current = managedSnapshot ?: return
        runManagementMutation(selected.profileId, current.revision) { endpoint, id, token ->
            pairingClient.reorderPage(
                endpoint,
                id,
                token,
                selected.profileId,
                pageId.trim(),
                current.revision,
                order,
            )
        }
    }

    fun deleteManagedPage(pageId: String, replacementPageId: String?) {
        val selected = selectedManagedProfile() ?: return
        val current = managedSnapshot ?: return
        if (pageId.trim() == current.activePage.id && replacementPageId.isNullOrBlank()) {
            managementError = "Informe explicitamente uma página substituta para a página ativa"
            return
        }
        runManagementMutation(selected.profileId, current.revision) { endpoint, id, token ->
            pairingClient.deletePage(
                endpoint,
                id,
                token,
                selected.profileId,
                pageId.trim(),
                current.revision,
                replacementPageId?.trim()?.ifEmpty { null },
            )
        }
    }

    fun exportManagedProfile() {
        val selected = selectedManagedProfile() ?: return
        scope.launch {
            managementLoading = true
            managementError = null
            try {
                val endpoint = ServerEndpoint.parse(serverAddress)
                val token = accessToken
                    ?: throw PairingException("TOKEN_MISSING", "Token de pareamento ausente")
                val authenticatedClientId = pairedClientId ?: clientId.trim()
                managementExportJson = pairingClient.exportProfileJson(
                    endpoint,
                    authenticatedClientId,
                    token,
                    selected.profileId,
                )
                managementSuccess = "JSON exportado em memória"
            } catch (error: Exception) {
                managementError = safeManagementMessage(error)
            } finally {
                managementLoading = false
            }
        }
    }

    fun importManagedProfile() {
        val selected = selectedManagedProfile() ?: return
        val current = managedSnapshot ?: return
        val imported = runCatching {
            ProfileSnapshotParser.parseWireProfile(managementImportJson)
        }.getOrElse { error ->
            managementError = error.message ?: "JSON de perfil inválido"
            return
        }
        if (imported.profileId != selected.profileId) {
            managementError = "O ID do JSON deve ser o mesmo do perfil selecionado"
            return
        }
        runManagementMutation(selected.profileId, current.revision) { endpoint, id, token ->
            pairingClient.importProfileJson(
                endpoint,
                id,
                token,
                current.revision,
                managementImportJson,
            )
        }
    }

    fun resolveManagementConflict(resolution: br.com.gustavo.streamdeck.ui.ConflictResolution) {
        when (resolution) {
            br.com.gustavo.streamdeck.ui.ConflictResolution.RETRY -> {
                managementConflictCode = null
                managementConflictMessage = null
                managementRetry?.invoke()
            }
            br.com.gustavo.streamdeck.ui.ConflictResolution.RELOAD -> {
                managementConflictCode = null
                managementConflictMessage = null
                managementRetry = null
                loadManagedProfiles(managedSelectedId)
            }
            br.com.gustavo.streamdeck.ui.ConflictResolution.CANCEL -> {
                managementConflictCode = null
                managementConflictMessage = null
                managementRetry = null
            }
        }
    }

    fun clearPairing() {
        socket?.cancel()
        socket = null
        accessToken = null
        pairedClientId = null
        pairedServerBaseUrl = null
        tlsTrust = null
        caCertificatePem = ""
        trustCode = ""
        pairingStore.clear()
        status = ConnectionStatus.DISCONNECTED
        statusMessage = "Pareamento removido"
        profileSnapshot = null
        editingProfile = false
        editorDraft = null
        savingProfile = false
        editorError = null
        managingProfiles = false
        managedProfiles = emptyList()
        managedSelectedId = null
        managedSnapshot = null
        managementLoading = false
        managementSuccess = null
        managementError = null
        managementConflictCode = null
        managementConflictMessage = null
        managementExportJson = ""
        managementImportJson = ""
        managementRetry = null
        buttonStates = emptyMap()
        pendingPresses = emptyMap()
    }

    val snapshot = profileSnapshot
    val draft = editorDraft
    if (snapshot == null) {
        PairingForm(
            serverAddress = serverAddress,
            onServerAddressChange = { updatedAddress ->
                serverAddress = updatedAddress
                val updatedBaseUrl = runCatching {
                    ServerEndpoint.parse(updatedAddress).httpBaseUrl
                }.getOrNull()
                if (pairedServerBaseUrl != null && updatedBaseUrl != pairedServerBaseUrl) {
                    accessToken = null
                    pairedClientId = null
                    pairedServerBaseUrl = null
                    tlsTrust = null
                    pairingStore.clear()
                }
            },
            clientId = clientId,
            onClientIdChange = { updatedClientId ->
                clientId = updatedClientId
                if (updatedClientId.trim() != pairedClientId) {
                    accessToken = null
                    pairedClientId = null
                    pairedServerBaseUrl = null
                    tlsTrust = null
                    pairingStore.clear()
                }
            },
            pairingCode = pairingCode,
            onPairingCodeChange = { pairingCode = it },
            caCertificatePem = caCertificatePem,
            onCaCertificatePemChange = {
                caCertificatePem = it
                tlsTrust = null
            },
            trustCode = trustCode,
            onTrustCodeChange = {
                trustCode = it
                tlsTrust = null
            },
            onConnect = ::connect,
            onClearPairing = ::clearPairing,
            status = status,
            statusMessage = statusMessage,
            revision = null,
        )
    } else if (managingProfiles) {
        ProfileManagementScreen(
            profiles = managedProfiles,
            selectedProfileId = managedSelectedId,
            snapshot = managedSnapshot,
            loading = managementLoading,
            successMessage = managementSuccess,
            errorMessage = managementError,
            conflictCode = managementConflictCode,
            conflictMessage = managementConflictMessage,
            exportJson = managementExportJson,
            importJson = managementImportJson,
            onImportJsonChange = { managementImportJson = it },
            onSelectProfile = { profileId ->
                managedSelectedId = profileId
                loadManagedProfiles(profileId)
            },
            onCreateProfile = ::createManagedProfile,
            onRenameProfile = ::renameManagedProfile,
            onDuplicateProfile = ::duplicateManagedProfile,
            onActivateProfile = ::activateManagedProfile,
            onDeleteProfile = ::deleteManagedProfile,
            onCreatePage = ::createManagedPage,
            onRenamePage = ::renameManagedPage,
            onReorderPage = ::reorderManagedPage,
            onDeletePage = ::deleteManagedPage,
            onExport = ::exportManagedProfile,
            onImport = ::importManagedProfile,
            onConflictResolution = ::resolveManagementConflict,
            onClose = {
                managingProfiles = false
                managementConflictCode = null
                managementConflictMessage = null
            },
        )
    } else if (editingProfile && draft != null) {
        ProfileEditorScreen(
            snapshot = snapshot,
            draft = draft,
            saving = savingProfile,
            errorMessage = editorError,
            // Undo is a recovery action for save failures (roadmap Fase 4):
            // it only appears after a failed save, when a revert is meaningful.
            hasChangesToRevert = editorOriginalDraft != null && editorError != null,
            onDraftChange = { editorDraft = it },
            onSave = ::saveProfile,
            onCancel = ::cancelEditing,
            onRevert = ::revertEditing,
        )
    } else {
        ConnectedDeckScreen(
            snapshot = snapshot,
            connectionStatus = status,
            statusMessage = statusMessage,
            buttonStates = buttonStates,
            onButtonPress = ::pressButton,
            onEditProfile = ::startEditing,
            onManageProfiles = ::openProfileManagement,
            onClearPairing = ::clearPairing,
        )
    }
}

@Composable
private fun PairingForm(
    serverAddress: String,
    onServerAddressChange: (String) -> Unit,
    clientId: String,
    onClientIdChange: (String) -> Unit,
    pairingCode: String,
    onPairingCodeChange: (String) -> Unit,
    caCertificatePem: String,
    onCaCertificatePemChange: (String) -> Unit,
    trustCode: String,
    onTrustCodeChange: (String) -> Unit,
    onConnect: () -> Unit,
    onClearPairing: () -> Unit,
    status: ConnectionStatus,
    statusMessage: String?,
    revision: Int?,
) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(24.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        AppTitle(subtitle = stringResource(R.string.phase2_subtitle))
        OutlinedTextField(
            modifier = Modifier.fillMaxWidth(),
            value = serverAddress,
            onValueChange = onServerAddressChange,
            label = { Text(stringResource(R.string.server_address_label)) },
            singleLine = true,
        )
        OutlinedTextField(
            modifier = Modifier.fillMaxWidth(),
            value = clientId,
            onValueChange = onClientIdChange,
            label = { Text(stringResource(R.string.client_id_label)) },
            singleLine = true,
        )
        OutlinedTextField(
            modifier = Modifier.fillMaxWidth(),
            value = pairingCode,
            onValueChange = onPairingCodeChange,
            label = { Text(stringResource(R.string.pairing_code_label)) },
            supportingText = {
                Text(stringResource(R.string.pairing_code_supporting_text))
            },
            singleLine = true,
        )
        OutlinedTextField(
            modifier = Modifier.fillMaxWidth(),
            value = caCertificatePem,
            onValueChange = onCaCertificatePemChange,
            label = { Text("CA privada (PEM)") },
            supportingText = {
                Text("Cole o certificado público entregue fora de banda pelo Windows")
            },
            minLines = 3,
            maxLines = 5,
        )
        OutlinedTextField(
            modifier = Modifier.fillMaxWidth(),
            value = trustCode,
            onValueChange = onTrustCodeChange,
            label = { Text("Código de confiança") },
            supportingText = {
                Text("Confirme o código exibido no Windows antes de conectar")
            },
            singleLine = true,
        )
        Button(
            modifier = Modifier.fillMaxWidth(),
            onClick = onConnect,
            enabled = serverAddress.isNotBlank() &&
                clientId.isNotBlank() &&
                caCertificatePem.isNotBlank() &&
                trustCode.isNotBlank(),
        ) {
            Text(stringResource(R.string.pair_and_connect))
        }
        OutlinedButton(
            modifier = Modifier.fillMaxWidth(),
            onClick = onClearPairing,
        ) {
            Text(stringResource(R.string.clear_pairing))
        }
        ConnectionStatusBlock(
            status = status,
            statusMessage = statusMessage,
            revision = revision,
        )
    }
}

@Composable
private fun ConnectedDeckScreen(
    snapshot: StreamDeckProfileSnapshot,
    connectionStatus: ConnectionStatus,
    statusMessage: String?,
    buttonStates: Map<String, ButtonExecutionState>,
    onButtonPress: (StreamDeckButton) -> Unit,
    onEditProfile: () -> Unit,
    onManageProfiles: () -> Unit,
    onClearPairing: () -> Unit,
) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        AppTitle(subtitle = stringResource(R.string.phase3_subtitle))
        Text(
            text = stringResource(R.string.active_page, snapshot.activePage.title),
            style = MaterialTheme.typography.titleMedium,
        )
        ConnectionStatusBlock(
            status = connectionStatus,
            statusMessage = statusMessage,
            revision = snapshot.revision,
        )
        StreamDeckGrid(
            page = snapshot.activePage,
            buttonStates = buttonStates,
            onButtonPress = onButtonPress,
            modifier = Modifier
                .fillMaxWidth()
                .weight(1f),
        )
        OutlinedButton(
            modifier = Modifier.fillMaxWidth(),
            onClick = onEditProfile,
        ) {
            Text("Editar perfil")
        }
        OutlinedButton(
            modifier = Modifier.fillMaxWidth(),
            onClick = onManageProfiles,
        ) {
            Text("Gerenciar perfis e páginas")
        }
        OutlinedButton(
            modifier = Modifier.fillMaxWidth(),
            onClick = onClearPairing,
        ) {
            Text(stringResource(R.string.clear_pairing))
        }
    }
}

@Composable
private fun AppTitle(subtitle: String) {
    Text(
        modifier = Modifier.fillMaxWidth(),
        text = stringResource(R.string.app_title),
        style = MaterialTheme.typography.headlineMedium,
        textAlign = TextAlign.Center,
    )
    Text(
        modifier = Modifier.fillMaxWidth(),
        text = subtitle,
        style = MaterialTheme.typography.bodyLarge,
        textAlign = TextAlign.Center,
    )
}

@Composable
private fun ConnectionStatusBlock(
    status: ConnectionStatus,
    statusMessage: String?,
    revision: Int?,
) {
    Text(
        text = when (status) {
            ConnectionStatus.DISCONNECTED -> stringResource(R.string.status_disconnected)
            ConnectionStatus.CONNECTING -> stringResource(R.string.status_connecting)
            ConnectionStatus.CONNECTED -> stringResource(R.string.status_connected)
            ConnectionStatus.ERROR -> stringResource(R.string.status_error)
        },
        style = MaterialTheme.typography.titleMedium,
    )
    statusMessage?.let { message ->
        Text(
            text = message,
            style = MaterialTheme.typography.bodyMedium,
            modifier = Modifier.semantics { liveRegion = LiveRegionMode.Polite },
        )
    }
    revision?.let { currentRevision ->
        Text(
            text = stringResource(R.string.profile_revision, currentRevision),
            style = MaterialTheme.typography.bodyMedium,
        )
    }
}
