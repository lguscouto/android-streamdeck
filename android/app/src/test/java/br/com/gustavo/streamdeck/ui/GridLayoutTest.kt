package br.com.gustavo.streamdeck.ui

import br.com.gustavo.streamdeck.network.StreamDeckButton
import br.com.gustavo.streamdeck.network.StreamDeckPage
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class GridLayoutTest {
    @Test
    fun `creates all configured cells in row major order`() {
        val saveButton = StreamDeckButton(
            id = "save",
            row = 0,
            column = 0,
            title = "Salvar",
            icon = "keyboard",
            color = "#4CAF50",
        )
        val lastButton = StreamDeckButton(
            id = "last",
            row = 4,
            column = 2,
            title = "Último",
            icon = null,
            color = null,
        )
        val page = StreamDeckPage(
            id = "main",
            title = "Principal",
            rows = 5,
            columns = 3,
            buttons = listOf(lastButton, saveButton),
        )

        val cells = GridLayout.cells(page)

        assertEquals(15, cells.size)
        assertEquals(0, cells.first().row)
        assertEquals(0, cells.first().column)
        assertEquals(saveButton, cells.first().button)
        assertEquals(0, cells[1].row)
        assertEquals(1, cells[1].column)
        assertNull(cells[1].button)
        assertEquals(4, cells.last().row)
        assertEquals(2, cells.last().column)
        assertEquals(lastButton, cells.last().button)
    }
}
