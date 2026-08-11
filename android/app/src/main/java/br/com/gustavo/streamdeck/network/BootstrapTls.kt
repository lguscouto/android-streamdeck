package br.com.gustavo.streamdeck.network

import java.security.cert.X509Certificate
import java.util.concurrent.TimeUnit
import javax.net.ssl.SSLContext
import javax.net.ssl.X509TrustManager
import okhttp3.OkHttpClient

/**
 * One-shot TLS transport for the password-authenticated bootstrap only.
 *
 * The default OkHttp hostname verifier remains active. The trust manager accepts only a
 * syntactically valid, currently valid server chain; the response is not trusted until its
 * HMAC proof binds the advertised CA to the pairing secret. This client is never persisted
 * or reused for REST/WSS.
 */
internal object BootstrapTls {
    fun newClient(): OkHttpClient {
        val trustManager = object : X509TrustManager {
            override fun checkClientTrusted(chain: Array<out X509Certificate>, authType: String) {
                throw IllegalArgumentException("client certificates are not accepted")
            }

            override fun checkServerTrusted(
                chain: Array<out X509Certificate>,
                authType: String,
            ) {
                require(chain.isNotEmpty()) { "server certificate chain is empty" }
                require(authType.isNotBlank()) { "TLS authentication type is missing" }
                chain.forEach { certificate ->
                    certificate.checkValidity()
                }
                require(chain.first().basicConstraints < 0) {
                    "server certificate must be a leaf certificate"
                }
            }

            override fun getAcceptedIssuers(): Array<X509Certificate> = emptyArray()
        }
        val sslContext = SSLContext.getInstance("TLS")
        sslContext.init(null, arrayOf(trustManager), null)
        return OkHttpClient.Builder()
            .sslSocketFactory(sslContext.socketFactory, trustManager)
            .connectTimeout(5, TimeUnit.SECONDS)
            .readTimeout(5, TimeUnit.SECONDS)
            .build()
    }
}
