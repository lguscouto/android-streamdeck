package br.com.gustavo.streamdeck.network

import java.net.URI

/** Validated base address for the local Stream Deck server. */
class ServerEndpoint private constructor(
    val httpBaseUrl: String,
    val websocketUrl: String,
    val pairingUrl: String,
) {
    fun profileUpdateUrl(profileId: String, expectedRevision: Int): String {
        require(STABLE_ID.matches(profileId)) { "profile id is invalid" }
        require(expectedRevision >= 1) { "profile revision must be positive" }
        return "$httpBaseUrl/api/v1/profiles/$profileId?expected_revision=$expectedRevision"
    }

    companion object {
        private val STABLE_ID = Regex("^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")

        fun parse(raw: String): ServerEndpoint {
            val normalized = raw.trim().trimEnd('/')
            require(normalized.isNotEmpty()) { "server endpoint is empty" }
            val uri = runCatching { URI(normalized) }
                .getOrElse { throw IllegalArgumentException("server endpoint is invalid", it) }
            require(uri.scheme == "http" || uri.scheme == "https") {
                "server endpoint must use http or https"
            }
            require(uri.userInfo.isNullOrEmpty()) {
                "server endpoint must not contain credentials"
            }
            require(uri.host != null && uri.host.isNotBlank()) {
                "server endpoint must contain a host"
            }
            require(uri.rawPath.isNullOrEmpty() || uri.rawPath == "/") {
                "server endpoint must not contain a path"
            }
            require(uri.rawQuery == null && uri.rawFragment == null) {
                "server endpoint must not contain query or fragment"
            }
            require(uri.port in -1..65535) {
                "server endpoint port is invalid"
            }

            val base = buildString {
                append(uri.scheme)
                append("://")
                append(uri.rawAuthority)
            }
            val websocketScheme = if (uri.scheme == "https") "wss" else "ws"
            return ServerEndpoint(
                httpBaseUrl = base,
                websocketUrl = "$websocketScheme://${uri.rawAuthority}/api/v1/ws",
                pairingUrl = "$base/api/v1/pairing/claim",
            )
        }
    }
}
