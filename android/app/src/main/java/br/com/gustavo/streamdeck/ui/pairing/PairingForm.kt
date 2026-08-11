package br.com.gustavo.streamdeck.ui.pairing

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import br.com.gustavo.streamdeck.R
import br.com.gustavo.streamdeck.ui.components.ConnectionPill
import br.com.gustavo.streamdeck.ui.components.ConnectionStatus

@Composable
fun PairingForm(
    serverAddress: String,
    onServerAddressChange: (String) -> Unit,
    pairingSecret: String,
    onPairingSecretChange: (String) -> Unit,
    hasStoredAccessToken: Boolean,
    onScanQr: () -> Unit,
    onConnect: () -> Unit,
    onClearPairing: () -> Unit,
    status: ConnectionStatus,
    statusMessage: String?,
) {
    val canConnect = serverAddress.isNotBlank() &&
        (pairingSecret.isNotBlank() || hasStoredAccessToken)

    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(horizontal = 16.dp, vertical = 20.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        Card(
            modifier = Modifier.fillMaxWidth(),
            colors = CardDefaults.cardColors(
                containerColor = MaterialTheme.colorScheme.surface,
            ),
        ) {
            Column(
                modifier = Modifier.padding(20.dp),
                verticalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                Text(
                    text = "PAREAR DISPOSITIVO",
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.primary,
                )
                Text(
                    text = "Conectar ao servidor Windows",
                    style = MaterialTheme.typography.headlineSmall,
                )
                Text(
                    text = "Use o IP exibido na janela de pareamento e a senha temporária. A porta e os dados de segurança são internos.",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                OutlinedTextField(
                    modifier = Modifier.fillMaxWidth(),
                    value = serverAddress,
                    onValueChange = onServerAddressChange,
                    label = { Text("IP do servidor") },
                    supportingText = { Text("Ex.: 192.168.100.20") },
                    singleLine = true,
                )
                OutlinedTextField(
                    modifier = Modifier.fillMaxWidth(),
                    value = pairingSecret,
                    onValueChange = onPairingSecretChange,
                    label = { Text("Senha temporária") },
                    supportingText = {
                        Text("A senha expira após alguns minutos e só pode ser usada uma vez")
                    },
                    visualTransformation = PasswordVisualTransformation(),
                    singleLine = true,
                )
                OutlinedButton(
                    modifier = Modifier.fillMaxWidth(),
                    onClick = onScanQr,
                    enabled = status != ConnectionStatus.CONNECTING,
                ) {
                    Text("Ler QR code")
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
            Text(if (hasStoredAccessToken && pairingSecret.isBlank()) "Reconectar" else "Parear e conectar")
        }
        OutlinedButton(
            modifier = Modifier.fillMaxWidth(),
            onClick = onClearPairing,
            enabled = status != ConnectionStatus.CONNECTING,
        ) {
            Text("Limpar pareamento")
        }
    }
}
