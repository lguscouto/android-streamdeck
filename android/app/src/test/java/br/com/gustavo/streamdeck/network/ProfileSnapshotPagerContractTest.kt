package br.com.gustavo.streamdeck.network

import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class ProfileSnapshotPagerContractTest {
    @Test
    fun serializa_e_reconstitui_a_pagina_ativa_sem_perder_as_paginas() {
        val primary = page("main", "Principal", 0, "main-button", "A")
        val secondary = page("secondary", "Secundária", 1, "secondary-button", "B")
        val snapshot = StreamDeckProfileSnapshot(
            profileId = "default",
            profileName = "Perfil",
            revision = 7,
            activePage = secondary,
            pages = listOf(primary, secondary),
        )

        val wire = ProfileSnapshotSerializer.toWire(snapshot, revision = 8)
        val json = JSONObject(wire)
        val parsed = ProfileSnapshotParser.parseWireProfile(wire)

        assertEquals(8, json.getInt("revision"))
        assertEquals("secondary", json.getString("active_page_id"))
        assertEquals(listOf("main", "secondary"), parsed.pages.map { it.id })
        assertEquals("secondary", parsed.activePage.id)
        assertTrue(parsed.activePage.buttons.single().title.startsWith("Secundária"))
    }

    private fun page(
        id: String,
        title: String,
        order: Int,
        buttonId: String,
        key: String,
    ) = StreamDeckPage(
        id = id,
        title = title,
        rows = 1,
        columns = 1,
        order = order,
        buttons = listOf(
            StreamDeckButton(
                id = buttonId,
                row = 0,
                column = 0,
                title = "$title · Atalho",
                icon = "keyboard",
                color = "#38D9C5",
                action = StreamDeckKeyAction(key),
            ),
        ),
    )
}
