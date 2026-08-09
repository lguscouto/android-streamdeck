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

            val encryptedValues = context.getSharedPreferences(
                "streamdeck_pairing",
                Context.MODE_PRIVATE,
            ).all.values.filterIsInstance<String>()
            assertEquals(3, encryptedValues.size)
            assertTrue(encryptedValues.all { it.startsWith("v1:") })
            assertFalse(encryptedValues.any { it.contains(credentials.accessToken) })
        } finally {
            store.clear()
        }
    }
}
