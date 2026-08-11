package br.com.gustavo.streamdeck.ui.onboarding

import br.com.gustavo.streamdeck.ui.settings.StreamDeckPreferences

/** Version of the first-run onboarding flow understood by this app. */
const val CURRENT_ONBOARDING_VERSION = 1

/** Inputs supplied by the controller without coupling the policy to credential storage. */
data class OnboardingPolicyInput(
    val onboardingVersion: Int = 0,
    val hasExistingCredential: Boolean = false,
    val replayRequested: Boolean = false,
)

enum class OnboardingDecision {
    SHOW,
    SKIP,
    REPLAY,
}

/** Pure first-run policy; persistence and credential lookup stay outside this type. */
object OnboardingPolicy {
    fun decide(
        input: OnboardingPolicyInput,
        currentVersion: Int = CURRENT_ONBOARDING_VERSION,
    ): OnboardingDecision {
        require(currentVersion > 0) { "A versão do onboarding deve ser positiva" }

        if (input.replayRequested) {
            return OnboardingDecision.REPLAY
        }
        if (input.hasExistingCredential) {
            return OnboardingDecision.SKIP
        }
        return if (input.onboardingVersion < currentVersion) {
            OnboardingDecision.SHOW
        } else {
            OnboardingDecision.SKIP
        }
    }

    fun decide(
        preferences: StreamDeckPreferences,
        hasExistingCredential: Boolean = false,
        replayRequested: Boolean = false,
        currentVersion: Int = CURRENT_ONBOARDING_VERSION,
    ): OnboardingDecision = decide(
        input = OnboardingPolicyInput(
            onboardingVersion = preferences.onboardingVersion,
            hasExistingCredential = hasExistingCredential,
            replayRequested = replayRequested,
        ),
        currentVersion = currentVersion,
    )
}
