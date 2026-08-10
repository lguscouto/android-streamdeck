package br.com.gustavo.streamdeck

/**
 * Single source of truth for product metadata.
 *
 * Values come from BuildConfig (populated from the Gradle module) so there is a
 * unique source of version/application identity; see app/build.gradle.kts.
 * Test AppMetadataTest guards against drift between Gradle and this object.
 */
object AppMetadata {
    const val PRODUCT_NAME = "Android Stream Deck"

    val APPLICATION_ID: String = BuildConfig.APPLICATION_ID
    val VERSION_CODE: Int = BuildConfig.VERSION_CODE
    val VERSION_NAME: String = BuildConfig.VERSION_NAME

    // Lowercase aliases used by newer call sites; both views read BuildConfig.
    val applicationId: String get() = APPLICATION_ID
    val versionCode: Int get() = VERSION_CODE
    val versionName: String get() = VERSION_NAME
}