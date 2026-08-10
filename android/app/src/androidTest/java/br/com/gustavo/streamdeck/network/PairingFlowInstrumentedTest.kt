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
            val fields = waitForFields()
            fields[0].setText(serverAddress)
            fields[2].setText(pairingCode)
            fields[3].setText(caCertificatePem)
            fields[4].setText(trustCode)
            tapByText("Parear e conectar")
            assertAuthenticatedProfile()
            assertActionFeedback()
            assertEditorSave()
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
            assertTrue(device.wait(Until.hasObject(By.text("Parear e conectar")), TIMEOUT_MS))
            tapByText("Parear e conectar")
            assertAuthenticatedProfile(
                revision = 2,
                shortcutTitle = "Atalho fase 4",
            )
        }
    }

    private fun tapByText(text: String) {
        var target = device.wait(Until.findObject(By.text(text)), TIMEOUT_MS)
        if (target == null || target.visibleBounds.isEmpty) {
            var attempt = 0
            while (
                (target == null || target.visibleBounds.isEmpty) && attempt < 8
            ) {
                // Close the IME only while a text field holds focus.
                if (device.hasObject(By.focused(true))) {
                    device.pressBack()
                    Thread.sleep(300)
                }
                if (attempt == 0) {
                    Thread.sleep(400)
                }
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
                attempt += 1
            }
        }
        checkNotNull(target) { "element '$text' not found after scrolling. Visible: ${visibleNonSensitiveText()}" }
        check(!target.visibleBounds.isEmpty) { "element '$text' not visible after scrolling. Visible: ${visibleNonSensitiveText()}" }
        target.click()
    }

    private fun assertActionFeedback() {
        tapByText("Atalho Ctrl+Shift+S")
        assertTrue(device.wait(Until.hasObject(By.text("Concluído")), TIMEOUT_MS))
        tapByText("Reproduzir/pausar")
        assertTrue(device.wait(Until.hasObject(By.text("Concluído")), TIMEOUT_MS))
    }

    private fun assertEditorSave() {
        tapByText("Editar perfil")
        assertTextVisible("Revisão atual: 1")
        val fields = device.findObjects(By.clazz("android.widget.EditText"))
        assertTrue("editor did not expose editable fields", fields.size >= 9)
        fields[2].clear()
        fields[2].setText("Atalho fase 4")
        tapByText("Salvar perfil")
        assertTextVisible("Perfil salvo na revisão 2")
        assertTextVisible("Atalho fase 4")
        assertTextVisible("Perfil sincronizado na revisão 2")
    }
    private fun waitForFields(): List<androidx.test.uiautomator.UiObject2> {
        assertTrue(device.wait(Until.hasObject(By.clazz("android.widget.EditText")), TIMEOUT_MS))
        repeat(20) {
            val fields = device.findObjects(By.clazz("android.widget.EditText"))
            if (fields.size >= 5) {
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
        assertTextVisible("Perfil sincronizado na revisão $revision")
        assertTextVisible("Página: Principal")
        assertTextVisible(shortcutTitle)
        assertTextVisible("Reproduzir/pausar")
        assertTextVisible("Documentação")
    }

    private fun assertTextVisible(expectedText: String) {
        val found = device.wait(Until.hasObject(By.text(expectedText)), TIMEOUT_MS)
        if (!found) {
            throw AssertionError(
                "Expected '$expectedText'. Visible text: ${visibleNonSensitiveText()}",
            )
        }
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
