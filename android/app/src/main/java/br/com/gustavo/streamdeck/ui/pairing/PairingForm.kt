package br.com.gustavo.streamdeck.ui.pairing

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawing
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.Build
import androidx.compose.material.icons.outlined.Edit
import androidx.compose.material.icons.outlined.LinkOff
import androidx.compose.material.icons.outlined.MoreVert
import androidx.compose.material.icons.outlined.Settings
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
import br.com.gustavo.streamdeck.network.StreamDeckPage
import br.com.gustavo.streamdeck.network.StreamDeckProfileSnapshot
import br.com.gustavo.streamdeck.network.StreamDeckSocketListener
import br.com.gustavo.streamdeck.network.StreamDeckWebSocketClient
import br.com.gustavo.streamdeck.network.TlsTrust
import br.com.gustavo.streamdeck.ui.ButtonExecutionState
import br.com.gustavo.streamdeck.ui.ProfileEditorDraft
import br.com.gustavo.streamdeck.ui.ProfileEditorScreen
import br.com.gustavo.streamdeck.ui.ProfileManagementScreen
import br.com.gustavo.streamdeck.ui.StreamDeckGrid
import br.com.gustavo.streamdeck.ui.components.ConnectionPill
import br.com.gustavo.streamdeck.ui.deck.ConnectedDeckScreen
import br.com.gustavo.streamdeck.ui.components.ConnectionStatus
import br.com.gustavo.streamdeck.ui.pairing.PairingForm
import br.com.gustavo.streamdeck.ui.components.PagePager
import br.com.gustavo.streamdeck.ui.navigation.StreamDeckDestination
import br.com.gustavo.streamdeck.ui.settings.DeckDensity
import br.com.gustavo.streamdeck.ui.settings.SettingsScreen
import br.com.gustavo.streamdeck.ui.settings.StreamDeckPreferences
import br.com.gustavo.streamdeck.ui.settings.StreamDeckPreferencesStore
import br.com.gustavo.streamdeck.ui.theme.StreamDeckTheme
import java.util.UUID
import kotlinx.coroutines.launch
import okhttp3.WebSocket
import org.json.JSONObject

import br.com.gustavo.streamdeck.AppMetadata
import br.com.gustavo.streamdeck.R
@Composable
fun PairingForm(
    serverAddress: String,
    onServerAddressChange: (String) -> Unit,
    clientId: String,
    onClientIdChange: (String) -> Unit,
    pairingCode: String,
    onPairingCodeChange: (String) -> Unit,
    hasStoredAccessToken: Boolean,
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
    var advancedExpanded by remember {
        mutableStateOf(caCertificatePem.isNotBlank() || trustCode.isNotBlank())
    }
    val canConnect = serverAddress.isNotBlank() &&
        clientId.isNotBlank() &&
        (pairingCode.isNotBlank() || hasStoredAccessToken) &&
        caCertificatePem.isNotBlank() &&
        trustCode.isNotBlank()

    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(horizontal = 16.dp, vertical = 20.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        Card(
            modifier = Modifier.fillMaxWidth(),
            shape = br.com.gustavo.streamdeck.ui.theme.CommandShapes.card,
            colors = CardDefaults.cardColors(
                containerColor = MaterialTheme.colorScheme.surface,
            ),
        ) {
            Column(
                modifier = Modifier.padding(20.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                Text(
                    text = "COMMAND SURFACE",
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.primary,
                )
                Text(
                    text = stringResource(R.string.app_title),
                    style = MaterialTheme.typography.displaySmall,
                )
                Text(
                    text = "Seu painel de comandos, organizado e seguro.",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                HorizontalDivider(modifier = Modifier.padding(vertical = 6.dp))
                Text(
                    text = "1  ·  Conectar ao servidor",
                    style = MaterialTheme.typography.titleMedium,
                )
                Text(
                    text = "Informe os dados básicos. A conexão só será liberada após validar a identidade TLS.",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
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
            }
        }

        Card(
            modifier = Modifier.fillMaxWidth(),
            shape = br.com.gustavo.streamdeck.ui.theme.CommandShapes.card,
            colors = CardDefaults.cardColors(
                containerColor = MaterialTheme.colorScheme.surface,
            ),
        ) {
            Column(
                modifier = Modifier.padding(20.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    verticalAlignment = androidx.compose.ui.Alignment.CenterVertically,
                ) {
                    Column(modifier = Modifier.weight(1f)) {
                        Text("2  ·  Segurança da conexão", style = MaterialTheme.typography.titleMedium)
                        Text(
                            "HTTPS/WSS e certificado privado",
                            style = MaterialTheme.typography.bodyMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                    TextButton(onClick = { advancedExpanded = !advancedExpanded }) {
                        Text(if (advancedExpanded) "Ocultar" else "Exibir")
                    }
                }
                AnimatedVisibility(visible = advancedExpanded) {
                    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                        OutlinedTextField(
                            modifier = Modifier.fillMaxWidth(),
                            value = caCertificatePem,
                            onValueChange = onCaCertificatePemChange,
                            label = { Text("CA privada (PEM)") },
                            supportingText = {
                                Text("Certificado público entregue fora de banda pelo Windows")
                            },
                            minLines = 3,
                            maxLines = 6,
                        )
                        OutlinedTextField(
                            modifier = Modifier.fillMaxWidth(),
                            value = trustCode,
                            onValueChange = onTrustCodeChange,
                            label = { Text("Código de confiança") },
                            supportingText = {
                                Text("Confirme o código exibido no Windows")
                            },
                            singleLine = true,
                        )
                    }
                }
            }
        }

        ConnectionPill(
            status = status,
            modifier = Modifier.padding(horizontal = 4.dp),
        )
        statusMessage?.let { message ->
            Text(
                text = message,
                modifier = Modifier.semantics { liveRegion = LiveRegionMode.Polite },
                style = MaterialTheme.typography.bodyMedium,
                color = if (status == ConnectionStatus.ERROR) {
                    MaterialTheme.colorScheme.error
                } else {
                    MaterialTheme.colorScheme.onSurfaceVariant
                },
            )
        }
        if (status == ConnectionStatus.CONNECTING) {
            LinearProgressIndicator(modifier = Modifier.fillMaxWidth())
        }
        Button(
            modifier = Modifier.fillMaxWidth(),
            onClick = onConnect,
            enabled = canConnect && status != ConnectionStatus.CONNECTING,
        ) {
            Text(stringResource(R.string.pair_and_connect))
        }
        OutlinedButton(
            modifier = Modifier.fillMaxWidth(),
            onClick = onClearPairing,
            enabled = status != ConnectionStatus.CONNECTING,
        ) {
            Text(stringResource(R.string.clear_pairing))
        }
        revision?.let { currentRevision ->
            Text(
                text = stringResource(R.string.profile_revision, currentRevision),
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}