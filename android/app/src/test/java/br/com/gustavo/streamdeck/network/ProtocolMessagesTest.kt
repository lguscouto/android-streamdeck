package br.com.gustavo.streamdeck.network

import java.util.UUID
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Test

class ProtocolMessagesTest {
    @Test
    fun `hello autenticado inclui token apenas no payload`() {
        val accessToken = "token-fixture-${UUID.randomUUID()}"
        val message = JSONObject(
            ProtocolMessages.hello(
                clientId = "android-1",
                clientVersion = "0.1.0",
                accessToken = accessToken,
            )
        )

        assertEquals(1, message.getInt("protocol_version"))
        assertEquals("hello", message.getString("type"))
        assertEquals(
            "android-1",
            message.getJSONObject("payload").getString("client_id"),
        )
        assertEquals(
            accessToken,
            message.getJSONObject("payload").getString("access_token"),
        )
        assertFalse(message.toString().contains("?access_token"))
    }

    @Test
    fun `classifica mensagens do servidor`() {
        assertEquals("welcome", ProtocolMessages.messageType("{\"type\":\"welcome\"}"))
        assertEquals("profile_snapshot", ProtocolMessages.messageType("{\"type\":\"profile_snapshot\"}"))
        assertEquals(null, ProtocolMessages.messageType("not-json"))
    }
}
