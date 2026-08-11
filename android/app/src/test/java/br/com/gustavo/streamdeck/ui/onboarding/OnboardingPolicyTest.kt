package br.com.gustavo.streamdeck.ui.onboarding

import br.com.gustavo.streamdeck.ui.settings.StreamDeckPreferences
import org.junit.Assert.assertEquals
import org.junit.Test

class OnboardingPolicyTest {
    @Test
    fun `estado novo mostra onboarding`() {
        assertEquals(
            OnboardingDecision.SHOW,
            OnboardingPolicy.decide(
                OnboardingPolicyInput(onboardingVersion = 0),
            ),
        )
    }

    @Test
    fun `versao atual ja concluida pula onboarding`() {
        assertEquals(
            OnboardingDecision.SKIP,
            OnboardingPolicy.decide(
                OnboardingPolicyInput(onboardingVersion = CURRENT_ONBOARDING_VERSION),
            ),
        )
    }

    @Test
    fun `versao anterior mostra onboarding atualizado`() {
        assertEquals(
            OnboardingDecision.SHOW,
            OnboardingPolicy.decide(
                OnboardingPolicyInput(onboardingVersion = CURRENT_ONBOARDING_VERSION - 1),
            ),
        )
    }

    @Test
    fun `credencial existente nao interrompe instalacao sem estado de onboarding`() {
        assertEquals(
            OnboardingDecision.SKIP,
            OnboardingPolicy.decide(
                OnboardingPolicyInput(
                    onboardingVersion = 0,
                    hasExistingCredential = true,
                ),
            ),
        )
    }

    @Test
    fun `replay explicito reabre onboarding mesmo quando versao atual foi concluida`() {
        assertEquals(
            OnboardingDecision.REPLAY,
            OnboardingPolicy.decide(
                OnboardingPolicyInput(
                    onboardingVersion = CURRENT_ONBOARDING_VERSION,
                    replayRequested = true,
                ),
            ),
        )
    }

    @Test
    fun `politica usa versao persistida nas preferencias`() {
        assertEquals(
            OnboardingDecision.SHOW,
            OnboardingPolicy.decide(
                preferences = StreamDeckPreferences(onboardingVersion = 0),
            ),
        )
    }

    @Test
    fun `preferencias iniciam com versao de onboarding zero`() {
        assertEquals(0, StreamDeckPreferences().onboardingVersion)
    }
}
