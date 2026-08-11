package br.com.gustavo.streamdeck.network

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class TlsTrustTest {
    @Test
    fun `aceita CA privada somente quando o codigo de confianca coincide`() {
        val trust = TlsTrust.fromPem(TestTlsFixture.CA_PEM, TestTlsFixture.TRUST_CODE)

        assertEquals(TestTlsFixture.TRUST_CODE, trust.trustCode)
        assertEquals(1, trust.trustManager.acceptedIssuers.size)
    }

    @Test
    fun `aceita CA autenticada por prova sem exigir trust code na UX`() {
        val trust = TlsTrust.fromVerifiedPem(TestTlsFixture.CA_PEM)

        assertEquals(TestTlsFixture.TRUST_CODE, trust.trustCode)
    }

    @Test
    fun `aceita CA PEM compacta recebida por bootstrap de campo de texto`() {
        val compactPem = TestTlsFixture.CA_PEM.replace("\n", "")

        val trust = TlsTrust.fromPem(compactPem, TestTlsFixture.TRUST_CODE)

        assertEquals(TestTlsFixture.TRUST_CODE, trust.trustCode)
    }

    @Test
    fun `recusa CA privada quando o codigo de confianca diverge`() {
        val error = runCatching {
            TlsTrust.fromPem(TestTlsFixture.CA_PEM, "AAAA-AAAA-AAAA-AAAA")
        }.exceptionOrNull()

        assertTrue(error is IllegalArgumentException)
    }
}
