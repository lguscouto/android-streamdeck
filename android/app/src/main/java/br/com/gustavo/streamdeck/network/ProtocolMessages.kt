package br.com.gustavo.streamdeck.network

import org.json.JSONObject
import org.json.JSONArray

enum class ActionAcknowledgementStatus {
    ACCEPTED,
    COMPLETED,
    REJECTED,
}

data class ActionAcknowledgement(
    val requestId: String,
    val status: ActionAcknowledgementStatus,
    val message: String?,
)

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

    fun press(
        requestId: String,
        profileId: String,
        pageId: String,
        buttonId: String,
        revision: Int,
    ): String {
        require(requestId.isNotBlank()) { "Request identifier must not be blank" }
        require(profileId.isNotBlank()) { "Profile identifier must not be blank" }
        require(pageId.isNotBlank()) { "Page identifier must not be blank" }
        require(buttonId.isNotBlank()) { "Button identifier must not be blank" }
        require(revision >= 1) { "Profile revision must be positive" }
        return JSONObject()
            .put("protocol_version", 1)
            .put("type", "press")
            .put(
                "payload",
                JSONObject()
                    .put("request_id", requestId)
                    .put("profile_id", profileId)
                    .put("page_id", pageId)
                    .put("button_id", buttonId)
                    .put("revision", revision),
            )
            .toString()
    }

    fun ping(nonce: String): String = JSONObject()
        .put("protocol_version", 1)
        .put("type", "ping")
        .put("payload", JSONObject().put("nonce", nonce))
        .toString()

    fun actionAcknowledgement(raw: String): ActionAcknowledgement? = runCatching {
        val envelope = JSONObject(raw)
        require(envelope.getInt("protocol_version") == 1)
        require(envelope.getString("type") == "ack")
        val payload = envelope.getJSONObject("payload")
        val status = when (payload.getString("status")) {
            "accepted" -> ActionAcknowledgementStatus.ACCEPTED
            "completed" -> ActionAcknowledgementStatus.COMPLETED
            "rejected" -> ActionAcknowledgementStatus.REJECTED
            else -> throw IllegalArgumentException("Unknown action acknowledgement status")
        }
        ActionAcknowledgement(
            requestId = payload.getString("request_id"),
            status = status,
            message = payload.optString("message").trim().takeIf { it.isNotEmpty() },
        )
    }.getOrNull()

    fun messageType(raw: String): String? = runCatching {
        JSONObject(raw).optString("type").takeIf { it.isNotEmpty() }
    }.getOrNull()
}
