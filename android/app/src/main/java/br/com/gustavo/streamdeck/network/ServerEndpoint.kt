package br.com.gustavo.streamdeck.network

import java.net.URI

/** Validated base address for the local Stream Deck server. */
class ServerEndpoint private constructor(
    val httpBaseUrl: String,
    val websocketUrl: String,
    val pairingUrl: String,
) {
    val serverHost: String
        get() = URI(httpBaseUrl).host

    val serverPort: Int
        get() = URI(httpBaseUrl).port

    fun pairingBootstrapUrl(sessionId: String): String {
        require(SESSION_ID.matches(sessionId)) { "pairing session id is invalid" }
        return "$httpBaseUrl/api/v1/pairing/bootstrap?session_id=$sessionId"
    }

    fun profilesUrl(): String = "$httpBaseUrl/api/v1/profiles"

    fun profilesCreateUrl(expectedRevision: Int): String =
        queryUrl(profilesUrl(), expectedRevision)

    fun profileUrl(profileId: String): String {
        requireProfileId(profileId)
        return "$httpBaseUrl/api/v1/profiles/$profileId"
    }

    fun profileUpdateUrl(profileId: String, expectedRevision: Int): String =
        profileMutationUrl(profileId, expectedRevision)

    fun profileRenameUrl(profileId: String, expectedRevision: Int): String =
        profileMutationUrl(profileId, expectedRevision)

    fun profileDuplicateUrl(profileId: String, expectedRevision: Int): String =
        queryUrl("${profilePath(profileId)}/duplicate", expectedRevision)

    fun profileActivateUrl(profileId: String, expectedRevision: Int): String =
        queryUrl("${profilePath(profileId)}/activate", expectedRevision)

    fun profileDeleteUrl(
        profileId: String,
        expectedRevision: Int,
        replacementProfileId: String? = null,
    ): String = queryUrl(
        path = profileUrl(profileId),
        expectedRevision = expectedRevision,
        extra = replacementProfileId?.let {
            requireProfileId(it)
            "replacement_profile_id=$it"
        },
    )

    fun profilePagesUrl(profileId: String, expectedRevision: Int): String =
        queryUrl("${profilePath(profileId)}/pages", expectedRevision)

    fun pageUrl(profileId: String, pageId: String, expectedRevision: Int): String {
        requireProfileId(profileId)
        requirePageId(pageId)
        return queryUrl(
            path = "$httpBaseUrl/api/v1/profiles/$profileId/pages/$pageId",
            expectedRevision = expectedRevision,
        )
    }

    fun pageRenameUrl(profileId: String, pageId: String, expectedRevision: Int): String =
        pageUrl(profileId, pageId, expectedRevision)

    fun pageReorderUrl(profileId: String, pageId: String, expectedRevision: Int): String =
        queryUrl("${pagePath(profileId, pageId)}/reorder", expectedRevision)

    fun pageDeleteUrl(
        profileId: String,
        pageId: String,
        expectedRevision: Int,
        replacementPageId: String? = null,
    ): String = queryUrl(
        path = pagePath(profileId, pageId),
        expectedRevision = expectedRevision,
        extra = replacementPageId?.let {
            requirePageId(it)
            "replacement_page_id=$it"
        },
    )

    /** Export/import use the validated profile resource JSON contract. */
    fun profileExportUrl(profileId: String): String {
        requireProfileId(profileId)
        return "${profilePath(profileId)}/export"
    }

    fun profileImportUrl(expectedRevision: Int): String =
        queryUrl("$httpBaseUrl/api/v1/profiles/import", expectedRevision)

    fun profileImportUrl(profileId: String, expectedRevision: Int): String {
        requireProfileId(profileId)
        return profileImportUrl(expectedRevision)
    }

    private fun profileMutationUrl(profileId: String, expectedRevision: Int): String {
        requireProfileId(profileId)
        return queryUrl(profileUrl(profileId), expectedRevision)
    }

    private fun profilePath(profileId: String): String = profileUrl(profileId)

    private fun pagePath(profileId: String, pageId: String): String {
        requireProfileId(profileId)
        requirePageId(pageId)
        return "$httpBaseUrl/api/v1/profiles/$profileId/pages/$pageId"
    }

    private fun queryUrl(path: String, expectedRevision: Int, extra: String? = null): String {
        require(expectedRevision >= 1) { "profile revision must be positive" }
        return buildString {
            append(path)
            append("?expected_revision=")
            append(expectedRevision)
            if (!extra.isNullOrBlank()) {
                append('&')
                append(extra)
            }
        }
    }

    private fun requireProfileId(profileId: String) {
        require(STABLE_ID.matches(profileId)) { "profile id is invalid" }
    }

    private fun requirePageId(pageId: String) {
        require(STABLE_ID.matches(pageId)) { "page id is invalid" }
    }

    companion object {
        private val STABLE_ID = Regex("^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
        private val SESSION_ID = Regex("^[A-Za-z0-9_-]{22}$")

        fun fromPrivateIpv4(ip: String, port: Int = PairingInput.DEFAULT_PORT): ServerEndpoint {
            val input = PairingInput.parseIpv4(ip)
            val checkedPort = PairingInput.requirePort(port)
            val base = "https://${input.ipv4}:$checkedPort"
            return ServerEndpoint(
                httpBaseUrl = base,
                websocketUrl = "wss://${input.ipv4}:$checkedPort/api/v1/ws",
                pairingUrl = "$base/api/v1/pairing/claim",
            )
        }

        fun parse(raw: String): ServerEndpoint {
            val normalized = raw.trim().trimEnd('/')
            require(normalized.isNotEmpty()) { "server endpoint is empty" }
            val uri = runCatching { URI(normalized) }
                .getOrElse { throw IllegalArgumentException("server endpoint is invalid", it) }
            require(uri.scheme == "https") {
                "server endpoint must use https"
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
            val websocketScheme = "wss"
            return ServerEndpoint(
                httpBaseUrl = base,
                websocketUrl = "$websocketScheme://${uri.rawAuthority}/api/v1/ws",
                pairingUrl = "$base/api/v1/pairing/claim",
            )
        }
    }
}
