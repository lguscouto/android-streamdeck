package br.com.gustavo.streamdeck.network

/** User-facing pairing input: a canonical private IPv4 and the hidden default port. */
class PairingInput private constructor(
    val ipv4: String,
    val defaultPort: Int = DEFAULT_PORT,
) {
    companion object {
        const val DEFAULT_PORT: Int = 8765
        private val IPV4 = Regex("^(\\d{1,3})(\\.)(\\d{1,3})(\\.)(\\d{1,3})(\\.)(\\d{1,3})$")

        fun parseIpv4(raw: String): PairingInput {
            val value = raw.trim()
            val match = IPV4.matchEntire(value)
                ?: throw IllegalArgumentException("pairing address must be a private IPv4")
            val octets = listOf(1, 3, 5, 7).map { match.groupValues[it] }
            require(octets.none { it.length > 1 && it.startsWith('0') }) {
                "pairing address must use canonical IPv4"
            }
            val values = octets.map { it.toIntOrNull() ?: -1 }
            require(values.all { it in 0..255 }) {
                "pairing address must be a private IPv4"
            }
            val isRfc1918 = values[0] == 10 ||
                (values[0] == 172 && values[1] in 16..31) ||
                (values[0] == 192 && values[1] == 168)
            require(isRfc1918) { "pairing address must be a private IPv4" }
            return PairingInput(values.joinToString("."))
        }

        fun requirePort(port: Int): Int {
            require(port in 1..65535) { "pairing port is invalid" }
            return port
        }
    }
}
