package br.com.gustavo.streamdeck.network

import kotlinx.coroutines.runBlocking
import okhttp3.Interceptor
import okhttp3.OkHttpClient
import okhttp3.Protocol
import okhttp3.Response
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.ResponseBody.Companion.toResponseBody
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Test

class PairingClientProfileUpdateTest {
    @Test
    fun `salva perfil com revisao e cabecalhos de autenticacao`() = runBlocking {
        val interceptor = RecordingResponseInterceptor(
            body = """
                {
                  "protocol_version": 1,
                  "id": "default",
                  "name": "Perfil",
                  "revision": 2,
                  "active_page_id": "main",
                  "pages": []
                }
            """.trimIndent(),
        )
        val client = PairingClient(
            httpClient = OkHttpClient.Builder()
                .addInterceptor(interceptor)
                .build(),
        )

        val response = client.updateProfile(
            endpoint = ServerEndpoint.parse("https://10.0.2.2:8765"),
            clientId = "android",
            accessToken = "opaque-token",
            profileId = "default",
            expectedRevision = 1,
            profileWire = """
                {
                  "protocol_version": 1,
                  "id": "default",
                  "name": "Perfil",
                  "revision": 2,
                  "active_page_id": "main",
                  "pages": []
                }
            """.trimIndent(),
        )

        assertEquals(2, org.json.JSONObject(response).optInt("revision"))
        val request = interceptor.request
        assertNotNull(request)
        assertEquals(
            "https://10.0.2.2:8765/api/v1/profiles/default?expected_revision=1",
            request!!.url.toString(),
        )
        assertEquals("Bearer opaque-token", request.header("Authorization"))
        assertEquals("android", request.header("X-StreamDeck-Client-Id"))
        assertEquals(
            "application/json",
            request.body?.contentType()?.toString()?.substringBefore(';'),
        )
    }
}

private class RecordingResponseInterceptor(
    private val body: String,
) : Interceptor {
    var request: okhttp3.Request? = null

    override fun intercept(chain: Interceptor.Chain): Response {
        request = chain.request()
        return Response.Builder()
            .request(request!!)
            .protocol(Protocol.HTTP_1_1)
            .code(200)
            .message("OK")
            .body(body.toResponseBody("application/json".toMediaType()))
            .build()
    }
}
