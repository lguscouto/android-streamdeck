package br.com.gustavo.streamdeck.network

import android.content.Context
import android.os.ParcelFileDescriptor
import androidx.test.core.app.ActivityScenario
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import androidx.test.uiautomator.By
import androidx.test.uiautomator.UiDevice
import androidx.test.uiautomator.UiObject2
import androidx.test.uiautomator.Until
import br.com.gustavo.streamdeck.MainActivity
import br.com.gustavo.streamdeck.INSTRUMENTATION_STORAGE_NAMESPACE
import br.com.gustavo.streamdeck.instrumentationActivityIntent
import br.com.gustavo.streamdeck.ui.onboarding.CURRENT_ONBOARDING_VERSION
import br.com.gustavo.streamdeck.ui.settings.StreamDeckPreferences
import br.com.gustavo.streamdeck.ui.settings.StreamDeckPreferencesStore
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.After
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class PairingFlowInstrumentedTest {
    private val device = UiDevice.getInstance(InstrumentationRegistry.getInstrumentation())
    private val context = InstrumentationRegistry.getInstrumentation().targetContext
    private val preferencesStore = StreamDeckPreferencesStore(
        context,
        INSTRUMENTATION_STORAGE_NAMESPACE,
    )
    private val pairingStore = EncryptedPairingStore(
        context,
        INSTRUMENTATION_STORAGE_NAMESPACE,
    )
    private var originalPreferences: StreamDeckPreferences? = null
    private var originalCredentials: PairingCredentials? = null

    @Before
    fun bypassFirstRunTutorialForPairingJourney() {
        originalPreferences = preferencesStore.load()
        originalCredentials = pairingStore.load()
        pairingStore.clear()
        preferencesStore.save(
            checkNotNull(originalPreferences).copy(
                onboardingVersion = CURRENT_ONBOARDING_VERSION,
            ),
        )
    }

    @After
    fun removeGeneratedScreenshots() {
        listOf("pairing", "editor", "deck-main", "deck-secondary", "settings").forEach { name ->
            device.executeShellCommand("rm -f /sdcard/streamdeck-golden-$name.png")
        }
        originalPreferences?.let(preferencesStore::save)
        if (originalCredentials == null) {
            pairingStore.clear()
        } else {
            pairingStore.save(originalCredentials!!)
        }
    }

    @Test
    fun pairsSynchronizesAndReconnectsWithEncryptedToken() {
        val arguments = InstrumentationRegistry.getArguments()
        val fixturePath = arguments.getString("pairingFixturePath")
            ?.takeIf { it.matches(Regex("/data/local/tmp/[a-z0-9-]+\\.json")) }
            ?: error("pairingFixturePath argument is required")
        val shell = InstrumentationRegistry.getInstrumentation().uiAutomation
        val fixture = runCatching {
            val descriptor = shell.executeShellCommand("cat $fixturePath")
            ParcelFileDescriptor.AutoCloseInputStream(descriptor).bufferedReader()
                .use { JSONObject(it.readText()) }
        }.getOrElse { error("pairing fixture could not be read") }
        shell.executeShellCommand("rm -f $fixturePath").close()
        val pairingSecret = fixture.optString("pairing_secret")
            .takeIf { it.isNotBlank() }
            ?: error("pairing fixture has no temporary secret")
        val serverAddress = fixture.optString("server_address")
            .takeIf { it.isNotBlank() }
            ?: error("pairing fixture has no server address")
        val qrUri = fixture.optString("pairing_qr_uri")
            .takeIf { it.isNotBlank() }
        if (qrUri != null) {
            val qrPayload = PairingQrPayload.parse(qrUri)
            assertTrue("QR server address mismatch", serverAddress == qrPayload.ipv4)
            assertEquals(PairingInput.DEFAULT_PORT, qrPayload.port)
            assertTrue("QR temporary secret mismatch", pairingSecret == qrPayload.pairingSecret)
            assertTrue(
                "QR session binding mismatch",
                PairingProof.sessionIdForSecret(pairingSecret) == qrPayload.sessionId,
            )
        }
        val store = EncryptedPairingStore(
            context,
            INSTRUMENTATION_STORAGE_NAMESPACE,
        )

        ActivityScenario.launch<MainActivity>(instrumentationActivityIntent(context)).use {
            val basicFields = waitForFields(minimum = 2)
            basicFields[0].setText(serverAddress)
            basicFields[1].setText(pairingSecret)
            val fields = waitForFields()
            assertTrue("pairing form must expose only two text fields", fields.size == 2)
            tapByText("Parear e conectar")
            assertAuthenticatedProfile()
            captureScreenshot("deck-main")
            assertTextVisible("Secundária")
            tapByText("Secundária")
            assertTextVisible("Página ativa: Secundária")
            assertTextContains("Secundária · Play/Pause")
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
            "streamdeck_pairing_instrumentation",
            Context.MODE_PRIVATE,
        ).all.values.filterIsInstance<String>()
        assertEquals(5, encryptedValues.size)
        assertTrue(encryptedValues.all { it.startsWith("v1:") })
        assertFalse(encryptedValues.any { it.contains(pairingSecret) })

        ActivityScenario.launch<MainActivity>(instrumentationActivityIntent(context)).use {
            // The reconnect action uses only the encrypted token and stored TLS trust.
            device.swipe(
                device.displayWidth / 2,
                (device.displayHeight * 2) / 3,
                device.displayWidth / 2,
                device.displayHeight / 3,
                40,
            )
            tapByText("Reconectar")
            if (!device.wait(Until.gone(By.text("Desconectado")), 1_500L)) {
                val label = device.wait(
                    Until.findObject(By.text("Reconectar")),
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
                firstControlTitle = "Atalho fase 4",
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
        listOf(
            "Play/Pause",
            "Próxima",
            "Mute",
            "Spotify",
            "Chrome",
            "Volume +",
            "Volume −",
            "Print Screen",
        ).forEach { label ->
            tapByText(label)
            assertTrue(
                "action '$label' did not complete. Visible: ${visibleNonSensitiveText()}",
                device.wait(Until.hasObject(By.text("Concluído")), TIMEOUT_MS),
            )
        }
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
    private fun waitForFields(minimum: Int = 2): List<androidx.test.uiautomator.UiObject2> {
        assertTrue(device.wait(Until.hasObject(By.clazz("android.widget.EditText")), TIMEOUT_MS))
        repeat(20) {
            val fields = device.findObjects(By.clazz("android.widget.EditText"))
            if (fields.size >= minimum) {
                return fields
            }
            Thread.sleep(100)
        }
        error("pairing form did not expose two text fields")
    }

    private fun assertAuthenticatedProfile(
        revision: Int = 1,
        firstControlTitle: String = "Play/Pause",
    ) {
        assertTextVisible("Conectado")
        assertTextVisible("Servidor autenticado")
        assertTextVisible("Controles essenciais")
        assertTextVisible("Principal  ·  r$revision")
        listOf(
            firstControlTitle,
            "Próxima",
            "Mute",
            "Spotify",
            "Chrome",
            "Volume +",
            "Volume −",
            "Print Screen",
        ).forEach(::assertTextVisible)
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
