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
            assertActionFeedback()
            assertEditorSave()
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
            assertAuthenticatedProfile(
                revision = 2,
                shortcutTitle = "Atalho fase 4",
            )
        }
    }

    private fun assertActionFeedback() {
        device.findObject(By.text("Atalho Ctrl+Shift+S")).click()
        assertTrue(device.wait(Until.hasObject(By.text("Concluído")), TIMEOUT_MS))
        device.findObject(By.text("Reproduzir/pausar")).click()
        assertTrue(device.wait(Until.hasObject(By.text("Concluído")), TIMEOUT_MS))
    }

    private fun assertEditorSave() {
        device.findObject(By.text("Editar perfil")).click()
        assertTextVisible("Revisão atual: 1")
        val fields = device.findObjects(By.clazz("android.widget.EditText"))
        assertTrue("editor did not expose editable fields", fields.size >= 9)
        fields[2].clear()
        fields[2].setText("Atalho fase 4")
        device.findObject(By.text("Salvar perfil")).click()
        assertTextVisible("Perfil salvo na revisão 2")
        assertTextVisible("Atalho fase 4")
        assertTextVisible("Perfil sincronizado na revisão 2")
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
