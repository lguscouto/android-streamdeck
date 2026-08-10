package br.com.gustavo.streamdeck.network

import android.content.Context
import androidx.test.core.app.ActivityScenario
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import androidx.test.uiautomator.By
import androidx.test.uiautomator.UiDevice
import androidx.test.uiautomator.Until
import br.com.gustavo.streamdeck.MainActivity
import org.junit.Assert.assertTrue
import org.junit.Assume.assumeTrue
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class ProfileManagementInstrumentedTest {
    private val device = UiDevice.getInstance(InstrumentationRegistry.getInstrumentation())
    private val context = InstrumentationRegistry.getInstrumentation().targetContext

    @Test
    fun opensProfileManagementLoadsRemoteProfileAndExportsJson() {
        val pairingCode = InstrumentationRegistry.getArguments()
            .getString("pairingCode")
            ?.takeIf { it.isNotBlank() }
            ?: run {
                assumeTrue("requires an explicit ephemeral pairing code", false)
                return
            }
        EncryptedPairingStore(context).clear()

        ActivityScenario.launch(MainActivity::class.java).use {
            assertTrue(device.wait(Until.hasObject(By.clazz("android.widget.EditText")), TIMEOUT_MS))
            val fields = device.findObjects(By.clazz("android.widget.EditText"))
            assertTrue("pairing form did not expose three text fields", fields.size >= 3)
            fields.last().setText(pairingCode)
            device.findObject(By.text("Parear e conectar")).click()

            assertTrue(device.wait(Until.hasObject(By.text("Gerenciar perfis e páginas")), TIMEOUT_MS))
            device.findObject(By.text("Gerenciar perfis e páginas")).click()
            assertTrue(
                "profile management controls not visible: ${visibleTexts()}",
                device.wait(Until.hasObject(By.text("Perfis")), TIMEOUT_MS),
            )
            assertTrue(device.wait(Until.hasObject(By.textContains("default")), TIMEOUT_MS))
            device.swipe(540, 1700, 540, 500, 20)
            assertTrue(device.wait(Until.hasObject(By.text("Exportar JSON")), TIMEOUT_MS))

            device.findObject(By.text("Exportar JSON")).click()
            device.swipe(540, 500, 540, 1700, 20)
            assertTrue(device.wait(Until.hasObject(By.text("JSON exportado em memória")), TIMEOUT_MS))
        }
    }

    private fun visibleTexts(): String = device
        .findObjects(By.clazz("android.widget.TextView"))
        .mapNotNull { view -> runCatching { view.text?.toString() }.getOrNull() }
        .filter { it.isNotBlank() }
        .joinToString(" | ")

    private companion object {
        const val TIMEOUT_MS = 10_000L
    }
}
