package br.com.gustavo.streamdeck.network

import android.content.Context
import androidx.test.core.app.ActivityScenario
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import androidx.test.uiautomator.By
import androidx.test.uiautomator.UiDevice
import androidx.test.uiautomator.Until
import br.com.gustavo.streamdeck.MainActivity
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Assume.assumeTrue
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class PairingFlowInstrumentedTest {
    private val device = UiDevice.getInstance(InstrumentationRegistry.getInstrumentation())
    private val context = InstrumentationRegistry.getInstrumentation().targetContext

    @Test
    fun pairsSynchronizesAndReconnectsWithEncryptedToken() {
        val pairingCode = InstrumentationRegistry.getArguments()
            .getString("pairingCode")
            ?.takeIf { it.isNotBlank() }
            ?: run {
                assumeTrue("requires an explicit ephemeral pairing code", false)
                return
            }
        val store = EncryptedPairingStore(context)
        store.clear()

        ActivityScenario.launch(MainActivity::class.java).use {
            val fields = waitForFields()
            fields.last().setText(pairingCode)
            device.findObject(By.text("Parear e conectar")).click()
            assertAuthenticatedProfile()
        }

        val credentials = store.load()
        assertNotNull(credentials)
        val encryptedValues = context.getSharedPreferences(
            "streamdeck_pairing",
            Context.MODE_PRIVATE,
        ).all.values.filterIsInstance<String>()
        assertEquals(3, encryptedValues.size)
        assertTrue(encryptedValues.all { it.startsWith("v1:") })
        assertFalse(encryptedValues.any { it.contains(pairingCode) })

        ActivityScenario.launch(MainActivity::class.java).use {
            assertTrue(device.wait(Until.hasObject(By.text("Parear e conectar")), TIMEOUT_MS))
            device.findObject(By.text("Parear e conectar")).click()
            assertAuthenticatedProfile()
        }
    }

    private fun waitForFields(): List<androidx.test.uiautomator.UiObject2> {
        assertTrue(device.wait(Until.hasObject(By.clazz("android.widget.EditText")), TIMEOUT_MS))
        repeat(20) {
            val fields = device.findObjects(By.clazz("android.widget.EditText"))
            if (fields.size >= 3) {
                return fields
            }
            Thread.sleep(100)
        }
        error("pairing form did not expose three text fields")
    }

    private fun assertAuthenticatedProfile() {
        assertTrue(device.wait(Until.hasObject(By.text("Conectado")), TIMEOUT_MS))
        assertTrue(device.wait(Until.hasObject(By.text("Servidor autenticado")), TIMEOUT_MS))
        assertTrue(
            device.wait(
                Until.hasObject(By.text("Perfil sincronizado na revisão 1")),
                TIMEOUT_MS,
            ),
        )
    }

    private companion object {
        const val TIMEOUT_MS = 10_000L
    }
}
