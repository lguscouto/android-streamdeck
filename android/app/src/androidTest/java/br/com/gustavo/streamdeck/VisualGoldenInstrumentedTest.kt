package br.com.gustavo.streamdeck

import androidx.test.core.app.ActivityScenario
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.uiautomator.By
import androidx.test.uiautomator.UiDevice
import androidx.test.uiautomator.Until
import androidx.test.platform.app.InstrumentationRegistry
import br.com.gustavo.streamdeck.network.EncryptedPairingStore
import br.com.gustavo.streamdeck.ui.onboarding.CURRENT_ONBOARDING_VERSION
import br.com.gustavo.streamdeck.ui.settings.StreamDeckPreferencesStore
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith

/** Captures a deterministic visual smoke artifact from the real Android surface. */
@RunWith(AndroidJUnit4::class)
class VisualGoldenInstrumentedTest {
    private val timeoutMs = 12_000L

    @Test
    fun captures_pairing_surface_visual_smoke() {
        val targetContext = ApplicationProvider.getApplicationContext<android.content.Context>()
        val pairingStore = EncryptedPairingStore(
            targetContext,
            INSTRUMENTATION_STORAGE_NAMESPACE,
        )
        val preferencesStore = StreamDeckPreferencesStore(
            targetContext,
            INSTRUMENTATION_STORAGE_NAMESPACE,
        )
        val originalPreferences = preferencesStore.load()
        val originalCredentials = pairingStore.load()
        preferencesStore.save(
            originalPreferences.copy(onboardingVersion = CURRENT_ONBOARDING_VERSION),
        )
        pairingStore.clear()
        val device = UiDevice.getInstance(InstrumentationRegistry.getInstrumentation())
        try {
            ActivityScenario.launch<MainActivity>(instrumentationActivityIntent(targetContext)).use {
                assertTrue(device.wait(Until.hasObject(By.text("Parear e conectar")), timeoutMs))
                val shell = InstrumentationRegistry.getInstrumentation().uiAutomation
                shell.executeShellCommand(
                    "screencap -p /sdcard/streamdeck-golden-pairing.png",
                ).close()
            }
        } finally {
            preferencesStore.save(originalPreferences)
            if (originalCredentials == null) pairingStore.clear() else pairingStore.save(originalCredentials)
            device.executeShellCommand("rm -f /sdcard/streamdeck-golden-pairing.png")
        }
    }
}
