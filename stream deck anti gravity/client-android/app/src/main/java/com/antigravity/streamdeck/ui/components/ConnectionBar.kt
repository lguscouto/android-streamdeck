package com.antigravity.streamdeck.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.antigravity.streamdeck.data.network.ConnectionStatus
import com.antigravity.streamdeck.ui.theme.DeckTheme

@Composable
fun ConnectionBar(
    status: ConnectionStatus,
    serverIp: String,
    currentTheme: DeckTheme,
    onThemeChange: (DeckTheme) -> Unit,
    onConnectClick: (String) -> Unit,
    onQrClick: () -> Unit,
    modifier: Modifier = Modifier
) {
    var ipText by remember(serverIp) { mutableStateOf(serverIp) }
    var showThemeMenu by remember { mutableStateOf(false) }

    val statusColor = when (status) {
        ConnectionStatus.CONNECTED -> Color(0xFF00F0FF)
        ConnectionStatus.CONNECTING -> Color(0xFFF39C12)
        ConnectionStatus.DISCONNECTED -> Color(0xFFFF007F)
    }

    val statusText = when (status) {
        ConnectionStatus.CONNECTED -> "Online"
        ConnectionStatus.CONNECTING -> "Conectando..."
        ConnectionStatus.DISCONNECTED -> "Offline"
    }

    Surface(
        modifier = modifier
            .fillMaxWidth()
            .padding(10.dp),
        shape = RoundedCornerShape(14.dp),
        color = Color(0xCC161824)
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 14.dp, vertical = 8.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Box(
                    modifier = Modifier
                        .size(10.dp)
                        .clip(CircleShape)
                        .background(statusColor)
                )
                Spacer(modifier = Modifier.width(8.dp))
                Text(
                    text = statusText,
                    color = Color.White,
                    fontSize = 13.sp,
                    fontWeight = FontWeight.Bold
                )

                // Menu de Temas Visuais
                Box {
                    IconButton(onClick = { showThemeMenu = true }) {
                        Text("🎨", fontSize = 16.sp)
                    }
                    DropdownMenu(
                        expanded = showThemeMenu,
                        onDismissRequest = { showThemeMenu = false }
                    ) {
                        DropdownMenuItem(
                            text = { Text("Cyberpunk Neon") },
                            onClick = { onThemeChange(DeckTheme.CYBERPUNK); showThemeMenu = false }
                        )
                        DropdownMenuItem(
                            text = { Text("OLED Dark") },
                            onClick = { onThemeChange(DeckTheme.OLED_DARK); showThemeMenu = false }
                        )
                        DropdownMenuItem(
                            text = { Text("Glassmorphism") },
                            onClick = { onThemeChange(DeckTheme.GLASSMORPHISM); showThemeMenu = false }
                        )
                        DropdownMenuItem(
                            text = { Text("Nordic Slate") },
                            onClick = { onThemeChange(DeckTheme.NORDIC_SLATE); showThemeMenu = false }
                        )
                    }
                }
            }

            Row(verticalAlignment = Alignment.CenterVertically) {
                IconButton(
                    onClick = onQrClick,
                    modifier = Modifier.size(36.dp)
                ) {
                    Text("📷", fontSize = 16.sp)
                }
                Spacer(modifier = Modifier.width(4.dp))
                OutlinedTextField(
                    value = ipText,
                    onValueChange = { ipText = it },
                    singleLine = true,
                    modifier = Modifier.width(130.dp),
                    placeholder = { Text("10.0.2.2", fontSize = 11.sp) },
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedTextColor = Color.White,
                        unfocusedTextColor = Color.White,
                        focusedBorderColor = Color(0xFF00F0FF),
                        unfocusedBorderColor = Color(0xFF313244)
                    )
                )
                Spacer(modifier = Modifier.width(6.dp))
                Button(
                    onClick = { onConnectClick(ipText) },
                    colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF00F0FF))
                ) {
                    Text("OK", color = Color.Black, fontWeight = FontWeight.Bold, fontSize = 12.sp)
                }
            }
        }
    }
}
