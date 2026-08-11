package br.com.gustavo.streamdeck.network

import android.content.Context
import android.os.ParcelFileDescriptor
import androidx.test.core.app.ActivityScenario
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import androidx.test.uiautomator.By
import androidx.test.uiautomator.UiDevice
import androidx.test.uiautomator.Until
import br.com.gustavo.streamdeck.MainActivity
import br.com.gustavo.streamdeck.instrumentationActivityIntent
import org.json.JSONObject
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class ProfileManagementInstrumentedTest {
    private val device = UiDevice.getInstance(InstrumentationRegistry.getInstrumentation())
    private val context = InstrumentationRegistry.getInstrumentation().targetContext

    @Test
    fun opensProfileManagementLoadsRemoteProfileAndExportsJson() {
        val fixturePath = InstrumentationRegistry.getArguments()
            .getString("pairingFixturePath")
            ?.takeIf { it.matches(Regex("/data/local/tmp/[a-z0-9-]+\\.json")) }
            ?: error("pairingFixturePath argument is required")
        val shell = InstrumentationRegistry.getInstrumentation().uiAutomation
        val fixture = runCatching {
            val descriptor = shell.executeShellCommand("cat $fixturePath")
            ParcelFileDescriptor.AutoCloseInputStream(descriptor).bufferedReader()
                .use { JSONObject(it.readText()) }
        }.getOrElse { error("pairing fixture could not be read") }
        shell.executeShellCommand("rm -f $fixturePath").close()
        val serverAddress = fixture.optString("server_address")
            .takeIf { it.isNotBlank() }
            ?: error("pairing fixture has no server address")
        val pairingSecret = fixture.optString("pairing_secret")
            .takeIf { it.isNotBlank() }
            ?: error("pairing fixture has no temporary secret")

        ActivityScenario.launch<MainActivity>(instrumentationActivityIntent(context)).use {
            assertTrue(device.wait(Until.hasObject(By.clazz("android.widget.EditText")), TIMEOUT_MS))
            val fields = device.findObjects(By.clazz("android.widget.EditText"))
            assertTrue("pairing form did not expose two text fields", fields.size == 2)
            fields[0].setText(serverAddress)
            fields[1].setText(pairingSecret)
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
