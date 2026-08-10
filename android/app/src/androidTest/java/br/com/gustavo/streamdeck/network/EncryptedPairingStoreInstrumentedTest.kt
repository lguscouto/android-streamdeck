package br.com.gustavo.streamdeck.network

import android.content.Context
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class EncryptedPairingStoreInstrumentedTest {
    @Test
    fun storesCredentialsEncryptedAndReloadsThem() {
        val context = ApplicationProvider.getApplicationContext<Context>()
        val store = EncryptedPairingStore(context)
        val credentials = PairingCredentials.fromStored(
            serverBaseUrl = "https://deck.example",
            clientId = "instrumented-client",
            accessToken = "opaque-instrumented-token-123",
            caCertificatePem = TEST_CA_PEM,
            trustCode = TEST_TRUST_CODE,
        )
        requireNotNull(credentials)
        store.clear()

        try {
            store.save(credentials)

            val loaded = store.load()
            assertNotNull(loaded)
            assertEquals(credentials.serverBaseUrl, loaded?.serverBaseUrl)
            assertEquals(credentials.clientId, loaded?.clientId)
            assertEquals(credentials.accessToken, loaded?.accessToken)
            assertEquals(credentials.tlsTrust.caCertificatePem, loaded?.tlsTrust?.caCertificatePem)
            assertEquals(credentials.tlsTrust.trustCode, loaded?.tlsTrust?.trustCode)

            val encryptedValues = context.getSharedPreferences(
                "streamdeck_pairing",
                Context.MODE_PRIVATE,
            ).all.values.filterIsInstance<String>()
            assertEquals(5, encryptedValues.size)
            assertTrue(encryptedValues.all { it.startsWith("v1:") })
            assertFalse(encryptedValues.any { it.contains(credentials.accessToken) })
            assertFalse(encryptedValues.any { it.contains(credentials.tlsTrust.caCertificatePem) })
            assertFalse(encryptedValues.any { it.contains(credentials.tlsTrust.trustCode) })
        } finally {
            store.clear()
        }
    }

    private companion object {
        const val TEST_TRUST_CODE = "GJBG-GCAM-LAZP-ORC6"

        val TEST_CA_PEM = """
            -----BEGIN CERTIFICATE-----
            MIIBYzCCAQqgAwIBAgIUUWpquYS/i2v50e9jLGiZSyM92AIwCgYIKoZIzj0EAwIw
            JjEkMCIGA1UEAwwbQW5kcm9pZCBTdHJlYW0gRGVjayBUZXN0IENBMB4XDTI2MDgx
            MDEwNTYwOVoXDTM2MDgwNzEwNTcwOVowJjEkMCIGA1UEAwwbQW5kcm9pZCBTdHJl
            YW0gRGVjayBUZXN0IENBMFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEO4ob88zl
            gwAazhAx8LvOCkbVOpALBt8N6Ordqwy33XIY50e//o+mSnVeRuFJV0hRFfmHR3Dy
            8TNE1/LQ4dOx7KMWMBQwEgYDVR0TAQH/BAgwBgEB/wIBADAKBggqhkjOPQQDAgNH
            ADBEAiBScyUbP37whD/Ucr+ECXWqiRtyyAGgs4cFtQFvFqGevwIgEmk4OP5UECJw
            eWoraB3HVW7CIuAiYA9EQbxAoqYG2ik=
            -----END CERTIFICATE-----
        """.trimIndent()
    }
}
