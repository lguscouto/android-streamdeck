package br.com.gustavo.streamdeck.network

import kotlinx.coroutines.runBlocking
import okhttp3.Interceptor
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Protocol
import okhttp3.Response
import okhttp3.ResponseBody.Companion.toResponseBody
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class PairingClientCrudTest {
    @Test
    fun `recusa requisicao sem CA privada verificada`() = runBlocking {
        val error = runCatching {
            PairingClient().listProfiles(
                ServerEndpoint.parse("https://127.0.0.1:1"),
                "android",
                "token",
            )
        }.exceptionOrNull()

        assertTrue(error is PairingException)
        assertEquals("TLS_TRUST_REQUIRED", (error as PairingException).code)
    }

    @Test
    fun `envia autenticacao e expected revision em todas as mutacoes e valida rotas`() = runBlocking {
        val recorder = RequestRecorder()
        val client = PairingClient(
            httpClient = OkHttpClient.Builder().addInterceptor(recorder).build(),
        )
        val endpoint = ServerEndpoint.parse("https://10.0.2.2:8765/")
        val json = "{}"

        client.listProfiles(endpoint, "android", "token")
        client.getProfile(endpoint, "android", "token", "default")
        client.createProfile(endpoint, "android", "token", 1, json)
        client.renameProfile(endpoint, "android", "token", "default", 2, "Renomeado")
        client.duplicateProfile(endpoint, "android", "token", "default", 2, "copy", "Cópia")
        client.activateProfile(endpoint, "android", "token", "default", 2)
        client.deleteProfile(endpoint, "android", "token", "default", 2, "copy")
        client.createPage(endpoint, "android", "token", "default", 3, json)
        client.renamePage(endpoint, "android", "token", "default", "main", 4, "Principal")
        client.reorderPage(endpoint, "android", "token", "default", "main", 5, 0)
        client.deletePage(endpoint, "android", "token", "default", "main", 6, "secondary")
        client.exportProfileJson(endpoint, "android", "token", "default")
        client.importProfileJson(endpoint, "android", "token", 7, json)

        assertEquals(13, recorder.requests.size)
        recorder.requests.drop(2).filter { it.method != "GET" }.forEach { request ->
            assertEquals("Bearer token", request.header("Authorization"))
            assertEquals("android", request.header("X-StreamDeck-Client-Id"))
            assertTrue(request.url.queryParameter("expected_revision") != null)
        }
        assertEquals(
            "https://10.0.2.2:8765/api/v1/profiles/default/pages/main/reorder?expected_revision=5",
            recorder.requests[9].url.toString(),
        )
        assertEquals(
            "https://10.0.2.2:8765/api/v1/profiles/default/pages/main?expected_revision=6&replacement_page_id=secondary",
            recorder.requests[10].url.toString(),
        )
        assertEquals(
            "https://10.0.2.2:8765/api/v1/profiles/default/export",
            recorder.requests[11].url.toString(),
        )
        assertEquals("GET", recorder.requests[11].method)
        assertEquals(
            "https://10.0.2.2:8765/api/v1/profiles/import?expected_revision=7",
            recorder.requests[12].url.toString(),
        )
        assertEquals("POST", recorder.requests[12].method)
    }

    @Test
    fun `conflito 409 nao vaza corpo sensivel`() = runBlocking {
        val recorder = RequestRecorder(
            code = 409,
            body = """{"code":"PROFILE_REVISION_CONFLICT","message":"access_token=[REDACTED] /private/db"}""",
        )
        val client = PairingClient(
            httpClient = OkHttpClient.Builder().addInterceptor(recorder).build(),
        )
        val endpoint = ServerEndpoint.parse("https://10.0.2.2:8765")

        val error = runCatching {
            client.renameProfile(endpoint, "android", "token", "default", 1, "Novo")
        }.exceptionOrNull() as PairingException

        assertEquals("PROFILE_REVISION_CONFLICT", error.code)
        assertEquals("Profile revision conflict", error.message)
        assertTrue("[REDACTED]" !in error.message.orEmpty())
        assertTrue("/private/db" !in error.message.orEmpty())
    }
}

private class RequestRecorder(
    private val code: Int = 200,
    private val body: String = "{\"profiles\":[]}",
) : Interceptor {
    val requests = mutableListOf<okhttp3.Request>()

    override fun intercept(chain: Interceptor.Chain): Response {
        val request = chain.request()
        requests += request
        return Response.Builder()
            .request(request)
            .protocol(Protocol.HTTP_1_1)
            .code(code)
            .message(if (code == 200) "OK" else "Conflict")
            .body(body.toResponseBody("application/json".toMediaType()))
            .build()
    }
}