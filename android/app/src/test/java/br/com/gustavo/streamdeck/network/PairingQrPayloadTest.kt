package br.com.gustavo.streamdeck.network

import org.junit.Assert.assertEquals
import org.junit.Test

class PairingQrPayloadTest {
    private val secret = "A".repeat(26)
    private val session = "A".repeat(22)

    @Test
    fun `le QR canonico emite os dados internos sem expor URL para a UI`() {
        val payload = PairingQrPayload.parse(
            "streamdeck://pair/v1?ip=192.168.100.20&port=8765&session=$session&secret=$secret",
        )

        assertEquals("192.168.100.20", payload.ipv4)
        assertEquals(8765, payload.port)
        assertEquals(session, payload.sessionId)
        assertEquals(secret, payload.pairingSecret)
    }

    @Test(expected = IllegalArgumentException::class)
    fun `rejeita parametro extra`() {
        PairingQrPayload.parse(
            "streamdeck://pair/v1?ip=192.168.100.20&port=8765&session=$session&secret=$secret&token=x",
        )
    }

    @Test(expected = IllegalArgumentException::class)
    fun `rejeita chave duplicada`() {
        PairingQrPayload.parse(
            "streamdeck://pair/v1?ip=192.168.100.20&port=8765&session=$session&session=$session&secret=$secret",
        )
    }

    @Test(expected = IllegalArgumentException::class)
    fun `rejeita encoding percentificado nao canonico`() {
        PairingQrPayload.parse(
            "streamdeck://pair/v1?ip=192.168.100.20&port=8765&session=$session&secret=%41$secret",
        )
    }

    @Test(expected = IllegalArgumentException::class)
    fun `rejeita servidor publico`() {
        PairingQrPayload.parse(
            "streamdeck://pair/v1?ip=8.8.8.8&port=8765&session=$session&secret=$secret",
        )
    }
}
