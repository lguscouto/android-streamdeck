package br.com.gustavo.streamdeck

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
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
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import br.com.gustavo.streamdeck.network.ActionAcknowledgementStatus
import br.com.gustavo.streamdeck.network.EncryptedPairingStore
import br.com.gustavo.streamdeck.network.PairingClient
import br.com.gustavo.streamdeck.network.PairingCredentials
import br.com.gustavo.streamdeck.network.PairingException
import br.com.gustavo.streamdeck.network.ProfileSnapshotParser
import br.com.gustavo.streamdeck.network.ProfileSnapshotSerializer
import br.com.gustavo.streamdeck.network.ProtocolMessages
import br.com.gustavo.streamdeck.network.ServerEndpoint
import br.com.gustavo.streamdeck.network.StreamDeckButton
import br.com.gustavo.streamdeck.network.StreamDeckProfileSnapshot
import br.com.gustavo.streamdeck.network.StreamDeckSocketListener
import br.com.gustavo.streamdeck.network.StreamDeckWebSocketClient
import br.com.gustavo.streamdeck.ui.ButtonExecutionState
import br.com.gustavo.streamdeck.ui.ProfileEditorDraft
import br.com.gustavo.streamdeck.ui.ProfileEditorScreen
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

@Composable
fun StreamDeckApp() {
    MaterialTheme {
        Surface(
            modifier = Modifier.fillMaxSize(),
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
        mutableStateOf(storedCredentials?.serverBaseUrl ?: "http://10.0.2.2:8765")
    }
    var pairingCode by remember { mutableStateOf("") }
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
    var savingProfile by remember { mutableStateOf(false) }
    var editorError by remember { mutableStateOf<String?>(null) }
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
                    pairingStore.clear()
                    token = null
                }
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
        editorError = null
        editingProfile = true
    }

    fun cancelEditing() {
        profileSnapshot?.let { snapshot ->
            editorDraft = ProfileEditorDraft.from(snapshot)
        }
        editorError = null
        editingProfile = false
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

    fun clearPairing() {
        socket?.cancel()
        socket = null
        accessToken = null
        pairedClientId = null
        pairedServerBaseUrl = null
        pairingStore.clear()
        status = ConnectionStatus.DISCONNECTED
        statusMessage = "Pareamento removido"
        profileSnapshot = null
        editingProfile = false
        editorDraft = null
        savingProfile = false
        editorError = null
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
                    pairingStore.clear()
                }
            },
            pairingCode = pairingCode,
            onPairingCodeChange = { pairingCode = it },
            onConnect = ::connect,
            onClearPairing = ::clearPairing,
            status = status,
            statusMessage = statusMessage,
            revision = null,
        )
    } else if (editingProfile && draft != null) {
        ProfileEditorScreen(
            snapshot = snapshot,
            draft = draft,
            saving = savingProfile,
            errorMessage = editorError,
            onDraftChange = { editorDraft = it },
            onSave = ::saveProfile,
            onCancel = ::cancelEditing,
        )
    } else {
        ConnectedDeckScreen(
            snapshot = snapshot,
            connectionStatus = status,
            statusMessage = statusMessage,
            buttonStates = buttonStates,
            onButtonPress = ::pressButton,
            onEditProfile = ::startEditing,
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
    onConnect: () -> Unit,
    onClearPairing: () -> Unit,
    status: ConnectionStatus,
    statusMessage: String?,
    revision: Int?,
) {
    Column(
        modifier = Modifier
            .fillMaxSize()
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
        Button(
            modifier = Modifier.fillMaxWidth(),
            onClick = onConnect,
            enabled = serverAddress.isNotBlank() && clientId.isNotBlank(),
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
        Text(text = message, style = MaterialTheme.typography.bodyMedium)
    }
    revision?.let { currentRevision ->
        Text(
            text = stringResource(R.string.profile_revision, currentRevision),
            style = MaterialTheme.typography.bodyMedium,
        )
    }
}
