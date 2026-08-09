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

    @Test(expected = IllegalArgumentException::class)
    fun `rejeita credenciais no endpoint`() {
        ServerEndpoint.parse("http://user:secret@example.com:8765")
    }

    @Test(expected = IllegalArgumentException::class)
    fun `rejeita caminho arbitrario no endpoint`() {
        ServerEndpoint.parse("http://10.0.2.2:8765/private")
    }
}
