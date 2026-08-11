package br.com.gustavo.streamdeck

import android.app.Activity
import android.content.Context
import android.content.ContextWrapper
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.safeDrawing
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import br.com.gustavo.streamdeck.ui.settings.StreamDeckPreferences
import br.com.gustavo.streamdeck.ui.settings.StreamDeckPreferencesStore
import br.com.gustavo.streamdeck.network.EncryptedPairingStore
import br.com.gustavo.streamdeck.ui.onboarding.CURRENT_ONBOARDING_VERSION
import br.com.gustavo.streamdeck.ui.onboarding.OnboardingDecision
import br.com.gustavo.streamdeck.ui.onboarding.OnboardingPolicy
import br.com.gustavo.streamdeck.ui.onboarding.OnboardingPolicyInput
import br.com.gustavo.streamdeck.ui.onboarding.WelcomeTutorialScreen
import br.com.gustavo.streamdeck.ui.shell.PairingScreen
import br.com.gustavo.streamdeck.ui.theme.StreamDeckTheme

@Composable
fun StreamDeckApp() {
    val context = LocalContext.current
    val storageNamespace = remember(context) {
        if (BuildConfig.DEBUG) {
            context.findActivity()?.intent?.getStringExtra(
                MainActivity.TEST_STORAGE_NAMESPACE_EXTRA,
            )
        } else {
            null
        }
    }
    val preferencesStore = remember(context, storageNamespace) {
        StreamDeckPreferencesStore(context, storageNamespace)
    }
    val pairingStore = remember(context, storageNamespace) {
        EncryptedPairingStore(context, storageNamespace)
    }
    val hasExistingCredential = remember(pairingStore) { pairingStore.load() != null }
    var preferences by remember(preferencesStore) {
        mutableStateOf<StreamDeckPreferences>(preferencesStore.load())
    }
    var showTutorial by remember(preferencesStore, hasExistingCredential) {
        mutableStateOf(
            OnboardingPolicy.decide(
                OnboardingPolicyInput(
                    onboardingVersion = preferences.onboardingVersion,
                    hasExistingCredential = hasExistingCredential,
                ),
            ) == OnboardingDecision.SHOW,
        )
    }

    LaunchedEffect(hasExistingCredential, preferences.onboardingVersion) {
        if (
            hasExistingCredential &&
            preferences.onboardingVersion < CURRENT_ONBOARDING_VERSION
        ) {
            val updated = preferences.copy(onboardingVersion = CURRENT_ONBOARDING_VERSION)
            preferences = updated
            preferencesStore.save(updated)
        }
    }

    fun finishTutorial() {
        val updated = preferences.copy(onboardingVersion = CURRENT_ONBOARDING_VERSION)
        preferences = updated
        preferencesStore.save(updated)
        showTutorial = false
    }

    StreamDeckTheme(themePreference = preferences.theme) {
        Surface(
            modifier = Modifier
                .fillMaxSize()
                .windowInsetsPadding(WindowInsets.safeDrawing),
            color = MaterialTheme.colorScheme.background,
        ) {
            Box(modifier = Modifier.fillMaxSize()) {
                PairingScreen(
                    preferences = preferences,
                    storageNamespace = storageNamespace,
                    onPreferencesChange = { updated ->
                        preferences = updated
                        preferencesStore.save(updated)
                    },
                    onShowTutorial = { showTutorial = true },
                )
                if (showTutorial) {
                    WelcomeTutorialScreen(onFinish = ::finishTutorial)
                }
            }
        }
    }
}

private tailrec fun Context.findActivity(): Activity? = when (this) {
    is Activity -> this
    is ContextWrapper -> baseContext.findActivity()
    else -> null
}
