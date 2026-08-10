package br.com.gustavo.streamdeck.network

object TestTlsFixture {
    const val TRUST_CODE = "GJBG-GCAM-LAZP-ORC6"

    val CA_PEM = """
        -----BEGIN CERTIFICATE-----
        MIIBYzCCAQqgAwIBAgIUUWpquYS/i2v50e9jLGiZSyM92AIwCgYIKoZIzj0EAwIw
        JjEkMCIGA1UEAwwbQW5kcm9pZCBTdHJlYW0gRGVjayBUZXN0IENBMB4XDTI2MDgx
        MDEwNTYwOVoXDTM2MDgwNzEwNTcwOVowJjEkMCIGA1UEAwwbQW5kcm9pZCBTdHJl
        YW0gRGVjayBUZXN0IENBMFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEO4ob88zl
        gwAazhAx8LvOCkbVOpALBt8N6Ordqwy33XIY50e//o+mSnVeRuFJV0hRFfmHR3Dy
        8TNE1/LQ4dOx7KMWMBQwEgYDVR0TAQH/BAgwBgEB/wIBADAKBggqhkjOPQQDAgNH
        ADBEAiBScyUbP37whD/Ucr+ECXWqiRtyyAGgs4cFtQFvFqGevwIgEmk4OP5UECJw
        eWoraB3HVW7CIuAiYA9EQbxAoqYG2ik=
        -----END CERTIFICATE-----
    """.trimIndent()
}
