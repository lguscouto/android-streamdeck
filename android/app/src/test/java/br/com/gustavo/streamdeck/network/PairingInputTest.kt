package br.com.gustavo.streamdeck.network

import org.junit.Assert.assertEquals
import org.junit.Test

class PairingInputTest {
    @Test
    fun `aceita IPv4 privado canonico para o pareamento`() {
        val input = PairingInput.parseIpv4("192.168.100.20")

        assertEquals("192.168.100.20", input.ipv4)
        assertEquals(8765, input.defaultPort)
    }

    @Test
    fun `aceita o endereco especial do emulador`() {
        assertEquals("10.0.2.2", PairingInput.parseIpv4("10.0.2.2").ipv4)
    }

    @Test(expected = IllegalArgumentException::class)
    fun `rejeita IPv4 publico`() {
        PairingInput.parseIpv4("8.8.8.8")
    }

    @Test(expected = IllegalArgumentException::class)
    fun `rejeita hostname`() {
        PairingInput.parseIpv4("deck.local")
    }

    @Test(expected = IllegalArgumentException::class)
    fun `rejeita path ou query no campo de IP`() {
        PairingInput.parseIpv4("192.168.100.20/path?secret=hidden")
    }

    @Test(expected = IllegalArgumentException::class)
    fun `rejeita porta fora do intervalo interno`() {
        ServerEndpoint.fromPrivateIpv4("192.168.100.20", port = 0)
    }
}
