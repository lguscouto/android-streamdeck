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
    fun `press inclui somente identificadores e revisão do snapshot`() {
        val message = JSONObject(
            ProtocolMessages.press(
                requestId = "press-123",
                profileId = "default",
                pageId = "main",
                buttonId = "save-shortcut",
                revision = 7,
            ),
        )

        assertEquals(1, message.getInt("protocol_version"))
        assertEquals("press", message.getString("type"))
        val payload = message.getJSONObject("payload")
        assertEquals("press-123", payload.getString("request_id"))
        assertEquals("default", payload.getString("profile_id"))
        assertEquals("main", payload.getString("page_id"))
        assertEquals("save-shortcut", payload.getString("button_id"))
        assertEquals(7, payload.getInt("revision"))
        assertFalse(message.toString().contains("hotkey"))
        assertFalse(message.toString().contains("command"))
    }

    @Test
    fun `decodifica ack de ação com resultado seguro`() {
        val acknowledgement = ProtocolMessages.actionAcknowledgement(
            """
            {
              "protocol_version": 1,
              "type": "ack",
              "payload": {
                "request_id": "press-123",
                "status": "completed",
                "message": "Action completed"
              }
            }
            """.trimIndent(),
        )

        assertEquals("press-123", acknowledgement?.requestId)
        assertEquals(ActionAcknowledgementStatus.COMPLETED, acknowledgement?.status)
        assertEquals("Action completed", acknowledgement?.message)
    }

    @Test
    fun `classifica mensagens do servidor`() {
        assertEquals("welcome", ProtocolMessages.messageType("{\"type\":\"welcome\"}"))
        assertEquals("profile_snapshot", ProtocolMessages.messageType("{\"type\":\"profile_snapshot\"}"))
        assertEquals(null, ProtocolMessages.messageType("not-json"))
    }
}
