package br.com.gustavo.streamdeck.network

/** A valid client identity paired with an opaque server-issued access token and private CA. */
class PairingCredentials private constructor(
    val serverBaseUrl: String,
    val clientId: String,
    val accessToken: String,
    val tlsTrust: TlsTrust,
) {
    fun isFor(serverBaseUrl: String): Boolean = this.serverBaseUrl == serverBaseUrl

    companion object {
        fun fromStored(
            serverBaseUrl: String?,
            clientId: String?,
            accessToken: String?,
            caCertificatePem: String? = null,
            trustCode: String? = null,
        ): PairingCredentials? {
            val normalizedServerBaseUrl = serverBaseUrl?.trim()?.trimEnd('/')
                ?.takeIf { it.isNotEmpty() }
                ?: return null
            val endpoint = runCatching { ServerEndpoint.parse(normalizedServerBaseUrl) }
                .getOrNull()
                ?: return null
            val normalizedClientId = clientId?.trim()?.takeIf { it.isNotEmpty() }
                ?: return null
            val opaqueAccessToken = accessToken?.takeIf { it.isNotBlank() }
                ?: return null
            val tlsTrust = runCatching {
                if (trustCode.isNullOrBlank()) {
                    TlsTrust.fromVerifiedPem(caCertificatePem.orEmpty())
                } else {
                    TlsTrust.fromPem(caCertificatePem.orEmpty(), trustCode)
                }
            }.getOrNull() ?: return null
            return PairingCredentials(
                endpoint.httpBaseUrl,
                normalizedClientId,
                opaqueAccessToken,
                tlsTrust,
            )
        }
    }
}
