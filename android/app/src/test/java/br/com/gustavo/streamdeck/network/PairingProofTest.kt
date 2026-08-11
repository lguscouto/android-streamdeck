package br.com.gustavo.streamdeck.network

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class PairingProofTest {
    private val secret = "A".repeat(26)
    private val session = "A".repeat(22)
    private val salt = "A".repeat(22)
    private val key = PairingProof.derivePairingKey(secret, salt)

    @Test
    fun `deriva o mesmo session id que o servidor para o modo manual`() {
        assertEquals("JpZL0zkBj3xXyfS69e84YA", PairingProof.sessionIdForSecret(secret))
    }

    @Test
    fun `reproduz vetor HKDF e server proof do servidor`() {
        val bundle = PairingBootstrap(
            version = 1,
            sessionId = session,
            salt = salt,
            expiresAt = "2026-08-11T12:00:00Z",
            serverIp = "192.168.100.20",
            port = 8765,
            caCertificatePem = "synthetic-ca-pem",
            serverProof = "z7ztkkOmrr9CU_vr4rFqGXcl0nub6NbhC9SaqCXdAuo",
        )

        assertTrue(PairingProof.verifyServerProof(bundle, key))
        assertEquals(
            "514348XPGv8vldoMTmWpXorVDkaOQMFW3lCKlOWm4GU",
            PairingProof.clientProof(key, session, "android-test", "0.1.0"),
        )
    }

    @Test
    fun `qualquer alteracao no bootstrap invalida a prova`() {
        val bundle = PairingBootstrap(
            version = 1,
            sessionId = session,
            salt = salt,
            expiresAt = "2026-08-11T12:00:00Z",
            serverIp = "192.168.100.20",
            port = 8765,
            caCertificatePem = "synthetic-ca-pem",
            serverProof = "z7ztkkOmrr9CU_vr4rFqGXcl0nub6NbhC9SaqCXdAuo",
        )

        assertFalse(
            PairingProof.verifyServerProof(
                bundle.copy(serverIp = "192.168.100.21"),
                key,
            ),
        )
    }
}
