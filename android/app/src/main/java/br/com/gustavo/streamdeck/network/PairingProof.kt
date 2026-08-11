package br.com.gustavo.streamdeck.network

import java.nio.charset.StandardCharsets
import java.security.MessageDigest
import java.security.MessageDigest.isEqual
import java.util.Base64
import javax.crypto.Mac
import javax.crypto.spec.SecretKeySpec

data class PairingBootstrap(
    val version: Int,
    val sessionId: String,
    val salt: String,
    val expiresAt: String,
    val serverIp: String,
    val port: Int,
    val caCertificatePem: String,
    val serverProof: String,
)

/** Shared HKDF/HMAC contract with server/app/pairing_session.py. */
object PairingProof {
    private const val INFO = "streamdeck-pairing-v1"
    private const val PAIRING_BYTES = 16
    private val BASE32_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"
    private val BASE32_PATTERN = Regex("^[A-Z2-7]{26}$")
    private val BASE64_URL_PATTERN = Regex("^[A-Za-z0-9_-]{43}$")

    fun derivePairingKey(pairingSecret: String, saltBase64Url: String): ByteArray {
        val secret = normalizeSecret(pairingSecret)
        val secretBytes = secret.toByteArray(StandardCharsets.US_ASCII)
        val salt = decodeBase64Url(saltBase64Url, PAIRING_BYTES)
        return try {
            hkdfSha256(
                inputKeyMaterial = secretBytes,
                salt = salt,
                info = INFO.toByteArray(StandardCharsets.US_ASCII),
                length = 32,
            )
        } finally {
            secretBytes.fill(0)
            salt.fill(0)
        }
    }

    fun sessionIdForSecret(pairingSecret: String): String {
        val normalized = normalizeSecret(pairingSecret)
        val input = "$INFO|session|".toByteArray(StandardCharsets.US_ASCII) +
            normalized.toByteArray(StandardCharsets.US_ASCII)
        val digest = MessageDigest.getInstance("SHA-256")
            .digest(input)
            .copyOf(16)
        input.fill(0)
        return try {
            encodeBase64Url(digest)
        } finally {
            digest.fill(0)
        }
    }

    fun verifyServerProof(bundle: PairingBootstrap, pairingKey: ByteArray): Boolean {
        require(bundle.version == 1) { "unsupported pairing version" }
        val supplied = decodeBase64Url(bundle.serverProof, 32)
        val message = canonicalBootstrap(bundle).toByteArray(StandardCharsets.UTF_8)
        return try {
            val expected = hmacSha256(pairingKey, message)
            try {
                isEqual(expected, supplied)
            } finally {
                expected.fill(0)
            }
        } finally {
            supplied.fill(0)
            message.fill(0)
        }
    }

    fun clientProof(
        pairingKey: ByteArray,
        sessionId: String,
        clientId: String,
        clientVersion: String,
    ): String {
        require(sessionId.isNotBlank()) { "pairing session is required" }
        require(clientId.isNotBlank()) { "client id is required" }
        require(clientVersion.isNotBlank()) { "client version is required" }
        val canonical = "$INFO|claim|" +
            "session_id=$sessionId|client_id=$clientId|client_version=$clientVersion"
        val message = canonical.toByteArray(StandardCharsets.UTF_8)
        val proof = hmacSha256(pairingKey, message)
        message.fill(0)
        return try {
            encodeBase64Url(proof)
        } finally {
            proof.fill(0)
        }
    }

    fun normalizeSecret(value: String): String {
        val normalized = value.filterNot(Char::isWhitespace).replace("-", "").uppercase()
        require(BASE32_PATTERN.matches(normalized)) { "pairing secret is invalid" }
        val decoded = decodeBase32(normalized)
        try {
            require(decoded.size == PAIRING_BYTES) {
                "pairing secret is invalid"
            }
        } finally {
            decoded.fill(0)
        }
        return normalized
    }

    private fun canonicalBootstrap(bundle: PairingBootstrap): String {
        val caBytes = bundle.caCertificatePem.toByteArray(StandardCharsets.UTF_8)
        val caDigest = MessageDigest.getInstance("SHA-256").digest(caBytes)
        return try {
            "$INFO|bootstrap|" +
                "version=${bundle.version}|session_id=${bundle.sessionId}|salt=${bundle.salt}|" +
                "expires_at=${bundle.expiresAt}|server_ip=${bundle.serverIp}|port=${bundle.port}|" +
                "ca_sha256=${encodeBase64Url(caDigest)}"
        } finally {
            caBytes.fill(0)
            caDigest.fill(0)
        }
    }

    private fun decodeBase64Url(value: String, expectedBytes: Int): ByteArray {
        require(!value.contains('=')) { "base64url padding is not canonical" }
        require(value.isNotEmpty() && value.all { it.isLetterOrDigit() || it == '_' || it == '-' }) {
            "base64url value is invalid"
        }
        val decoded = runCatching { Base64.getUrlDecoder().decode(value) }
            .getOrElse { throw IllegalArgumentException("base64url value is invalid", it) }
        require(decoded.size == expectedBytes) { "base64url value has invalid length" }
        return decoded
    }

    private fun decodeBase32(value: String): ByteArray {
        var accumulator = 0
        var bits = 0
        val output = ArrayList<Byte>(PAIRING_BYTES)
        for (character in value) {
            val digit = BASE32_ALPHABET.indexOf(character)
            require(digit >= 0) { "base32 value is invalid" }
            accumulator = (accumulator shl 5) or digit
            bits += 5
            while (bits >= 8) {
                bits -= 8
                output += ((accumulator shr bits) and 0xff).toByte()
                accumulator = if (bits == 0) 0 else accumulator and ((1 shl bits) - 1)
            }
        }
        require(bits < 8 && accumulator == 0) { "base32 value is not canonical" }
        return output.toByteArray()
    }

    private fun hkdfSha256(
        inputKeyMaterial: ByteArray,
        salt: ByteArray,
        info: ByteArray,
        length: Int,
    ): ByteArray {
        require(length in 1..255 * 32) { "HKDF output length is invalid" }
        val prk = hmacSha256(salt, inputKeyMaterial)
        val result = ByteArray(length)
        var previous = ByteArray(0)
        var offset = 0
        var counter = 1
        var completed = false
        try {
            while (offset < length) {
                val mac = Mac.getInstance("HmacSHA256")
                mac.init(SecretKeySpec(prk, "HmacSHA256"))
                mac.update(previous)
                mac.update(info)
                mac.update(counter.toByte())
                val next = mac.doFinal()
                previous.fill(0)
                previous = next
                val copied = minOf(previous.size, length - offset)
                previous.copyInto(result, offset, 0, copied)
                offset += copied
                counter += 1
            }
            completed = true
            return result
        } finally {
            prk.fill(0)
            previous.fill(0)
            if (!completed) {
                result.fill(0)
            }
        }
    }

    private fun hmacSha256(key: ByteArray, message: ByteArray): ByteArray {
        val mac = Mac.getInstance("HmacSHA256")
        mac.init(SecretKeySpec(key, "HmacSHA256"))
        return mac.doFinal(message)
    }

    private fun encodeBase64Url(value: ByteArray): String =
        Base64.getUrlEncoder().withoutPadding().encodeToString(value)
}
