package br.com.gustavo.streamdeck.network

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertThrows
import org.junit.Test

class ProfileSnapshotTest {
    @Test
    fun `parses configured grid and preserves button presentation data`() {
        val snapshot = ProfileSnapshotParser.parse(
            """
            {
              "protocol_version": 1,
              "type": "profile_snapshot",
              "payload": {
                "profile": {
                  "protocol_version": 1,
                  "id": "default",
                  "name": "Perfil padrão",
                  "revision": 7,
                  "active_page_id": "main",
                  "pages": [
                    {
                      "id": "main",
                      "title": "Principal",
                      "order": 0,
                      "rows": 5,
                      "columns": 3,
                      "buttons": [
                        {
                          "id": "save-shortcut",
                          "row": 0,
                          "column": 0,
                          "title": "Salvar",
                          "icon": "keyboard",
                          "color": "#4CAF50",
                          "action": {
                            "type": "hotkey",
                            "modifiers": ["ctrl"],
                            "key": "S"
                          }
                        },
                        {
                          "id": "plain-button",
                          "row": 4,
                          "column": 2,
                          "title": "Sem aparência opcional",
                          "action": {
                            "type": "media",
                            "command": "play_pause"
                          }
                        }
                      ]
                    }
                  ]
                }
              }
            }
            """.trimIndent(),
        )

        assertEquals("default", snapshot.profileId)
        assertEquals(7, snapshot.revision)
        assertEquals("Principal", snapshot.activePage.title)
        assertEquals(5, snapshot.activePage.rows)
        assertEquals(3, snapshot.activePage.columns)
        assertEquals(2, snapshot.activePage.buttons.size)
        assertEquals("keyboard", snapshot.activePage.buttons.first().icon)
        assertEquals("#4CAF50", snapshot.activePage.buttons.first().color)
        assertNull(snapshot.activePage.buttons.last().icon)
        assertNull(snapshot.activePage.buttons.last().color)
    }

    @Test
    fun `rejects button outside configured grid`() {
        val malformedSnapshot =
            """
            {
              "protocol_version": 1,
              "type": "profile_snapshot",
              "payload": {
                "profile": {
                  "protocol_version": 1,
                  "id": "default",
                  "name": "Perfil padrão",
                  "revision": 1,
                  "active_page_id": "main",
                  "pages": [
                    {
                      "id": "main",
                      "title": "Principal",
                      "order": 0,
                      "rows": 1,
                      "columns": 1,
                      "buttons": [
                        {
                          "id": "outside",
                          "row": 1,
                          "column": 0,
                          "title": "Inválido",
                          "action": {"type": "hotkey", "modifiers": ["ctrl"], "key": "S"}
                        }
                      ]
                    }
                  ]
                }
              }
            }
            """.trimIndent()

        assertThrows(IllegalArgumentException::class.java) {
            ProfileSnapshotParser.parse(malformedSnapshot)
        }
    }
}
