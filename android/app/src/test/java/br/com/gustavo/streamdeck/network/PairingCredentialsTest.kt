package br.com.gustavo.streamdeck.network

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class PairingCredentialsTest {
    @Test
    fun `recusa credencial persistida sem identificador ou token`() {
        assertNull(PairingCredentials.fromStored("http://server", null, "token"))
        assertNull(PairingCredentials.fromStored("http://server", "android-1", null))
        assertNull(PairingCredentials.fromStored("http://server", "   ", "token"))
        assertNull(PairingCredentials.fromStored("http://server", "android-1", "   "))
    }

    @Test
    fun `normaliza identificador sem modificar token opaco`() {
        val credentials = PairingCredentials.fromStored(
            serverBaseUrl = "http://10.0.2.2:8765",
            clientId = " android-1 ",
            accessToken = "opaque-token_123",
        )

        requireNotNull(credentials)
        assertEquals("android-1", credentials.clientId)
        assertEquals("opaque-token_123", credentials.accessToken)
    }

    @Test
    fun `vincula token ao endpoint que emitiu o pareamento`() {
        val credentials = PairingCredentials.fromStored(
            serverBaseUrl = "http://10.0.2.2:8765",
            clientId = "android-1",
            accessToken = "opaque-token_123",
        )

        requireNotNull(credentials)
        assertEquals("http://10.0.2.2:8765", credentials.serverBaseUrl)
        assertEquals(true, credentials.isFor("http://10.0.2.2:8765"))
        assertEquals(false, credentials.isFor("http://192.168.1.10:8765"))
    }
}
