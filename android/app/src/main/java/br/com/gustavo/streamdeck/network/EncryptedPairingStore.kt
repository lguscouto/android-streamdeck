package br.com.gustavo.streamdeck.network

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import java.security.GeneralSecurityException
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey

/**
 * Persists pairing credentials encrypted with an AES-GCM key held by Android Keystore.
 *
 * The legacy plaintext keys use this same preference file. On first load after an
 * upgrade, non-encrypted legacy values fail authentication and are deleted.
 */
class EncryptedPairingStore(
    context: Context,
    storageNamespace: String? = null,
) {
    private val preferences = context.applicationContext.getSharedPreferences(
        storageNamespace?.let { "${PREFERENCES_FILE}_$it" } ?: PREFERENCES_FILE,
        Context.MODE_PRIVATE,
    )

    fun load(): PairingCredentials? {
        val serverBaseUrl = decryptPreference(SERVER_BASE_URL_KEY)
        val clientId = decryptPreference(CLIENT_ID_KEY)
        val accessToken = decryptPreference(ACCESS_TOKEN_KEY)
        val caCertificatePem = decryptPreference(CA_CERTIFICATE_PEM_KEY)
        val trustCode = decryptPreference(TRUST_CODE_KEY)
        return PairingCredentials.fromStored(
            serverBaseUrl,
            clientId,
            accessToken,
            caCertificatePem,
            trustCode,
        ).also { credentials ->
            if (credentials == null && (
                    preferences.contains(SERVER_BASE_URL_KEY) ||
                        preferences.contains(CLIENT_ID_KEY) ||
                        preferences.contains(ACCESS_TOKEN_KEY) ||
                        preferences.contains(CA_CERTIFICATE_PEM_KEY) ||
                        preferences.contains(TRUST_CODE_KEY)
                )
            ) {
                clear()
            }
        }
    }

    fun save(credentials: PairingCredentials) {
        val encryptedServerBaseUrl = encrypt(credentials.serverBaseUrl)
        val encryptedClientId = encrypt(credentials.clientId)
        val encryptedToken = encrypt(credentials.accessToken)
        val encryptedCaCertificatePem = encrypt(credentials.tlsTrust.caCertificatePem)
        val encryptedTrustCode = encrypt(credentials.tlsTrust.trustCode)
        check(
            preferences.edit()
                .putString(SERVER_BASE_URL_KEY, encryptedServerBaseUrl)
                .putString(CLIENT_ID_KEY, encryptedClientId)
                .putString(ACCESS_TOKEN_KEY, encryptedToken)
                .putString(CA_CERTIFICATE_PEM_KEY, encryptedCaCertificatePem)
                .putString(TRUST_CODE_KEY, encryptedTrustCode)
                .commit(),
        ) { "Não foi possível persistir o pareamento" }
    }

    fun clear() {
        preferences.edit()
            .remove(SERVER_BASE_URL_KEY)
            .remove(CLIENT_ID_KEY)
            .remove(ACCESS_TOKEN_KEY)
            .remove(CA_CERTIFICATE_PEM_KEY)
            .remove(TRUST_CODE_KEY)
            .apply()
    }

    private fun decryptPreference(key: String): String? {
        val storedValue = preferences.getString(key, null) ?: return null
        return try {
            decrypt(storedValue)
        } catch (_: GeneralSecurityException) {
            clear()
            null
        } catch (_: IllegalArgumentException) {
            clear()
            null
        }
    }

    private fun encrypt(value: String): String {
        val cipher = Cipher.getInstance(TRANSFORMATION)
        cipher.init(Cipher.ENCRYPT_MODE, key())
        return listOf(
            FORMAT_VERSION,
            Base64.encodeToString(cipher.iv, Base64.NO_WRAP),
            Base64.encodeToString(cipher.doFinal(value.toByteArray(Charsets.UTF_8)), Base64.NO_WRAP),
        ).joinToString(SEPARATOR)
    }

    private fun decrypt(encoded: String): String {
        val parts = encoded.split(SEPARATOR)
        require(parts.size == 3 && parts[0] == FORMAT_VERSION) { "Formato inválido" }
        val iv = Base64.decode(parts[1], Base64.NO_WRAP)
        val ciphertext = Base64.decode(parts[2], Base64.NO_WRAP)
        require(iv.isNotEmpty() && ciphertext.isNotEmpty()) { "Dados vazios" }
        val cipher = Cipher.getInstance(TRANSFORMATION)
        cipher.init(Cipher.DECRYPT_MODE, key(), javax.crypto.spec.GCMParameterSpec(GCM_TAG_BITS, iv))
        return cipher.doFinal(ciphertext).toString(Charsets.UTF_8)
    }

    private fun key(): SecretKey {
        val keyStore = KeyStore.getInstance(ANDROID_KEYSTORE).apply { load(null) }
        val existing = keyStore.getKey(KEY_ALIAS, null) as? SecretKey
        if (existing != null) {
            return existing
        }
        return KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, ANDROID_KEYSTORE)
            .apply {
                init(
                    KeyGenParameterSpec.Builder(
                        KEY_ALIAS,
                        KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT,
                    )
                        .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                        .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                        .build(),
                )
            }
            .generateKey()
    }

    private companion object {
        const val PREFERENCES_FILE = "streamdeck_pairing"
        const val SERVER_BASE_URL_KEY = "server_base_url"
        const val CLIENT_ID_KEY = "client_id"
        const val ACCESS_TOKEN_KEY = "access_token"
        const val CA_CERTIFICATE_PEM_KEY = "ca_certificate_pem"
        const val TRUST_CODE_KEY = "trust_code"
        const val ANDROID_KEYSTORE = "AndroidKeyStore"
        const val KEY_ALIAS = "streamdeck.pairing.aes-gcm.v1"
        const val TRANSFORMATION = "AES/GCM/NoPadding"
        const val FORMAT_VERSION = "v1"
        const val SEPARATOR = ":"
        const val GCM_TAG_BITS = 128
    }
}
