package br.com.gustavo.streamdeck.network

import android.os.Handler
import android.os.Looper
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener
import org.json.JSONObject
import java.util.concurrent.TimeUnit

class PairingException(
    val code: String,
    message: String,
) : Exception(message)

data class PairingResult(
    val clientId: String,
    val accessToken: String,
)

class PairingClient(
    private val httpClient: OkHttpClient = OkHttpClient.Builder()
        .connectTimeout(5, TimeUnit.SECONDS)
        .readTimeout(5, TimeUnit.SECONDS)
        .build(),
) {
    suspend fun claim(
        endpoint: ServerEndpoint,
        clientId: String,
        clientVersion: String,
        pairingCode: String,
    ): PairingResult = withContext(Dispatchers.IO) {
        val payload = JSONObject()
            .put("client_id", clientId)
            .put("client_version", clientVersion)
            .put("pairing_code", pairingCode)
        val request = Request.Builder()
            .url(endpoint.pairingUrl)
            .post(payload.toString().toRequestBody(JSON_MEDIA_TYPE))
            .build()
        httpClient.newCall(request).execute().use { response ->
            val body = response.body?.string().orEmpty()
            if (!response.isSuccessful) {
                val error = runCatching { JSONObject(body) }.getOrNull()
                throw PairingException(
                    code = error?.optString("code").orEmpty().ifEmpty { "PAIRING_FAILED" },
                    message = error?.optString("message").orEmpty()
                        .ifEmpty { "Pairing failed" },
                )
            }
            val result = runCatching { JSONObject(body) }
                .getOrElse { throw PairingException("INVALID_RESPONSE", "Invalid pairing response") }
            val token = result.optString("access_token")
            if (token.isBlank()) {
                throw PairingException("INVALID_RESPONSE", "Pairing response has no token")
            }
            PairingResult(
                clientId = result.optString("client_id", clientId),
                accessToken = token,
            )
        }
    }

    suspend fun updateProfile(
        endpoint: ServerEndpoint,
        clientId: String,
        accessToken: String,
        profileId: String,
        expectedRevision: Int,
        profileWire: String,
    ): String = withContext(Dispatchers.IO) {
        require(clientId.isNotBlank()) { "client id is required" }
        require(accessToken.isNotBlank()) { "access token is required" }
        val request = Request.Builder()
            .url(endpoint.profileUpdateUrl(profileId, expectedRevision))
            .header("Authorization", "Bearer $accessToken")
            .header("X-StreamDeck-Client-Id", clientId)
            .put(profileWire.toRequestBody(JSON_MEDIA_TYPE))
            .build()
        httpClient.newCall(request).execute().use { response ->
            val body = response.body?.string().orEmpty()
            if (!response.isSuccessful) {
                val error = runCatching { JSONObject(body) }.getOrNull()
                throw PairingException(
                    code = error?.optString("code").orEmpty().ifEmpty { "PROFILE_UPDATE_FAILED" },
                    message = error?.optString("message").orEmpty()
                        .ifEmpty { "Profile update failed" },
                )
            }
            if (body.isBlank()) {
                throw PairingException("INVALID_RESPONSE", "Profile update response is empty")
            }
            return@use body
        }
    }

    companion object {
        private val JSON_MEDIA_TYPE = "application/json".toMediaType()
    }
}

interface StreamDeckSocketListener {
    fun onConnected() {}
    fun onMessage(type: String, rawMessage: String) {}
    fun onClosed() {}
    fun onFailure(message: String) {}
}

class StreamDeckWebSocketClient(
    private val httpClient: OkHttpClient = OkHttpClient.Builder()
        .readTimeout(0, TimeUnit.MILLISECONDS)
        .build(),
    private val callbackHandler: Handler = Handler(Looper.getMainLooper()),
) {
    fun connect(
        endpoint: ServerEndpoint,
        clientId: String,
        clientVersion: String,
        accessToken: String,
        listener: StreamDeckSocketListener,
    ): WebSocket {
        val request = Request.Builder()
            .url(endpoint.websocketUrl)
            .build()
        return httpClient.newWebSocket(
            request,
            object : WebSocketListener() {
                override fun onOpen(webSocket: WebSocket, response: Response) {
                    webSocket.send(
                        ProtocolMessages.hello(
                            clientId = clientId,
                            clientVersion = clientVersion,
                            accessToken = accessToken,
                        ),
                    )
                    dispatch { listener.onConnected() }
                }

                override fun onMessage(webSocket: WebSocket, text: String) {
                    val type = ProtocolMessages.messageType(text)
                    if (type == null) {
                        dispatch { listener.onFailure("Mensagem do servidor inválida") }
                    } else {
                        dispatch { listener.onMessage(type, text) }
                    }
                }

                override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                    dispatch { listener.onClosed() }
                }

                override fun onFailure(
                    webSocket: WebSocket,
                    t: Throwable,
                    response: Response?,
                ) {
                    dispatch {
                        listener.onFailure(t.message ?: "Falha de conexão")
                    }
                }
            },
        )
    }

    private fun dispatch(action: () -> Unit) {
        callbackHandler.post(action)
    }
}
