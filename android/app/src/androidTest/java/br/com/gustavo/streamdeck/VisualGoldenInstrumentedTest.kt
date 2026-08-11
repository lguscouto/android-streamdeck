package br.com.gustavo.streamdeck

import androidx.test.core.app.ActivityScenario
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.uiautomator.By
import androidx.test.uiautomator.UiDevice
import androidx.test.uiautomator.Until
import androidx.test.platform.app.InstrumentationRegistry
import br.com.gustavo.streamdeck.network.EncryptedPairingStore
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith

/** Captures deterministic visual baselines from the real Android surface. */
@RunWith(AndroidJUnit4::class)
class VisualGoldenInstrumentedTest {
    private val timeoutMs = 12_000L

    @Test
    fun captures_pairing_surface_golden() {
        val targetContext = ApplicationProvider.getApplicationContext<android.content.Context>()
        EncryptedPairingStore(targetContext).clear()
        val device = UiDevice.getInstance(InstrumentationRegistry.getInstrumentation())
        ActivityScenario.launch(MainActivity::class.java).use {
            assertTrue(device.wait(Until.hasObject(By.text("Parear e conectar")), timeoutMs))
            val shell = InstrumentationRegistry.getInstrumentation().uiAutomation
            shell.executeShellCommand(
                "screencap -p /sdcard/streamdeck-golden-pairing.png",
            ).close()
        }
    }
}
