package com.antigravity.streamdeck

import android.Manifest
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.os.VibrationEffect
import android.os.Vibrator
import android.os.VibratorManager
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.core.content.ContextCompat
import com.antigravity.streamdeck.data.network.WebSocketManager
import com.antigravity.streamdeck.ui.components.ConnectionBar
import com.antigravity.streamdeck.ui.components.DeckGrid
import com.antigravity.streamdeck.ui.components.QrScannerDialog
import com.antigravity.streamdeck.ui.theme.AntiGravityTheme
import com.antigravity.streamdeck.ui.theme.DeckTheme

class MainActivity : ComponentActivity() {

    private val webSocketManager = WebSocketManager()
    private val showScannerDialog = mutableStateOf(false)

    private val requestCameraPermission = registerForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { isGranted ->
        if (isGranted) {
            showScannerDialog.value = true
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        setContent {
            var currentTheme by remember { mutableStateOf(DeckTheme.CYBERPUNK) }
            val status by webSocketManager.connectionStatus.collectAsState()
            val gridSync by webSocketManager.gridData.collectAsState()
            var serverIp by remember { mutableStateOf("10.0.2.2") }

            LaunchedEffect(Unit) {
                webSocketManager.connect("10.0.2.2")
            }

            AntiGravityTheme(theme = currentTheme) {
                Surface(
                    modifier = Modifier
                        .fillMaxSize()
                        .background(Color(0xFF0D0E15)),
                    color = Color(0xFF0D0E15)
                ) {
                    Column(modifier = Modifier.fillMaxSize()) {
                        ConnectionBar(
                            status = status,
                            serverIp = serverIp,
                            currentTheme = currentTheme,
                            onThemeChange = { selectedTheme -> currentTheme = selectedTheme },
                            onConnectClick = { newIp ->
                                serverIp = newIp
                                webSocketManager.connect(newIp)
                            },
                            onQrClick = {
                                if (ContextCompat.checkSelfPermission(this@MainActivity, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED) {
                                    showScannerDialog.value = true
                                } else {
                                    requestCameraPermission.launch(Manifest.permission.CAMERA)
                                }
                            }
                        )

                        if (gridSync != null) {
                            DeckGrid(
                                gridConfig = gridSync!!.gridConfig,
                                buttons = gridSync!!.buttons,
                                serverIp = serverIp,
                                onButtonClick = { button ->
                                    triggerHapticFeedback()
                                    webSocketManager.pressButton(button)
                                },
                                modifier = Modifier.weight(1f)
                            )
                        } else {
                            Box(
                                modifier = Modifier
                                    .fillMaxSize()
                                    .weight(1f)
                            )
                        }

                        if (showScannerDialog.value) {
                            QrScannerDialog(
                                onQrScanned = { scannedIp, port ->
                                    showScannerDialog.value = false
                                    serverIp = scannedIp
                                    webSocketManager.connect(scannedIp, port)
                                },
                                onDismissRequest = {
                                    showScannerDialog.value = false
                                }
                            )
                        }
                    }
                }
            }
        }
    }

    private fun triggerHapticFeedback() {
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                val vibratorManager = getSystemService(VibratorManager::class.java)
                val vibrator = vibratorManager.defaultVibrator
                vibrator.vibrate(VibrationEffect.createOneShot(30, VibrationEffect.DEFAULT_AMPLITUDE))
            } else {
                @Suppress("DEPRECATION")
                val vibrator = getSystemService(Vibrator::class.java)
                vibrator?.vibrate(30)
            }
        } catch (_: Exception) {}
    }

    override fun onDestroy() {
        super.onDestroy()
        webSocketManager.disconnect()
    }
}
