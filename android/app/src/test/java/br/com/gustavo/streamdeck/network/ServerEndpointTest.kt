package br.com.gustavo.streamdeck.network

import org.junit.Assert.assertEquals
import org.junit.Test

class ServerEndpointTest {
    @Test
    fun `normaliza endpoint HTTP e deriva websocket`() {
        val endpoint = ServerEndpoint.parse("http://10.0.2.2:18771/")

        assertEquals("http://10.0.2.2:18771", endpoint.httpBaseUrl)
        assertEquals("ws://10.0.2.2:18771/api/v1/ws", endpoint.websocketUrl)
        assertEquals(
            "http://10.0.2.2:18771/api/v1/pairing/claim",
            endpoint.pairingUrl,
        )
    }

    @Test
    fun `converte HTTPS em WSS`() {
        val endpoint = ServerEndpoint.parse("https://deck.example:9443")

        assertEquals("wss://deck.example:9443/api/v1/ws", endpoint.websocketUrl)
    }

    @Test
    fun `deriva rotas CRUD com revisao e substitutos explicitos`() {
        val endpoint = ServerEndpoint.parse("http://10.0.2.2:8765")

        assertEquals("http://10.0.2.2:8765/api/v1/profiles", endpoint.profilesUrl())
        assertEquals(
            "http://10.0.2.2:8765/api/v1/profiles/default/duplicate?expected_revision=2",
            endpoint.profileDuplicateUrl("default", 2),
        )
        assertEquals(
            "http://10.0.2.2:8765/api/v1/profiles/default?expected_revision=2&replacement_profile_id=work",
            endpoint.profileDeleteUrl("default", 2, "work"),
        )
        assertEquals(
            "http://10.0.2.2:8765/api/v1/profiles/default/pages/main/reorder?expected_revision=3",
            endpoint.pageReorderUrl("default", "main", 3),
        )
        assertEquals(
            "http://10.0.2.2:8765/api/v1/profiles/default/export",
            endpoint.profileExportUrl("default"),
        )
        assertEquals(
            "http://10.0.2.2:8765/api/v1/profiles/import?expected_revision=3",
            endpoint.profileImportUrl(3),
        )
    }

    @Test(expected = IllegalArgumentException::class)
    fun `rejeita credenciais no endpoint`() {
        ServerEndpoint.parse("http://user:secret@example.com:8765")
    }

    @Test(expected = IllegalArgumentException::class)
    fun `rejeita caminho arbitrario no endpoint`() {
        ServerEndpoint.parse("http://10.0.2.2:8765/private")
    }

    @Test(expected = IllegalArgumentException::class)
    fun `rejeita ids livres em rotas de pagina`() {
        ServerEndpoint.parse("http://10.0.2.2:8765").pageUrl("default", "page/id", 1)
    }
}
