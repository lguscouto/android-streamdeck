package br.com.gustavo.streamdeck.ui.deck

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
fun ConnectedDeckScreen(
    snapshot: StreamDeckProfileSnapshot,
    connectionStatus: ConnectionStatus,
    statusMessage: String?,
    buttonStates: Map<String, ButtonExecutionState>,
    density: DeckDensity,
    reduceMotion: Boolean,
    hapticsEnabled: Boolean,
    onButtonPress: (StreamDeckButton) -> Unit,
    onPageSelected: (StreamDeckPage) -> Unit,
    pageSwitching: Boolean,
    onEditProfile: () -> Unit,
    onManageProfiles: () -> Unit,
    onOpenSettings: () -> Unit,
    onClearPairing: () -> Unit,
) {
    var menuExpanded by remember { mutableStateOf(false) }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(horizontal = 8.dp, vertical = 6.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = androidx.compose.ui.Alignment.CenterVertically,
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = snapshot.profileName,
                    maxLines = 1,
                    style = MaterialTheme.typography.titleLarge,
                )
                Text(
                    text = "${snapshot.activePage.title}  ·  r${snapshot.revision}",
                    maxLines = 1,
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            ConnectionPill(status = connectionStatus)
            Box {
                IconButton(onClick = { menuExpanded = true }) {
                    Icon(
                        imageVector = Icons.Outlined.MoreVert,
                        contentDescription = "Abrir ações do deck",
                    )
                }
                DropdownMenu(
                    expanded = menuExpanded,
                    onDismissRequest = { menuExpanded = false },
                ) {
                    DropdownMenuItem(
                        text = { Text("Editar deck") },
                        leadingIcon = {
                            Icon(Icons.Outlined.Edit, contentDescription = null)
                        },
                        onClick = {
                            menuExpanded = false
                            onEditProfile()
                        },
                    )
                    DropdownMenuItem(
                        text = { Text("Gerenciar perfis") },
                        leadingIcon = {
                            Icon(Icons.Outlined.Build, contentDescription = null)
                        },
                        onClick = {
                            menuExpanded = false
                            onManageProfiles()
                        },
                    )
                    DropdownMenuItem(
                        text = { Text("Configurações") },
                        leadingIcon = {
                            Icon(Icons.Outlined.Settings, contentDescription = null)
                        },
                        onClick = {
                            menuExpanded = false
                            onOpenSettings()
                        },
                    )
                    DropdownMenuItem(
                        text = { Text(stringResource(R.string.clear_pairing)) },
                        leadingIcon = {
                            Icon(Icons.Outlined.LinkOff, contentDescription = null)
                        },
                        onClick = {
                            menuExpanded = false
                            onClearPairing()
                        },
                    )
                }
            }
        }
        statusMessage?.let { message ->
            Text(
                text = message,
                modifier = Modifier.semantics { liveRegion = LiveRegionMode.Polite },
                maxLines = 1,
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
        PagePager(
            pages = snapshot.pages,
            activePageId = snapshot.activePage.id,
            enabled = connectionStatus == ConnectionStatus.CONNECTED && !pageSwitching,
            onPageSelected = onPageSelected,
        )
        StreamDeckGrid(
            page = snapshot.activePage,
            buttonStates = buttonStates,
            onButtonPress = onButtonPress,
            density = density,
            reduceMotion = reduceMotion,
            hapticsEnabled = hapticsEnabled,
            modifier = Modifier
                .fillMaxWidth()
                .weight(1f),
        )
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
