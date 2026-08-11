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
import org.json.JSONArray
import org.json.JSONObject
import java.time.Instant
import java.util.concurrent.TimeUnit

class PairingException(
    val code: String,
    message: String,
) : Exception(message)

data class RemoteProfileSummary(
    val profileId: String,
    val profileName: String,
    val revision: Int,
    val activePageId: String,
    val isActive: Boolean,
)

data class PairingResult(
    val clientId: String,
    val accessToken: String,
    val tlsTrust: TlsTrust? = null,
)

data class PairingBootstrapResult(
    val bundle: PairingBootstrap,
    val tlsTrust: TlsTrust,
)

private data class VerifiedPairingBootstrap(
    val bundle: PairingBootstrap,
    val pairingKey: ByteArray,
    val tlsTrust: TlsTrust,
)

class PairingClient(
    private var httpClient: OkHttpClient? = null,
    private val bootstrapClientFactory: (() -> OkHttpClient)? = null,
) {
    fun configureTlsTrust(tlsTrust: TlsTrust) {
        httpClient = tlsTrust.newHttpClient()
    }

    suspend fun bootstrap(
        endpoint: ServerEndpoint,
        sessionId: String,
        pairingSecret: String,
        now: Instant = Instant.now(),
    ): PairingBootstrapResult {
        val verified = bootstrapVerified(endpoint, sessionId, pairingSecret, now)
        return try {
            PairingBootstrapResult(verified.bundle, verified.tlsTrust)
        } finally {
            verified.pairingKey.fill(0)
        }
    }

    private suspend fun bootstrapVerified(
        endpoint: ServerEndpoint,
        sessionId: String,
        pairingSecret: String,
        now: Instant,
    ): VerifiedPairingBootstrap = withContext(Dispatchers.IO) {
        var pairingKey = ByteArray(0)
        try {
        val normalizedSecret = runCatching { PairingProof.normalizeSecret(pairingSecret) }
            .getOrElse {
                throw PairingException("PAIRING_SECRET_INVALID", "Pairing secret is invalid")
            }
        val request = Request.Builder()
            .url(endpoint.pairingBootstrapUrl(sessionId))
            .get()
            .build()
        val bootstrapClient = bootstrapClientFactory?.invoke() ?: BootstrapTls.newClient()
        bootstrapClient.newCall(request).execute().use { response ->
            val body = response.body?.string().orEmpty()
            if (!response.isSuccessful) {
                throw safeApiException(
                    body,
                    "PAIRING_BOOTSTRAP_FAILED",
                    "Pairing bootstrap failed",
                )
            }
            val bundle = parseBootstrap(body)
            require(bundle.sessionId == sessionId) {
                "bootstrap session does not match request"
            }
            require(bundle.serverIp == endpoint.serverHost) {
                "bootstrap server address does not match endpoint"
            }
            require(bundle.port == endpoint.serverPort) {
                "bootstrap server port does not match endpoint"
            }
            PairingInput.requirePort(bundle.port)
            val expiresAt = runCatching { Instant.parse(bundle.expiresAt) }
                .getOrElse {
                    throw PairingException("PAIRING_BOOTSTRAP_INVALID", "Bootstrap expiry is invalid")
                }
            if (!expiresAt.isAfter(now)) {
                throw PairingException("PAIRING_EXPIRED", "Pairing session expired")
            }
            pairingKey = runCatching {
                PairingProof.derivePairingKey(normalizedSecret, bundle.salt)
            }.getOrElse {
                throw PairingException("PAIRING_BOOTSTRAP_INVALID", "Bootstrap proof is invalid")
            }
            val proofValid = runCatching {
                PairingProof.verifyServerProof(bundle, pairingKey)
            }.getOrDefault(false)
            if (!proofValid) {
                throw PairingException("PAIRING_PROOF_INVALID", "Pairing proof is invalid")
            }
            val tlsTrust = runCatching { TlsTrust.fromVerifiedPem(bundle.caCertificatePem) }
                .getOrElse {
                    throw PairingException("TLS_CA_INVALID", "Server CA is invalid")
                }
            httpClient = tlsTrust.newHttpClient()
            VerifiedPairingBootstrap(bundle, pairingKey, tlsTrust)
        }
        } catch (error: Throwable) {
            pairingKey.fill(0)
            throw error
        }
    }

    suspend fun bootstrapAndClaim(
        endpoint: ServerEndpoint,
        sessionId: String,
        pairingSecret: String,
        clientId: String,
        clientVersion: String,
        now: Instant = Instant.now(),
    ): PairingResult {
        val bootstrapResult = bootstrapVerified(endpoint, sessionId, pairingSecret, now)
        return try {
            claimWithProof(
                endpoint = endpoint,
                clientId = clientId,
                clientVersion = clientVersion,
                sessionId = sessionId,
                pairingKey = bootstrapResult.pairingKey,
            ).copy(tlsTrust = bootstrapResult.tlsTrust)
        } finally {
            bootstrapResult.pairingKey.fill(0)
        }
    }

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
        postClaim(endpoint, payload, clientId)
    }

    private suspend fun claimWithProof(
        endpoint: ServerEndpoint,
        clientId: String,
        clientVersion: String,
        sessionId: String,
        pairingKey: ByteArray,
    ): PairingResult = withContext(Dispatchers.IO) {
        val payload = JSONObject()
            .put("client_id", clientId)
            .put("client_version", clientVersion)
            .put(
                "session_id",
                sessionId,
            )
            .put(
                "client_proof",
                PairingProof.clientProof(pairingKey, sessionId, clientId, clientVersion),
            )
        postClaim(endpoint, payload, clientId)
    }

    private fun postClaim(
        endpoint: ServerEndpoint,
        payload: JSONObject,
        fallbackClientId: String,
    ): PairingResult {
        val request = Request.Builder()
            .url(endpoint.pairingUrl)
            .post(payload.toString().toRequestBody(JSON_MEDIA_TYPE))
            .build()
        return secureHttpClient().newCall(request).execute().use { response ->
            val body = response.body?.string().orEmpty()
            if (!response.isSuccessful) {
                throw safeApiException(body, "PAIRING_FAILED", "Pairing failed")
            }
            val result = runCatching { JSONObject(body) }
                .getOrElse { throw PairingException("INVALID_RESPONSE", "Invalid pairing response") }
            val token = result.optString("access_token")
            if (token.isBlank()) {
                throw PairingException("INVALID_RESPONSE", "Pairing response has no token")
            }
            PairingResult(
                clientId = result.optString("client_id", fallbackClientId),
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
        secureHttpClient().newCall(request).execute().use { response ->
            val body = response.body?.string().orEmpty()
            if (!response.isSuccessful) {
                throw safeApiException(body, "PROFILE_UPDATE_FAILED", "Profile update failed")
            }
            if (body.isBlank()) {
                throw PairingException("INVALID_RESPONSE", "Profile update response is empty")
            }
            return@use body
        }
    }

    suspend fun listProfiles(
        endpoint: ServerEndpoint,
        clientId: String,
        accessToken: String,
    ): List<RemoteProfileSummary> = authenticatedRequest(
        request(endpoint.profilesUrl(), clientId, accessToken, "GET"),
        fallback = "Profile list failed",
    ).let { body ->
        val profiles = runCatching { JSONObject(body).getJSONArray("profiles") }
            .getOrElse { throw PairingException("INVALID_RESPONSE", "Invalid profile list") }
        buildList {
            for (index in 0 until profiles.length()) {
                val profile = profiles.getJSONObject(index)
                add(
                    RemoteProfileSummary(
                        profileId = profile.optString("id").requireNonBlank("profile id"),
                        profileName = profile.optString("name").requireNonBlank("profile name"),
                        revision = profile.optInt("revision").also {
                            require(it >= 1) { "Profile revision must be positive" }
                        },
                        activePageId = profile.optString("active_page_id")
                            .requireNonBlank("active page id"),
                        isActive = profile.optBoolean("is_active"),
                    ),
                )
            }
        }
    }

    suspend fun getProfile(
        endpoint: ServerEndpoint,
        clientId: String,
        accessToken: String,
        profileId: String,
    ): String = authenticatedRequest(
        request(endpoint.profileUrl(profileId), clientId, accessToken, "GET"),
        fallback = "Profile load failed",
    )

    suspend fun createProfile(
        endpoint: ServerEndpoint,
        clientId: String,
        accessToken: String,
        expectedRevision: Int,
        profileWire: String,
    ): String = authenticatedRequest(
        request(
            url = endpoint.profilesCreateUrl(expectedRevision),
            clientId = clientId,
            accessToken = accessToken,
            method = "POST",
            body = profileWire,
        ),
        fallback = "Profile creation failed",
    )

    suspend fun renameProfile(
        endpoint: ServerEndpoint,
        clientId: String,
        accessToken: String,
        profileId: String,
        expectedRevision: Int,
        name: String,
    ): String = authenticatedRequest(
        request(
            endpoint.profileRenameUrl(profileId, expectedRevision),
            clientId,
            accessToken,
            "PATCH",
            JSONObject().put("name", name.trim()).toString(),
        ),
        fallback = "Profile rename failed",
    )

    suspend fun duplicateProfile(
        endpoint: ServerEndpoint,
        clientId: String,
        accessToken: String,
        profileId: String,
        expectedRevision: Int,
        newProfileId: String,
        newProfileName: String? = null,
    ): String {
        val payload = JSONObject().put("id", newProfileId)
        newProfileName?.trim()?.takeIf { it.isNotEmpty() }?.let { payload.put("name", it) }
        return authenticatedRequest(
            request(
                endpoint.profileDuplicateUrl(profileId, expectedRevision),
                clientId,
                accessToken,
                "POST",
                payload.toString(),
            ),
            fallback = "Profile duplication failed",
        )
    }

    suspend fun activateProfile(
        endpoint: ServerEndpoint,
        clientId: String,
        accessToken: String,
        profileId: String,
        expectedRevision: Int,
    ): String = authenticatedRequest(
        request(endpoint.profileActivateUrl(profileId, expectedRevision), clientId, accessToken, "POST"),
        fallback = "Profile activation failed",
    )

    suspend fun deleteProfile(
        endpoint: ServerEndpoint,
        clientId: String,
        accessToken: String,
        profileId: String,
        expectedRevision: Int,
        replacementProfileId: String? = null,
    ): String = authenticatedRequest(
        request(
            endpoint.profileDeleteUrl(profileId, expectedRevision, replacementProfileId),
            clientId,
            accessToken,
            "DELETE",
        ),
        fallback = "Profile deletion failed",
    )

    suspend fun createPage(
        endpoint: ServerEndpoint,
        clientId: String,
        accessToken: String,
        profileId: String,
        expectedRevision: Int,
        pageWire: String,
    ): String = authenticatedRequest(
        request(
            endpoint.profilePagesUrl(profileId, expectedRevision),
            clientId,
            accessToken,
            "POST",
            pageWire,
        ),
        fallback = "Page creation failed",
    )

    suspend fun createPage(
        endpoint: ServerEndpoint,
        clientId: String,
        accessToken: String,
        profileId: String,
        expectedRevision: Int,
        page: StreamDeckPage,
    ): String = createPage(
        endpoint = endpoint,
        clientId = clientId,
        accessToken = accessToken,
        profileId = profileId,
        expectedRevision = expectedRevision,
        pageWire = page.toWire(),
    )

    suspend fun renamePage(
        endpoint: ServerEndpoint,
        clientId: String,
        accessToken: String,
        profileId: String,
        pageId: String,
        expectedRevision: Int,
        title: String,
    ): String = authenticatedRequest(
        request(
            endpoint.pageRenameUrl(profileId, pageId, expectedRevision),
            clientId,
            accessToken,
            "PATCH",
            JSONObject().put("title", title.trim()).toString(),
        ),
        fallback = "Page rename failed",
    )

    suspend fun reorderPage(
        endpoint: ServerEndpoint,
        clientId: String,
        accessToken: String,
        profileId: String,
        pageId: String,
        expectedRevision: Int,
        order: Int,
    ): String = authenticatedRequest(
        request(
            endpoint.pageReorderUrl(profileId, pageId, expectedRevision),
            clientId,
            accessToken,
            "POST",
            JSONObject().put("order", order).toString(),
        ),
        fallback = "Page reorder failed",
    )

    suspend fun deletePage(
        endpoint: ServerEndpoint,
        clientId: String,
        accessToken: String,
        profileId: String,
        pageId: String,
        expectedRevision: Int,
        replacementPageId: String? = null,
    ): String = authenticatedRequest(
        request(
            endpoint.pageDeleteUrl(profileId, pageId, expectedRevision, replacementPageId),
            clientId,
            accessToken,
            "DELETE",
        ),
        fallback = "Page deletion failed",
    )

    suspend fun exportProfileJson(
        endpoint: ServerEndpoint,
        clientId: String,
        accessToken: String,
        profileId: String,
    ): String = authenticatedRequest(
        request(endpoint.profileExportUrl(profileId), clientId, accessToken, "GET"),
        fallback = "Profile export failed",
    )

    suspend fun importProfileJson(
        endpoint: ServerEndpoint,
        clientId: String,
        accessToken: String,
        expectedRevision: Int,
        profileJson: String,
    ): String = authenticatedRequest(
        request(
            endpoint.profileImportUrl(expectedRevision),
            clientId,
            accessToken,
            "POST",
            profileJson,
        ),
        fallback = "Profile import failed",
    )

    private fun secureHttpClient(): OkHttpClient = httpClient
        ?: throw PairingException(
            "TLS_TRUST_REQUIRED",
            "Private CA trust must be configured before connecting",
        )

    private fun request(
        url: String,
        clientId: String,
        accessToken: String,
        method: String,
        body: String? = null,
    ): Request {
        require(clientId.isNotBlank()) { "client id is required" }
        require(accessToken.isNotBlank()) { "access token is required" }
        require(method in setOf("GET", "POST", "PATCH", "PUT", "DELETE")) {
            "unsupported HTTP method"
        }
        val builder = Request.Builder()
            .url(url)
            .header("Authorization", "Bearer $accessToken")
            .header("X-StreamDeck-Client-Id", clientId)
        when (method) {
            "GET" -> builder.get()
            "POST" -> builder.post((body ?: "{}").toRequestBody(JSON_MEDIA_TYPE))
            "PATCH" -> builder.patch((body ?: "{}").toRequestBody(JSON_MEDIA_TYPE))
            "PUT" -> builder.put((body ?: "{}").toRequestBody(JSON_MEDIA_TYPE))
            "DELETE" -> builder.delete(body?.toRequestBody(JSON_MEDIA_TYPE))
        }
        return builder.build()
    }

    private suspend fun authenticatedRequest(request: Request, fallback: String): String =
        withContext(Dispatchers.IO) {
            secureHttpClient().newCall(request).execute().use { response ->
                val body = response.body?.string().orEmpty()
                if (!response.isSuccessful) {
                    throw safeApiException(body, "HTTP_${response.code}", fallback)
                }
                if (body.isBlank()) {
                    throw PairingException("INVALID_RESPONSE", "Empty server response")
                }
                body
            }
        }

    private fun String.requireNonBlank(label: String): String = trim().also {
        require(it.isNotEmpty()) { "$label is missing" }
    }

    private fun StreamDeckPage.toWire(): String {
        val buttons = JSONArray()
        this.buttons.forEach { button ->
            val action = button.action
                ?: throw IllegalArgumentException("Button action is missing")
            val wireButton = JSONObject()
                .put("id", button.id)
                .put("row", button.row)
                .put("column", button.column)
                .put("title", button.title)
                .put("action", action.toJson())
            button.icon?.let { wireButton.put("icon", it) }
            button.color?.let { wireButton.put("color", it) }
            buttons.put(wireButton)
        }
        return JSONObject()
            .put("id", id)
            .put("title", title)
            .put("order", order)
            .put("rows", rows)
            .put("columns", columns)
            .put("buttons", buttons)
            .toString()
    }

    companion object {
        private val JSON_MEDIA_TYPE = "application/json".toMediaType()

        private fun parseBootstrap(body: String): PairingBootstrap {
            return runCatching {
                val json = JSONObject(body)
                PairingBootstrap(
                    version = json.getInt("version"),
                    sessionId = json.getString("session_id"),
                    salt = json.getString("salt"),
                    expiresAt = json.getString("expires_at"),
                    serverIp = json.getString("server_ip"),
                    port = json.getInt("port"),
                    caCertificatePem = json.getString("ca_certificate_pem"),
                    serverProof = json.getString("server_proof"),
                )
            }.getOrElse {
                throw PairingException("PAIRING_BOOTSTRAP_INVALID", "Bootstrap response is invalid")
            }
        }

        private fun safeApiException(
            body: String,
            fallbackCode: String,
            fallbackMessage: String,
        ): PairingException {
            val code = runCatching { JSONObject(body).optString("code") }
                .getOrNull()
                ?.takeIf { it.matches(Regex("^[A-Z][A-Z0-9_]{2,63}$")) }
                ?: fallbackCode
            val message = when (code) {
                "PROFILE_REVISION_CONFLICT" -> "Profile revision conflict"
                "PROFILE_DELETE_PROTECTED" -> "Profile deletion requires a replacement"
                "PAGE_DELETE_PROTECTED" -> "Page deletion requires a replacement"
                "AUTH_REQUIRED" -> "Authentication required"
                "PAIRING_CODE_INVALID" -> "Pairing code is invalid"
                "PAIRING_EXPIRED" -> "Pairing session expired"
                "PAIRING_USED" -> "Pairing session already used"
                "PAIRING_PROOF_INVALID" -> "Pairing proof is invalid"
                "PAIRING_SESSION_INVALID" -> "Pairing session is invalid"
                "PAIRING_BOOTSTRAP_INVALID" -> "Pairing bootstrap is invalid"
                "TLS_CA_INVALID" -> "Server CA is invalid"
                "VALIDATION_ERROR" -> "Request validation failed"
                else -> fallbackMessage
            }
            return PairingException(code, message)
        }
    }
}

interface StreamDeckSocketListener {
    fun onConnected() {}
    fun onMessage(type: String, rawMessage: String) {}
    fun onClosed() {}
    fun onFailure(message: String) {}
}

class StreamDeckWebSocketClient(
    private var httpClient: OkHttpClient? = null,
    private val callbackHandler: Handler = Handler(Looper.getMainLooper()),
) {
    fun configureTlsTrust(tlsTrust: TlsTrust) {
        httpClient = tlsTrust.newHttpClient(readTimeoutSeconds = 0)
    }

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
        return secureHttpClient().newWebSocket(
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

    private fun secureHttpClient(): OkHttpClient = httpClient
        ?: throw PairingException(
            "TLS_TRUST_REQUIRED",
            "Private CA trust must be configured before connecting",
        )

    private fun dispatch(action: () -> Unit) {
        callbackHandler.post(action)
    }
}
