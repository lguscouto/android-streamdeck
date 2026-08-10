package br.com.gustavo.streamdeck.network

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class PairingCredentialsTest {
    @Test
    fun `recusa credencial persistida sem identificador ou token`() {
        assertNull(PairingCredentials.fromStored("https://server", null, "token"))
        assertNull(PairingCredentials.fromStored("https://server", "android-1", null))
        assertNull(PairingCredentials.fromStored("https://server", "   ", "token"))
        assertNull(PairingCredentials.fromStored("https://server", "android-1", "   "))
    }

    @Test
    fun `recusa credencial persistida sem CA e codigo de confianca`() {
        assertNull(
            PairingCredentials.fromStored(
                serverBaseUrl = "https://10.0.2.2:8765",
                clientId = "android-1",
                accessToken = "token",
                caCertificatePem = null,
                trustCode = null,
            ),
        )
    }

    @Test
    fun `recusa credencial persistida em HTTP para impedir downgrade`() {
        assertNull(
            PairingCredentials.fromStored(
                "http://10.0.2.2:8765",
                "android-1",
                "token",
            ),
        )
    }

    @Test
    fun `normaliza identificador sem modificar token opaco`() {
        val credentials = PairingCredentials.fromStored(
            serverBaseUrl = "https://10.0.2.2:8765",
            clientId = " android-1 ",
            accessToken = "opaque-token_123",
            caCertificatePem = TestTlsFixture.CA_PEM,
            trustCode = TestTlsFixture.TRUST_CODE,
        )

        requireNotNull(credentials)
        assertEquals("android-1", credentials.clientId)
        assertEquals("opaque-token_123", credentials.accessToken)
    }

    @Test
    fun `vincula token ao endpoint que emitiu o pareamento`() {
        val credentials = PairingCredentials.fromStored(
            serverBaseUrl = "https://10.0.2.2:8765",
            clientId = "android-1",
            accessToken = "opaque-token_123",
            caCertificatePem = TestTlsFixture.CA_PEM,
            trustCode = TestTlsFixture.TRUST_CODE,
        )

        requireNotNull(credentials)
        assertEquals("https://10.0.2.2:8765", credentials.serverBaseUrl)
        assertEquals(true, credentials.isFor("https://10.0.2.2:8765"))
        assertEquals(false, credentials.isFor("https://192.168.1.10:8765"))
    }
}
