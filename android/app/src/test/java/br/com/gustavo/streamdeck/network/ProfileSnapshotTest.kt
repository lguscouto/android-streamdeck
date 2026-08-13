package br.com.gustavo.streamdeck.network

import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertThrows
import org.junit.Test

class ProfileSnapshotTest {
    @Test
    fun `preserves typed action and serializes a complete revision`() {
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
                  "revision": 1,
                  "active_page_id": "main",
                  "pages": [{
                    "id": "main",
                    "title": "Principal",
                    "order": 0,
                    "rows": 1,
                    "columns": 1,
                    "buttons": [{
                      "id": "save",
                      "row": 0,
                      "column": 0,
                      "title": "Salvar",
                      "action": {
                        "type": "hotkey",
                        "modifiers": ["ctrl", "shift"],
                        "key": "S"
                      }
                    }]
                  }]
                }
              }
            }
            """.trimIndent(),
        )

        assertEquals(
            StreamDeckHotkeyAction(listOf("ctrl", "shift"), "S"),
            snapshot.activePage.buttons.single().action,
        )

        val wire = ProfileSnapshotSerializer.toWire(snapshot, revision = 2)
        val profile = JSONObject(wire)
        assertEquals(2, profile.getInt("revision"))
        assertEquals("hotkey", profile.getJSONArray("pages")
            .getJSONObject(0)
            .getJSONArray("buttons")
            .getJSONObject(0)
            .getJSONObject("action")
            .getString("type"))
        assertEquals(
            2,
            ProfileSnapshotParser.parseWireProfile(wire).revision,
        )
    }

    @Test
    fun `rejects unknown action types instead of silently dropping them`() {
        val malformedSnapshot = """
            {
              "protocol_version": 1,
              "type": "profile_snapshot",
              "payload": {"profile": {
                "protocol_version": 1,
                "id": "default",
                "name": "Perfil",
                "revision": 1,
                "active_page_id": "main",
                "pages": [{
                  "id": "main", "title": "Principal", "order": 0,
                  "rows": 1, "columns": 1,
                  "buttons": [{
                    "id": "bad", "row": 0, "column": 0, "title": "Inválido",
                    "action": {"type": "shell", "command": "whoami"}
                  }]
                }]
              }}
            }
        """.trimIndent()

        assertThrows(IllegalArgumentException::class.java) {
            ProfileSnapshotParser.parse(malformedSnapshot)
        }
    }

    @Test
    fun `parses and serializes system info actions`() {
        val snapshot = ProfileSnapshotParser.parse(
            """
            {
              "protocol_version": 1,
              "type": "profile_snapshot",
              "payload": {"profile": {
                "protocol_version": 1,
                "id": "default",
                "name": "Perfil",
                "revision": 1,
                "active_page_id": "main",
                "pages": [{
                  "id": "main", "title": "Principal", "order": 0,
                  "rows": 1, "columns": 1,
                  "buttons": [{
                    "id": "cpu", "row": 0, "column": 0, "title": "CPU & Temp",
                    "action": {"type": "system_info", "target": "cpu"}
                  }]
                }]
              }}
            }
            """.trimIndent(),
        )

        assertEquals(
            StreamDeckSystemInfoAction("cpu"),
            snapshot.activePage.buttons.single().action,
        )

        val wire = ProfileSnapshotSerializer.toWire(snapshot)
        val action = JSONObject(wire)
            .getJSONArray("pages")
            .getJSONObject(0)
            .getJSONArray("buttons")
            .getJSONObject(0)
            .getJSONObject("action")
        assertEquals("system_info", action.getString("type"))
        assertEquals("cpu", action.getString("target"))
    }

    @Test
    fun `parses and serializes gpu system info action`() {
        val snapshot = ProfileSnapshotParser.parse(
            """
            {
              "protocol_version": 1,
              "type": "profile_snapshot",
              "payload": {"profile": {
                "protocol_version": 1,
                "id": "default",
                "name": "Perfil",
                "revision": 1,
                "active_page_id": "main",
                "pages": [{
                  "id": "main", "title": "Principal", "order": 0,
                  "rows": 1, "columns": 1,
                  "buttons": [{
                    "id": "gpu", "row": 0, "column": 0, "title": "GPU & VRAM",
                    "action": {"type": "system_info", "target": "gpu"}
                  }]
                }]
              }}
            }
            """.trimIndent(),
        )

        assertEquals(StreamDeckSystemInfoAction("gpu"), snapshot.activePage.buttons.single().action)
        val action = JSONObject(ProfileSnapshotSerializer.toWire(snapshot))
            .getJSONArray("pages")
            .getJSONObject(0)
            .getJSONArray("buttons")
            .getJSONObject(0)
            .getJSONObject("action")
        assertEquals("gpu", action.getString("target"))
    }

    @Test
    fun `rejects system info target outside the closed catalog`() {
        val malformedSnapshot = """
            {
              "protocol_version": 1,
              "type": "profile_snapshot",
              "payload": {"profile": {
                "protocol_version": 1,
                "id": "default",
                "name": "Perfil",
                "revision": 1,
                "active_page_id": "main",
                "pages": [{
                  "id": "main", "title": "Principal", "order": 0,
                  "rows": 1, "columns": 1,
                  "buttons": [{
                    "id": "bad", "row": 0, "column": 0, "title": "Inválido",
                    "action": {"type": "system_info", "target": "disk"}
                  }]
                }]
              }}
            }
        """.trimIndent()

        assertThrows(IllegalArgumentException::class.java) {
            ProfileSnapshotParser.parse(malformedSnapshot)
        }
    }

    @Test
    fun `rejects padded system info target outside shared contract`() {
        val malformedSnapshot = """
            {
              "protocol_version": 1,
              "type": "profile_snapshot",
              "payload": {"profile": {
                "protocol_version": 1,
                "id": "default",
                "name": "Perfil",
                "revision": 1,
                "active_page_id": "main",
                "pages": [{
                  "id": "main", "title": "Principal", "order": 0,
                  "rows": 1, "columns": 1,
                  "buttons": [{
                    "id": "bad", "row": 0, "column": 0, "title": "Inválido",
                    "action": {"type": "system_info", "target": " cpu "}
                  }]
                }]
              }}
            }
        """.trimIndent()

        assertThrows(IllegalArgumentException::class.java) {
            ProfileSnapshotParser.parse(malformedSnapshot)
        }
    }

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
