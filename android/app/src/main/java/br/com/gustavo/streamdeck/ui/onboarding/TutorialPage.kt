package br.com.gustavo.streamdeck.ui.onboarding

import br.com.gustavo.streamdeck.R

internal data class TutorialPage(
    val titleRes: Int,
    val descriptionRes: Int,
)

internal val TUTORIAL_PAGES = listOf(
    TutorialPage(
        titleRes = R.string.onboarding_page_one_title,
        descriptionRes = R.string.onboarding_page_one_description,
    ),
    TutorialPage(
        titleRes = R.string.onboarding_page_two_title,
        descriptionRes = R.string.onboarding_page_two_description,
    ),
    TutorialPage(
        titleRes = R.string.onboarding_page_three_title,
        descriptionRes = R.string.onboarding_page_three_description,
    ),
)
