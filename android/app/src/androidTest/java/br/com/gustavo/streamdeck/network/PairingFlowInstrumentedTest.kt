package br.com.gustavo.streamdeck.network

import android.content.Context
import android.util.Base64
import androidx.test.core.app.ActivityScenario
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import androidx.test.uiautomator.By
import androidx.test.uiautomator.UiDevice
import androidx.test.uiautomator.UiObject2
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
        val arguments = InstrumentationRegistry.getArguments()
        val pairingCode = arguments.getString("pairingCode")?.takeIf { it.isNotBlank() }
        val serverAddress = arguments.getString("serverAddress")?.takeIf { it.isNotBlank() }
        val trustCode = arguments.getString("trustCode")?.takeIf { it.isNotBlank() }
        val caCertificatePem = arguments.getString("caPemBase64")
            ?.takeIf { it.isNotBlank() }
            ?.let { encoded ->
                Base64.decode(encoded, Base64.DEFAULT)
                    .decodeToString()
                    .replace("\r", "")
                    .replace("\n", "")
            }
        assumeTrue(
            "requires explicit HTTPS endpoint, private CA and pairing code",
            pairingCode != null &&
                serverAddress != null &&
                trustCode != null &&
                caCertificatePem != null,
        )
        requireNotNull(pairingCode)
        requireNotNull(serverAddress)
        requireNotNull(trustCode)
        requireNotNull(caCertificatePem)
        val store = EncryptedPairingStore(context)
        store.clear()

        ActivityScenario.launch(MainActivity::class.java).use {
            val basicFields = waitForFields(minimum = 3)
            basicFields[0].setText(serverAddress)
            basicFields[2].setText(pairingCode)
            tapByText("Exibir")
            val fields = waitForFields()
            fields[3].setText(caCertificatePem)
            fields[4].setText(trustCode)
            tapByText("Parear e conectar")
            assertAuthenticatedProfile()
            captureScreenshot("deck-main")
            assertTextVisible("Secundária")
            tapByText("Secundária")
            assertTextVisible("Página ativa: Secundária")
            assertTextContains("Secundária · Atalho Ctrl+Shift+S")
            captureScreenshot("deck-secondary")
            tapByText("Principal")
            assertTextVisible("Página ativa: Principal")
            assertActionFeedback()
            assertEditorSave()
            captureSettingsScreenshot()
        }

        val credentials = store.load()
        assertNotNull(credentials)
        val encryptedValues = context.getSharedPreferences(
            "streamdeck_pairing",
            Context.MODE_PRIVATE,
        ).all.values.filterIsInstance<String>()
        assertEquals(5, encryptedValues.size)
        assertTrue(encryptedValues.all { it.startsWith("v1:") })
        assertFalse(encryptedValues.any { it.contains(pairingCode) })
        assertFalse(encryptedValues.any { it.contains(caCertificatePem) })
        assertFalse(encryptedValues.any { it.contains(trustCode) })

        ActivityScenario.launch(MainActivity::class.java).use {
            // Restored TLS material makes the form taller; move the reconnect
            // button away from the edge-to-edge navigation area before tapping.
            device.swipe(
                device.displayWidth / 2,
                (device.displayHeight * 2) / 3,
                device.displayWidth / 2,
                device.displayHeight / 3,
                40,
            )
            tapByText("Parear e conectar")
            if (!device.wait(Until.gone(By.text("Desconectado")), 1_500L)) {
                val label = device.wait(
                    Until.findObject(By.text("Parear e conectar")),
                    TIMEOUT_MS,
                )
                var reconnectButton = checkNotNull(label) {
                    "reconnect button was not found for shell fallback"
                }
                while (!reconnectButton.isClickable && reconnectButton.parent != null) {
                    reconnectButton = reconnectButton.parent
                }
                val bounds = reconnectButton.visibleBounds
                device.executeShellCommand(
                    "input tap ${bounds.centerX()} ${bounds.centerY()}",
                )
            }
            assertAuthenticatedProfile(
                revision = 4,
                shortcutTitle = "Atalho fase 4",
            )
        }
    }

    private fun tapByText(text: String) {
        // The IME overlays the lower half of the screen (edge-to-edge insets);
        // a visible button there is a no-op tap while the keyboard is open. ESC
        // (keyevent 111) closes the IME without navigating back, so it is safe.
        runCatching { device.executeShellCommand("input keyevent 111") }
        Thread.sleep(300)
        fun findTextNode(): UiObject2? = device
            .findObjects(By.clazz("android.widget.TextView"))
            .firstOrNull { node ->
                runCatching { node.text?.toString()?.contains(text) == true }
                    .getOrDefault(false)
            }
        var target = device.wait(Until.findObject(By.text(text)), TIMEOUT_MS)
            ?: findTextNode()
        if (target == null || target.visibleBounds.isEmpty) {
            var attempt = 0
            while (
                (target == null || target.visibleBounds.isEmpty) && attempt < 8
            ) {
                // Manual swipe up (content moves up) — reliable even when the
                // first By.scrollable node is a horizontal action row.
                device.swipe(
                    device.displayWidth / 2,
                    (device.displayHeight * 3) / 4,
                    device.displayWidth / 2,
                    device.displayHeight / 4,
                    50,
                )
                target = device.wait(Until.findObject(By.text(text)), 2_000L)
                    ?: findTextNode()
                attempt += 1
            }
        }
        val resolvedTarget = checkNotNull(target) {
            "element '$text' not found after scrolling. Visible: ${visibleNonSensitiveText()}"
        }
        check(!resolvedTarget.visibleBounds.isEmpty) {
            "element '$text' not visible after scrolling. Visible: ${visibleNonSensitiveText()}"
        }
        var clickTarget = resolvedTarget
        while (!clickTarget.isClickable && clickTarget.parent != null) {
            clickTarget = clickTarget.parent
        }
        check(clickTarget.isClickable) {
            "element '$text' has no clickable ancestor"
        }
        clickTarget.click()
    }

    private fun assertActionFeedback() {
        tapByText("Atalho Ctrl+Shift+S")
        assertTrue(
            "hotkey action did not complete. Visible: ${visibleNonSensitiveText()}",
            device.wait(Until.hasObject(By.text("Concluído")), TIMEOUT_MS),
        )
        tapByText("Reproduzir/pausar")
        assertTrue(
            "media action did not complete. Visible: ${visibleNonSensitiveText()}",
            device.wait(Until.hasObject(By.text("Concluído")), TIMEOUT_MS),
        )
    }

    private fun assertEditorSave() {
        tapByDescription("Abrir ações do deck")
        tapByText("Editar deck")
        assertTextVisible("Revisão 3 · Principal")
        captureScreenshot("editor")
        val fields = device.findObjects(By.clazz("android.widget.EditText"))
        assertTrue("editor did not expose the title field", fields.size >= 3)
        fields[2].clear()
        fields[2].setText("Atalho fase 4")

        // tapByText closes the IME before locating the bottom action. Submit once:
        // a retry here can race the navigation transition and duplicate the
        // optimistic profile mutation.
        tapByText("Salvar alterações")
        assertTrue(
            "save did not transition to revision 4. Visible: ${visibleNonSensitiveText()}",
            device.wait(Until.hasObject(By.text("Perfil salvo na revisão 4")), TIMEOUT_MS),
        )
        assertTextVisible("Atalho fase 4")
        assertTextVisible("Principal  ·  r4")
    }
    private fun waitForFields(minimum: Int = 5): List<androidx.test.uiautomator.UiObject2> {
        assertTrue(device.wait(Until.hasObject(By.clazz("android.widget.EditText")), TIMEOUT_MS))
        repeat(20) {
            val fields = device.findObjects(By.clazz("android.widget.EditText"))
            if (fields.size >= minimum) {
                return fields
            }
            Thread.sleep(100)
        }
        error("pairing form did not expose five text fields")
    }

    private fun assertAuthenticatedProfile(
        revision: Int = 1,
        shortcutTitle: String = "Atalho Ctrl+Shift+S",
    ) {
        assertTextVisible("Conectado")
        assertTextVisible("Servidor autenticado")
        assertTextVisible("Principal  ·  r$revision")
        assertTextVisible("Principal")
        assertTextVisible(shortcutTitle)
        assertTextVisible("Reproduzir/pausar")
        assertTextVisible("Documentação")
    }

    private fun captureSettingsScreenshot() {
        tapByDescription("Abrir ações do deck")
        tapByText("Configurações")
        assertTextVisible("Configurações")
        captureScreenshot("settings")
        tapByDescription("Voltar para o deck")
    }

    private fun tapByDescription(description: String) {
        val target = device.wait(Until.findObject(By.desc(description)), TIMEOUT_MS)
        checkNotNull(target) { "element with description '$description' was not found" }
        var clickTarget = target
        while (!clickTarget.isClickable && clickTarget.parent != null) {
            clickTarget = clickTarget.parent
        }
        check(clickTarget.isClickable) {
            "element with description '$description' has no clickable ancestor"
        }
        clickTarget.click()
    }

    private fun captureScreenshot(name: String) {
        val shell = InstrumentationRegistry.getInstrumentation().uiAutomation
        shell.executeShellCommand(
            "screencap -p /sdcard/streamdeck-golden-$name.png",
        ).close()
    }

    private fun assertTextVisible(expectedText: String) {
        val found = device.wait(Until.hasObject(By.text(expectedText)), TIMEOUT_MS)
        if (!found) {
            throw AssertionError(
                "Expected '$expectedText'. Visible text: ${visibleNonSensitiveText()}",
            )
        }
    }

    private fun assertTextContains(expectedText: String) {
        repeat(20) {
            if (visibleNonSensitiveText().contains(expectedText)) {
                return
            }
            Thread.sleep(100)
        }
        throw AssertionError(
            "Expected visible text containing '$expectedText'. Visible text: ${visibleNonSensitiveText()}",
        )
    }

    private fun visibleNonSensitiveText(): String = device
        .findObjects(By.clazz("android.widget.TextView"))
        .mapNotNull { textView ->
            runCatching { textView.text?.toString()?.takeIf { it.isNotBlank() } }
                .getOrNull()
        }
        .joinToString(separator = " | ")

    private companion object {
        const val TIMEOUT_MS = 10_000L
    }
}
