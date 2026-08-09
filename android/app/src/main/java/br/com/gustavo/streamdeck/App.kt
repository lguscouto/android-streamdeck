package br.com.gustavo.streamdeck


import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
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
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.platform.LocalContext
import kotlinx.coroutines.launch
import okhttp3.WebSocket
import org.json.JSONObject
import br.com.gustavo.streamdeck.network.PairingClient
import br.com.gustavo.streamdeck.network.PairingCredentials
import br.com.gustavo.streamdeck.network.PairingException
import br.com.gustavo.streamdeck.network.EncryptedPairingStore
import br.com.gustavo.streamdeck.network.ServerEndpoint
import br.com.gustavo.streamdeck.network.StreamDeckSocketListener
import br.com.gustavo.streamdeck.network.StreamDeckWebSocketClient

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
    var revision by remember { mutableStateOf<Int?>(null) }
    var socket by remember { mutableStateOf<WebSocket?>(null) }

    DisposableEffect(Unit) {
        onDispose {
            socket?.close(1000, "screen closed")
        }
    }

    fun connect() {
        scope.launch {
            status = ConnectionStatus.CONNECTING
            statusMessage = null
            revision = null
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
                                    revision = runCatching {
                                        JSONObject(rawMessage)
                                            .getJSONObject("payload")
                                            .getJSONObject("profile")
                                            .getInt("revision")
                                    }.getOrNull()
                                }
                                "error" -> {
                                    val payload = JSONObject(rawMessage)
                                        .optJSONObject("payload")
                                    status = ConnectionStatus.ERROR
                                    statusMessage = payload?.optString("message")
                                        ?.ifBlank { "Erro do servidor" }
                                }
                            }
                        }

                        override fun onClosed() {
                            if (status == ConnectionStatus.CONNECTED) {
                                status = ConnectionStatus.DISCONNECTED
                                statusMessage = "Conexão encerrada"
                            }
                        }

                        override fun onFailure(message: String) {
                            status = ConnectionStatus.ERROR
                            statusMessage = message
                        }
                    },
                )
            } catch (error: Exception) {
                status = ConnectionStatus.ERROR
                statusMessage = error.message ?: "Não foi possível conectar"
            }
        }
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(24.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        Text(
            modifier = Modifier.fillMaxWidth(),
            text = stringResource(R.string.app_title),
            style = MaterialTheme.typography.headlineMedium,
            textAlign = TextAlign.Center,
        )
        Text(
            modifier = Modifier.fillMaxWidth(),
            text = stringResource(R.string.phase2_subtitle),
            style = MaterialTheme.typography.bodyLarge,
            textAlign = TextAlign.Center,
        )
        OutlinedTextField(
            modifier = Modifier.fillMaxWidth(),
            value = serverAddress,
            onValueChange = { updatedAddress ->
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
            label = { Text(stringResource(R.string.server_address_label)) },
            singleLine = true,
        )
        OutlinedTextField(
            modifier = Modifier.fillMaxWidth(),
            value = clientId,
            onValueChange = { updatedClientId ->
                clientId = updatedClientId
                if (updatedClientId.trim() != pairedClientId) {
                    accessToken = null
                    pairedClientId = null
                    pairedServerBaseUrl = null
                    pairingStore.clear()
                }
            },
            label = { Text(stringResource(R.string.client_id_label)) },
            singleLine = true,
        )
        OutlinedTextField(
            modifier = Modifier.fillMaxWidth(),
            value = pairingCode,
            onValueChange = { pairingCode = it },
            label = { Text(stringResource(R.string.pairing_code_label)) },
            supportingText = {
                Text(stringResource(R.string.pairing_code_supporting_text))
            },
            singleLine = true,
        )
        Button(
            modifier = Modifier.fillMaxWidth(),
            onClick = ::connect,
            enabled = serverAddress.isNotBlank() && clientId.isNotBlank(),
        ) {
            Text(stringResource(R.string.pair_and_connect))
        }
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            OutlinedButton(
                modifier = Modifier.weight(1f),
                onClick = {
                    socket?.cancel()
                    accessToken = null
                    pairedClientId = null
                    pairedServerBaseUrl = null
                    pairingStore.clear()
                    status = ConnectionStatus.DISCONNECTED
                    statusMessage = "Pareamento removido"
                    revision = null
                },
            ) {
                Text(stringResource(R.string.clear_pairing))
            }
        }
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
}
