package br.com.gustavo.streamdeck.network

import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class ClientIdentityTest {
    @Test
    fun `gera identidade interna estavel no formato aceito pelo servidor`() {
        val first = ClientIdentity.generate()
        val second = ClientIdentity.generate()

        assertTrue(first.matches(Regex("^android-[0-9a-f-]{36}$")))
        assertTrue(second.matches(Regex("^android-[0-9a-f-]{36}$")))
        assertNotEquals(first, second)
    }
}
