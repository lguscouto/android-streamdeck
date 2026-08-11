package com.antigravity.streamdeck.data.network

import android.util.Log
import com.antigravity.streamdeck.data.model.*
import com.google.gson.Gson
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import okhttp3.*
import java.util.concurrent.TimeUnit

enum class ConnectionStatus {
    DISCONNECTED,
    CONNECTING,
    CONNECTED
}

class WebSocketManager(private val gson: Gson = Gson()) {

    private val client = OkHttpClient.Builder()
        .readTimeout(10, TimeUnit.SECONDS)
        .writeTimeout(10, TimeUnit.SECONDS)
        .build()

    private var webSocket: WebSocket? = null

    private val _connectionStatus = MutableStateFlow(ConnectionStatus.DISCONNECTED)
    val connectionStatus: StateFlow<ConnectionStatus> = _connectionStatus

    private val _gridData = MutableStateFlow<GridSyncPayload?>(null)
    val gridData: StateFlow<GridSyncPayload?> = _gridData

    private val _hardwareMetrics = MutableStateFlow<HardwareMetricsPayload?>(null)
    val hardwareMetrics: StateFlow<HardwareMetricsPayload?> = _hardwareMetrics

    private val _spotifyTrack = MutableStateFlow<SpotifyTrackPayload?>(null)
    val spotifyTrack: StateFlow<SpotifyTrackPayload?> = _spotifyTrack

    private var currentServerIp: String = "10.0.2.2"
    private var currentPort: Int = 5001
    private var pingJob: Job? = null
    private val scope = CoroutineScope(Dispatchers.IO + SupervisorJob())

    fun connect(serverIp: String, port: Int = 5001) {
        currentServerIp = serverIp
        currentPort = port

        if (_connectionStatus.value == ConnectionStatus.CONNECTED || _connectionStatus.value == ConnectionStatus.CONNECTING) {
            disconnect()
        }

        _connectionStatus.value = ConnectionStatus.CONNECTING

        val request = Request.Builder()
            .url("ws://$serverIp:$port")
            .build()

        webSocket = client.newWebSocket(request, object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) {
                Log.d("WebSocketManager", "Conectado ao servidor Stream Deck!")
                _connectionStatus.value = ConnectionStatus.CONNECTED
                startPingLoop()
            }

            override fun onMessage(webSocket: WebSocket, text: String) {
                handleIncomingMessage(text)
            }

            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                Log.e("WebSocketManager", "Falha na conexão WebSocket: ${t.message}")
                _connectionStatus.value = ConnectionStatus.DISCONNECTED
                stopPingLoop()
            }

            override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                Log.d("WebSocketManager", "Conexão fechada: $reason")
                _connectionStatus.value = ConnectionStatus.DISCONNECTED
                stopPingLoop()
            }
        })
    }

    fun disconnect() {
        stopPingLoop()
        webSocket?.close(1000, "Desconectado pelo usuário")
        webSocket = null
        _connectionStatus.value = ConnectionStatus.DISCONNECTED
    }

    fun pressButton(button: ButtonModel) {
        val grid = _gridData.value ?: return
        val payload = PressButtonPayload(
            profileId = grid.activeProfileId,
            pageIndex = grid.activePageIndex,
            row = button.row,
            col = button.col,
            buttonId = button.id,
            actionType = button.actionType
        )

        val message = WebSocketMessage(
            event = EventTypes.PRESS_BUTTON,
            payload = payload
        )

        sendJson(message)
    }

    private fun sendJson(data: Any) {
        val json = gson.toJson(data)
        webSocket?.send(json)
    }

    private fun handleIncomingMessage(text: String) {
        try {
            val baseMessage = gson.fromJson(text, Map::class.java)
            val event = baseMessage["event"] as? String ?: return

            when (event) {
                EventTypes.GRID_SYNC -> {
                    val payloadJson = gson.toJson(baseMessage["payload"])
                    val gridSync = gson.fromJson(payloadJson, GridSyncPayload::class.java)
                    _gridData.value = gridSync
                }

                EventTypes.BUTTON_STATE_CHANGE -> {
                    val payloadJson = gson.toJson(baseMessage["payload"])
                    val stateChange = gson.fromJson(payloadJson, ButtonStateChangePayload::class.java)
                    updateButtonStateLocally(stateChange.buttonId, stateChange.newState)
                }

                EventTypes.HARDWARE_SYNC -> {
                    val payloadJson = gson.toJson(baseMessage["payload"])
                    val metrics = gson.fromJson(payloadJson, HardwareMetricsPayload::class.java)
                    _hardwareMetrics.value = metrics
                    updateHardwareButtonsLocally(metrics)
                }

                EventTypes.SPOTIFY_SYNC -> {
                    val payloadJson = gson.toJson(baseMessage["payload"])
                    val track = gson.fromJson(payloadJson, SpotifyTrackPayload::class.java)
                    _spotifyTrack.value = track
                    updateSpotifyButtonsLocally(track)
                }
            }
        } catch (e: Exception) {
            Log.e("WebSocketManager", "Erro ao parsear mensagem WebSocket: ${e.message}")
        }
    }

    private fun updateButtonStateLocally(buttonId: String, newState: String) {
        val currentGrid = _gridData.value ?: return
        val updatedButtons = currentGrid.buttons.map { button ->
            if (button.id == buttonId) {
                button.copy(state = newState)
            } else {
                button
            }
        }
        _gridData.value = currentGrid.copy(buttons = updatedButtons)
    }

    private fun updateHardwareButtonsLocally(metrics: HardwareMetricsPayload) {
        val currentGrid = _gridData.value ?: return
        val updatedButtons = currentGrid.buttons.map { button ->
            when (button.actionType) {
                "HW_CPU" -> button.copy(label = "CPU: ${metrics.cpuUsage}%\n${metrics.cpuTemp}°C")
                "HW_RAM" -> button.copy(label = "RAM: ${metrics.ramUsage}%\n${metrics.ramUsedGb}/${metrics.ramTotalGb}GB")
                "HW_GPU" -> button.copy(label = "GPU: ${metrics.gpuUsage}%")
                else -> button
            }
        }
        _gridData.value = currentGrid.copy(buttons = updatedButtons)
    }

    private fun updateSpotifyButtonsLocally(track: SpotifyTrackPayload) {
        val currentGrid = _gridData.value ?: return
        val updatedButtons = currentGrid.buttons.map { button ->
            if (button.actionType == "SPOTIFY_TRACK") {
                val labelText = if (track.isPlaying) "${track.title}\n${track.artist}" else "Spotify Pausado"
                button.copy(label = labelText)
            } else {
                button
            }
        }
        _gridData.value = currentGrid.copy(buttons = updatedButtons)
    }

    private fun startPingLoop() {
        stopPingLoop()
        pingJob = scope.launch {
            while (isActive) {
                delay(10000)
                val ping = WebSocketMessage(
                    event = EventTypes.PING,
                    payload = mapOf("timestamp" to System.currentTimeMillis())
                )
                sendJson(ping)
            }
        }
    }

    private fun stopPingLoop() {
        pingJob?.cancel()
        pingJob = null
    }
}
