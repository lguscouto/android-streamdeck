package br.com.gustavo.streamdeck

import android.content.Context
import androidx.test.core.app.ActivityScenario
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.uiautomator.By
import androidx.test.uiautomator.UiDevice
import androidx.test.uiautomator.UiObject2
import androidx.test.uiautomator.Until
import androidx.test.platform.app.InstrumentationRegistry
import br.com.gustavo.streamdeck.network.EncryptedPairingStore
import br.com.gustavo.streamdeck.ui.onboarding.CURRENT_ONBOARDING_VERSION
import br.com.gustavo.streamdeck.ui.settings.StreamDeckPreferencesStore
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith

/** Verifies the first-run tutorial against the real Compose accessibility tree. */
@RunWith(AndroidJUnit4::class)
class OnboardingFlowInstrumentedTest {
    private val timeoutMs = 12_000L

    @Test
    fun tutorial_reaches_pairing_and_persists_version_without_clearing_app_data() {
        val context = ApplicationProvider.getApplicationContext<Context>()
        val preferencesStore = StreamDeckPreferencesStore(
            context,
            INSTRUMENTATION_STORAGE_NAMESPACE,
        )
        val pairingStore = EncryptedPairingStore(
            context,
            INSTRUMENTATION_STORAGE_NAMESPACE,
        )
        val originalPreferences = preferencesStore.load()
        val originalCredentials = pairingStore.load()
        val device = UiDevice.getInstance(InstrumentationRegistry.getInstrumentation())

        preferencesStore.save(originalPreferences.copy(onboardingVersion = 0))
        pairingStore.clear()
        try {
            ActivityScenario.launch<MainActivity>(instrumentationActivityIntent(context)).use {
                assertTrue(device.wait(Until.hasObject(By.text("Seu PC, a um toque")), timeoutMs))
                clickText(device, "Próximo")
                assertTrue(device.wait(Until.hasObject(By.text("Conecte com segurança")), timeoutMs))
                clickText(device, "Próximo")
                assertTrue(
                    "third onboarding page was not visible: " +
                        visibleNonSensitiveText(device),
                    device.wait(Until.hasObject(By.text("Oito controles prontos")), timeoutMs),
                )
                clickText(device, "Começar pareamento")
                assertTrue(device.wait(Until.hasObject(By.text("Parear e conectar")), timeoutMs))
                assertEquals(
                    CURRENT_ONBOARDING_VERSION,
                    preferencesStore.load().onboardingVersion,
                )
            }
        } finally {
            preferencesStore.save(originalPreferences)
            if (originalCredentials == null) {
                pairingStore.clear()
            } else {
                pairingStore.save(originalCredentials)
            }
        }
    }

    private fun clickText(device: UiDevice, text: String) {
        var target = device.wait(Until.findObject(By.desc(text)), timeoutMs)
            ?: device.wait(Until.findObject(By.text(text)), timeoutMs)
        repeat(8) {
            if (target != null) {
                var clickTarget: UiObject2 = target
                while (!clickTarget.isClickable && clickTarget.parent != null) {
                    clickTarget = clickTarget.parent
                }
                if (clickTarget.isClickable) {
                    clickTarget.click()
                    return
                }
                val bounds = clickTarget.visibleBounds
                if (!bounds.isEmpty) {
                    device.click(bounds.centerX(), bounds.centerY())
                    return
                }
            }
            device.swipe(
                device.displayWidth / 2,
                (device.displayHeight * 3) / 4,
                device.displayWidth / 2,
                device.displayHeight / 4,
                40,
            )
            target = device.wait(Until.findObject(By.text(text)), 1_000L)
        }
        error("element '$text' not found or clickable. Visible: ${visibleNonSensitiveText(device)}")
    }

    private fun visibleNonSensitiveText(device: UiDevice): String = device
        .findObjects(By.clazz("android.widget.TextView"))
        .mapNotNull { node ->
            runCatching { node.text?.toString()?.takeIf { it.isNotBlank() } }
                .getOrNull()
        }
        .joinToString(" | ")
}
