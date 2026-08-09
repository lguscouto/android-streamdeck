package br.com.gustavo.streamdeck.network

import org.json.JSONObject
import org.json.JSONArray

object ProtocolMessages {
    fun hello(
        clientId: String,
        clientVersion: String,
        accessToken: String,
    ): String = JSONObject()
        .put("protocol_version", 1)
        .put("type", "hello")
        .put(
            "payload",
            JSONObject()
                .put("client_id", clientId)
                .put("client_version", clientVersion)
                .put("supported_protocol_versions", JSONArray().put(1))
                .put("access_token", accessToken),
        )
        .toString()

    fun ping(nonce: String): String = JSONObject()
        .put("protocol_version", 1)
        .put("type", "ping")
        .put("payload", JSONObject().put("nonce", nonce))
        .toString()

    fun messageType(raw: String): String? = runCatching {
        JSONObject(raw).optString("type").takeIf { it.isNotEmpty() }
    }.getOrNull()
}
