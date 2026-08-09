package br.com.gustavo.streamdeck.network

/** A valid client identity paired with an opaque server-issued access token. */
class PairingCredentials private constructor(
    val serverBaseUrl: String,
    val clientId: String,
    val accessToken: String,
) {
    fun isFor(serverBaseUrl: String): Boolean = this.serverBaseUrl == serverBaseUrl

    companion object {
        fun fromStored(
            serverBaseUrl: String?,
            clientId: String?,
            accessToken: String?,
        ): PairingCredentials? {
            val normalizedServerBaseUrl = serverBaseUrl?.trim()?.trimEnd('/')
                ?.takeIf { it.isNotEmpty() }
                ?: return null
            val normalizedClientId = clientId?.trim()?.takeIf { it.isNotEmpty() }
                ?: return null
            val opaqueAccessToken = accessToken?.takeIf { it.isNotBlank() }
                ?: return null
            return PairingCredentials(
                normalizedServerBaseUrl,
                normalizedClientId,
                opaqueAccessToken,
            )
        }
    }
}
