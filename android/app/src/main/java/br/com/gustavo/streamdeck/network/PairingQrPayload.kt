package br.com.gustavo.streamdeck.network

import java.net.URI

/** Strict, versioned QR payload used only to bootstrap a one-time pairing session. */
class PairingQrPayload private constructor(
    val ipv4: String,
    val port: Int,
    val sessionId: String,
    val pairingSecret: String,
) {
    fun endpoint(): ServerEndpoint = ServerEndpoint.fromPrivateIpv4(ipv4, port)

    companion object {
        private val SESSION = Regex("^[A-Za-z0-9_-]{22}$")
        private val SECRET = Regex("^[A-Z2-7]{26}$")
        private val PORT = Regex("^[0-9]{1,5}$")
        private val KEYS = listOf("ip", "port", "session", "secret")

        fun parse(raw: String): PairingQrPayload {
            val uri = runCatching { URI(raw) }
                .getOrElse { throw IllegalArgumentException("QR payload is invalid", it) }
            require(uri.scheme == "streamdeck") { "QR payload scheme is invalid" }
            require(uri.rawAuthority == "pair") { "QR payload authority is invalid" }
            require(uri.userInfo == null && uri.port == -1) {
                "QR payload authority is invalid"
            }
            require(uri.rawPath == "/v1") { "QR payload version is invalid" }
            require(uri.rawFragment == null) { "QR payload fragment is invalid" }
            val rawQuery = uri.rawQuery
                ?: throw IllegalArgumentException("QR payload query is missing")
            require('%' !in rawQuery && '+' !in rawQuery) {
                "QR payload encoding is not canonical"
            }
            val parts = rawQuery.split('&')
            require(parts.size == KEYS.size) { "QR payload parameters are invalid" }
            val parsed = parts.map { part ->
                val separator = part.indexOf('=')
                require(separator > 0 && separator == part.lastIndexOf('=')) {
                    "QR payload parameter is invalid"
                }
                part.substring(0, separator) to part.substring(separator + 1)
            }
            require(parsed.map { it.first } == KEYS) {
                "QR payload parameters are invalid"
            }
            val values = parsed.map { it.second }
            require(values.none { it.isEmpty() || it.any(Char::isWhitespace) }) {
                "QR payload values are invalid"
            }
            val ip = PairingInput.parseIpv4(values[0]).ipv4
            require(PORT.matches(values[1])) { "QR payload port is invalid" }
            require(values[1] == values[1].trimStart('0') || values[1] == "0") {
                "QR payload port is not canonical"
            }
            val port = values[1].toIntOrNull()
                ?: throw IllegalArgumentException("QR payload port is invalid")
            PairingInput.requirePort(port)
            require(SESSION.matches(values[2])) { "QR payload session is invalid" }
            require(SECRET.matches(values[3])) { "QR payload secret is invalid" }
            return PairingQrPayload(ip, port, values[2], values[3])
        }
    }
}
