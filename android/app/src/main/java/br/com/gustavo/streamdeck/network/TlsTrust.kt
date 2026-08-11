package br.com.gustavo.streamdeck.network

import java.io.ByteArrayInputStream
import java.security.KeyStore
import java.security.MessageDigest
import java.security.cert.CertificateFactory
import java.security.cert.X509Certificate
import java.util.Locale
import java.util.concurrent.TimeUnit
import javax.net.ssl.SSLContext
import javax.net.ssl.TrustManagerFactory
import javax.net.ssl.X509TrustManager
import okhttp3.OkHttpClient

/** Explicitly verified private-CA trust material for one paired Stream Deck server. */
class TlsTrust private constructor(
    val caCertificatePem: String,
    val trustCode: String,
    internal val trustManager: X509TrustManager,
) {
    fun newHttpClient(
        connectTimeoutSeconds: Long = DEFAULT_TIMEOUT_SECONDS,
        readTimeoutSeconds: Long = DEFAULT_TIMEOUT_SECONDS,
    ): OkHttpClient {
        val sslContext = SSLContext.getInstance("TLS")
        sslContext.init(null, arrayOf(trustManager), null)
        return OkHttpClient.Builder()
            .sslSocketFactory(sslContext.socketFactory, trustManager)
            .connectTimeout(connectTimeoutSeconds, TimeUnit.SECONDS)
            .readTimeout(readTimeoutSeconds, TimeUnit.SECONDS)
            .build()
    }

    companion object {
        private const val DEFAULT_TIMEOUT_SECONDS = 5L
        private const val CERTIFICATE_BEGIN = "-----BEGIN CERTIFICATE-----"
        private const val CERTIFICATE_END = "-----END CERTIFICATE-----"
        private const val TRUST_CODE_LENGTH = 19
        private const val TRUST_CODE_RAW_LENGTH = 16
        private const val TRUST_CODE_GROUP_LENGTH = 4
        private const val BASE32_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"

        fun fromPem(caCertificatePem: String, trustCode: String): TlsTrust {
            val normalizedPem = canonicalizePem(caCertificatePem)
            val certificate = parseCertificate(normalizedPem)
            validateCaCertificate(certificate)
            val expectedTrustCode = trustCodeFor(certificate)
            val providedTrustCode = normalizeTrustCode(trustCode)
            require(
                MessageDigest.isEqual(
                    expectedTrustCode.toByteArray(Charsets.US_ASCII),
                    providedTrustCode.toByteArray(Charsets.US_ASCII),
                ),
            ) { "trust code does not match CA certificate" }
            return createTrust(normalizedPem, certificate, expectedTrustCode)
        }

        /** Builds strict trust only after the password-authenticated bootstrap proof passed. */
        fun fromVerifiedPem(caCertificatePem: String): TlsTrust {
            val normalizedPem = canonicalizePem(caCertificatePem)
            val certificate = parseCertificate(normalizedPem)
            validateCaCertificate(certificate)
            return createTrust(normalizedPem, certificate, trustCodeFor(certificate))
        }

        fun trustCodeFor(certificate: X509Certificate): String {
            val digest = MessageDigest.getInstance("SHA-256")
                .digest(certificate.publicKey.encoded)
                .copyOf(10)
            val raw = base32Encode(digest)
            return raw.chunked(TRUST_CODE_GROUP_LENGTH).joinToString("-")
        }

        private fun canonicalizePem(value: String): String {
            val trimmed = value.trim()
            require(trimmed.countOccurrences(CERTIFICATE_BEGIN) == 1) {
                "CA certificate must contain exactly one certificate"
            }
            require(trimmed.countOccurrences(CERTIFICATE_END) == 1) {
                "CA certificate must contain exactly one certificate"
            }
            val body = trimmed.substring(
                trimmed.indexOf(CERTIFICATE_BEGIN) + CERTIFICATE_BEGIN.length,
                trimmed.indexOf(CERTIFICATE_END),
            ).filterNot(Char::isWhitespace)
            require(body.isNotEmpty()) { "CA certificate body is empty" }
            require(body.all { it in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=" }) {
                "CA certificate body is invalid"
            }
            return buildString {
                append(CERTIFICATE_BEGIN)
                append('\n')
                body.chunked(64).forEachIndexed { index, line ->
                    if (index > 0) append('\n')
                    append(line)
                }
                append('\n')
                append(CERTIFICATE_END)
                append('\n')
            }
        }

        private fun parseCertificate(pem: String): X509Certificate = runCatching {
            CertificateFactory.getInstance("X.509")
                .generateCertificate(ByteArrayInputStream(pem.toByteArray(Charsets.US_ASCII)))
                as X509Certificate
        }.getOrElse { throw IllegalArgumentException("CA certificate is invalid", it) }

        private fun validateCaCertificate(certificate: X509Certificate) {
            require(certificate.basicConstraints >= 0) { "certificate is not a CA" }
            certificate.checkValidity()
        }

        private fun createTrust(
            normalizedPem: String,
            certificate: X509Certificate,
            trustCode: String,
        ): TlsTrust = TlsTrust(
            caCertificatePem = "$normalizedPem\n",
            trustCode = trustCode,
            trustManager = trustManagerFor(certificate),
        )

        private fun normalizeTrustCode(value: String): String {
            val normalized = value.trim().uppercase(Locale.ROOT)
            require(normalized.length == TRUST_CODE_LENGTH) { "trust code is invalid" }
            require(normalized.count { it == '-' } == 3) { "trust code is invalid" }
            val raw = normalized.replace("-", "")
            require(raw.length == TRUST_CODE_RAW_LENGTH) { "trust code is invalid" }
            require(raw.all { it in BASE32_ALPHABET }) { "trust code is invalid" }
            return raw.chunked(TRUST_CODE_GROUP_LENGTH).joinToString("-")
        }

        private fun trustManagerFor(certificate: X509Certificate): X509TrustManager {
            val keyStore = KeyStore.getInstance(KeyStore.getDefaultType()).apply {
                load(null, null)
                setCertificateEntry("streamdeck-private-ca", certificate)
            }
            val factory = TrustManagerFactory.getInstance(
                TrustManagerFactory.getDefaultAlgorithm(),
            ).apply { init(keyStore) }
            return factory.trustManagers.filterIsInstance<X509TrustManager>().singleOrNull()
                ?: throw IllegalStateException("private CA trust manager is unavailable")
        }

        private fun base32Encode(bytes: ByteArray): String {
            var buffer = 0
            var bufferedBits = 0
            return buildString {
                bytes.forEach { byte ->
                    buffer = (buffer shl 8) or (byte.toInt() and 0xff)
                    bufferedBits += 8
                    while (bufferedBits >= 5) {
                        append(BASE32_ALPHABET[(buffer shr (bufferedBits - 5)) and 0x1f])
                        bufferedBits -= 5
                    }
                }
                if (bufferedBits > 0) {
                    append(BASE32_ALPHABET[(buffer shl (5 - bufferedBits)) and 0x1f])
                }
            }
        }

        private fun String.countOccurrences(value: String): Int =
            windowed(value.length, 1).count { it == value }
    }
}
