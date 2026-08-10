import java.io.FileInputStream
import java.util.Properties

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
}

// ---------------------------------------------------------------------------
// External release signing (fail-closed). Credentials are read from an untracked
// signing.properties (or STREAMDECK_* environment variables) and NEVER from Git.
// A partial/absent config leaves the release APK unsigned and a dedicated task
// reports/validates that state; the Android Debug keystore is never a substitute.
// ---------------------------------------------------------------------------
val signingProps = Properties()
val signingFile = rootProject.file("release-signing.properties")
val hasSigningFile = signingFile.isFile
if (hasSigningFile) {
    FileInputStream(signingFile).use { signingProps.load(it) }
}

fun outer(name: String): String = System.getenv(name) ?: ""

fun signingValue(prop: String, env: String): String? {
    val fromProps = signingProps.getProperty(prop)?.takeIf { it.isNotBlank() }
    val fromEnv = outer(env).takeIf { it.isNotBlank() }
    return fromProps ?: fromEnv
}

val signingStoreFile = signingValue("storeFile", "STREAMDECK_STORE_FILE")
val signingStorePassword = signingValue("storePassword", "STREAMDECK_STORE_PASSWORD")
val signingKeyAlias = signingValue("keyAlias", "STREAMDECK_KEY_ALIAS")
val signingKeyPassword = signingValue("keyPassword", "STREAMDECK_KEY_PASSWORD")

val signingFields = listOf(
    signingStoreFile,
    signingStorePassword,
    signingKeyAlias,
    signingKeyPassword,
)
val signingComplete = signingFields.all { !it.isNullOrBlank() }
val signingPartial = signingFields.any { !it.isNullOrBlank() } && !signingComplete

if (signingPartial) {
    throw GradleException(
        "release signing configuration is INCOMPLETE. Provide all of storeFile, " +
            "storePassword, keyAlias, keyPassword in an untracked " +
            "release-signing.properties (or STREAMDECK_* env vars), or remove the " +
            "partial entry. Failing closed rather than shipping a misconfigured identity."
    )
}

android {
    namespace = "br.com.gustavo.streamdeck"
    compileSdk = 35
    buildToolsVersion = "35.0.0"

    defaultConfig {
        applicationId = "br.com.gustavo.streamdeck"
        minSdk = 26
        targetSdk = 35
        versionCode = 1
        versionName = "0.1.0"

        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
        vectorDrawables {
            useSupportLibrary = true
        }
    }

    signingConfigs {
        if (signingComplete) {
            create("release") {
                storeFile = file(signingStoreFile!!)
                storePassword = signingStorePassword!!
                keyAlias = signingKeyAlias!!
                keyPassword = signingKeyPassword!!
            }
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            if (signingComplete) {
                signingConfig = signingConfigs.getByName("release")
            }
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro",
            )
        }
    }

    buildFeatures {
        compose = true
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = "17"
    }

    packaging {
        resources {
            excludes += "/META-INF/{AL2.0,LGPL2.1}"
        }
    }
}

tasks.register("printReleaseSigningStatus") {
    doLast {
        if (signingComplete) {
            println("RELEASE_SIGNING=configured")
        } else {
            println("RELEASE_SIGNING=unsigned")
            println("RELEASE_SIGNING_NOTE=No untracked release-signing.properties or STREAMDECK_* vars. The release APK is unsigned and NOT distributable as-is.")
        }
    }
}

dependencies {
    implementation("androidx.activity:activity-compose:1.10.0")
    implementation("androidx.compose.ui:ui:1.8.3")
    implementation("androidx.compose.ui:ui-tooling-preview:1.8.3")
    implementation("androidx.compose.material3:material3:1.3.2")
    implementation("com.squareup.okhttp3:okhttp:4.12.0")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.9.0")

    debugImplementation("androidx.compose.ui:ui-tooling:1.8.3")

    testImplementation("junit:junit:4.13.2")
    testImplementation("org.json:json:20240303")

    androidTestImplementation("androidx.test:core:1.6.1")
    androidTestImplementation("androidx.test.ext:junit:1.2.1")
    androidTestImplementation("androidx.test:runner:1.6.2")
    androidTestImplementation("androidx.test.uiautomator:uiautomator:2.3.0")
}
