package br.com.gustavo.streamdeck.ui

import br.com.gustavo.streamdeck.network.StreamDeckApplicationAction
import br.com.gustavo.streamdeck.network.StreamDeckButton
import br.com.gustavo.streamdeck.network.StreamDeckHotkeyAction
import br.com.gustavo.streamdeck.network.StreamDeckKeyAction
import br.com.gustavo.streamdeck.network.StreamDeckMediaAction
import br.com.gustavo.streamdeck.network.StreamDeckPage
import br.com.gustavo.streamdeck.network.StreamDeckProfileSnapshot
import br.com.gustavo.streamdeck.network.StreamDeckSystemInfoAction
import br.com.gustavo.streamdeck.network.StreamDeckTextAction
import br.com.gustavo.streamdeck.network.StreamDeckUrlAction
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Test

class ProfileEditorDraftTest {
    @Test
    fun `aplica edicao somente ao botao selecionado e preserva o restante do perfil`() {
        val original = sampleSnapshot()
        val draft = ProfileEditorDraft.from(original).copy(
            profileName = "Perfil editado",
            pageTitle = "Principal editada",
            title = "Texto novo",
            row = "1",
            column = "0",
            icon = "note",
            color = "#112233",
            actionType = EditorActionType.TEXT,
            actionValue = "Mensagem segura",
        )

        val updated = draft.applyTo(original)
        val updatedButton = updated.activePage.buttons.single { it.id == "first" }

        assertEquals("Perfil editado", updated.profileName)
        assertEquals("Principal editada", updated.activePage.title)
        assertEquals("Texto novo", updatedButton.title)
        assertEquals(1, updatedButton.row)
        assertEquals(0, updatedButton.column)
        assertEquals(StreamDeckTextAction("Mensagem segura"), updatedButton.action)
        assertEquals(original.activePage.buttons.single { it.id == "second" },
            updated.activePage.buttons.single { it.id == "second" })
        assertNotEquals(original.profileName, updated.profileName)
    }

    @Test(expected = IllegalArgumentException::class)
    fun `rejeita posicao invalida antes do salvamento`() {
        ProfileEditorDraft.from(sampleSnapshot())
            .copy(row = "99")
            .applyTo(sampleSnapshot())
    }

    @Test
    fun `reverter alteracoes restaura exatamente o registro original`() {
        val original = sampleSnapshot()
        val editedDraft = ProfileEditorDraft.from(original).copy(
            profileName = "Nome errado",
            title = "Titulo errado",
        )

        // Undo = restaurar o draft original e reaplicá-lo reproduz o original.
        val restored = ProfileEditorDraft.from(original).applyTo(original)
        assertEquals(original, restored)
        assertNotEquals(original.profileName, editedDraft.applyTo(original).profileName)
    }

    @Test
    fun `preserva uma acao de telemetria ao editar o botao`() {
        val original = sampleSnapshot().let { snapshot ->
            val button = snapshot.activePage.buttons.first().copy(
                action = StreamDeckSystemInfoAction("memory"),
            )
            snapshot.copy(
                activePage = snapshot.activePage.copy(
                    buttons = listOf(button) + snapshot.activePage.buttons.drop(1),
                ),
            )
        }

        val draft = ProfileEditorDraft.from(original)
        val updated = draft.applyTo(original)

        assertEquals(EditorActionType.SYSTEM_INFO, draft.actionType)
        assertEquals("memory", draft.actionValue)
        assertEquals(
            StreamDeckSystemInfoAction("memory"),
            updated.activePage.buttons.first().action,
        )
    }

    @Test
    fun `preserva e aplica acao de gpu no editor`() {
        val original = sampleSnapshot().let { snapshot ->
            snapshot.copy(
                activePage = snapshot.activePage.copy(
                    buttons = listOf(
                        snapshot.activePage.buttons.first().copy(
                            action = StreamDeckSystemInfoAction("gpu"),
                        ),
                    ),
                ),
            )
        }

        val draft = ProfileEditorDraft.from(original)
        val updated = draft.applyTo(original)

        assertEquals(EditorActionType.SYSTEM_INFO, draft.actionType)
        assertEquals("gpu", draft.actionValue)
        assertEquals(
            StreamDeckSystemInfoAction("gpu"),
            updated.activePage.buttons.first().action,
        )
    }

    private fun sampleSnapshot(): StreamDeckProfileSnapshot {
        val first = StreamDeckButton(
            id = "first",
            row = 0,
            column = 0,
            title = "Atalho",
            icon = null,
            color = null,
            action = StreamDeckHotkeyAction(listOf("ctrl"), "S"),
        )
        val second = StreamDeckButton(
            id = "second",
            row = 0,
            column = 1,
            title = "Tecla",
            icon = "keyboard",
            color = "#445566",
            action = StreamDeckKeyAction("A"),
        )
        return StreamDeckProfileSnapshot(
            profileId = "default",
            profileName = "Perfil",
            revision = 3,
            activePage = StreamDeckPage(
                id = "main",
                title = "Principal",
                rows = 2,
                columns = 2,
                buttons = listOf(first, second),
                order = 0,
            ),
        )
    }
}
