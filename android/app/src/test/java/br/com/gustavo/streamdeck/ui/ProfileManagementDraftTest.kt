package br.com.gustavo.streamdeck.ui

import br.com.gustavo.streamdeck.network.StreamDeckButton
import br.com.gustavo.streamdeck.network.StreamDeckHotkeyAction
import br.com.gustavo.streamdeck.network.StreamDeckPage
import br.com.gustavo.streamdeck.network.StreamDeckProfileSnapshot
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Test

class ProfileManagementDraftTest {
    @Test
    fun `lista metadata e renomeia perfil sem perder revisao ou id`() {
        val original = ProfileManagementDraft.fromSnapshots(
            snapshots = listOf(profile("default", "Perfil", revision = 4), profile("work", "Trabalho")),
            activeProfileId = "default",
        )

        assertEquals(
            listOf(
                ProfileMetadata("default", "Perfil", revision = 4, isActive = true, pageCount = 1),
                ProfileMetadata("work", "Trabalho", revision = 1, isActive = false, pageCount = 1),
            ),
            original.listProfileMetadata(),
        )

        val updated = original.renameProfile("default", " Perfil principal ")
        val metadata = updated.listProfileMetadata().first()
        assertEquals("default", metadata.profileId)
        assertEquals("Perfil principal", metadata.profileName)
        assertEquals(4, metadata.revision)
        assertTrue(metadata.isActive)
    }

    @Test
    fun `cria perfil novo com revisao inicial e o perfil existente continua ativo`() {
        val original = ProfileManagementDraft.fromSnapshots(
            snapshots = listOf(profile("default", "Perfil", revision = 4)),
        )

        val updated = original.createProfile(
            profileId = "games",
            profileName = "Jogos",
            initialPage = profile("template", "Template").activePage,
        )

        assertEquals(
            listOf("default", "games"),
            updated.listProfileMetadata().map { it.profileId },
        )
        assertEquals(1, updated.listProfileMetadata().last().revision)
        assertTrue(updated.listProfileMetadata().first().isActive)
        assertEquals("main", updated.profiles.last().snapshot.activePage.id)
    }

    @Test
    fun `duplica perfil com novo id e preserva paginas e botoes`() {
        val original = ProfileManagementDraft.fromSnapshots(
            snapshots = listOf(profile("default", "Perfil", revision = 4)),
        )

        val duplicated = original.duplicateProfile(
            sourceProfileId = "default",
            newProfileId = "copy",
            newProfileName = "Cópia",
        )

        val copy = duplicated.profiles.single { it.snapshot.profileId == "copy" }
        assertEquals(1, copy.snapshot.revision)
        assertEquals("main", copy.snapshot.activePage.id)
        assertEquals("copy-button", copy.snapshot.activePage.buttons.single().id)
        assertTrue(duplicated.listProfileMetadata().single { it.profileId == "default" }.isActive)
    }

    @Test
    fun `ativa e exclui perfil sem deixar dois ativos`() {
        val original = ProfileManagementDraft.fromSnapshots(
            snapshots = listOf(profile("default", "Perfil"), profile("work", "Trabalho")),
            activeProfileId = "default",
        )

        val activated = original.activateProfile("work")
        assertEquals(
            listOf(false, true),
            activated.listProfileMetadata().map { it.isActive },
        )

        val deleted = activated.deleteProfile("work", replacementProfileId = "default")
        assertEquals(listOf("default"), deleted.profiles.map { it.snapshot.profileId })
        assertTrue(deleted.profiles.single().isActive)
    }

    @Test
    fun `nao permite excluir o ultimo perfil nem perfil ativo sem substituto explicito`() {
        val only = ProfileManagementDraft.fromSnapshots(listOf(profile("default", "Perfil")))

        assertThrows(IllegalArgumentException::class.java) {
            only.deleteProfile("default")
        }

        val withReplacement = ProfileManagementDraft.fromSnapshots(
            snapshots = listOf(profile("default", "Perfil"), profile("work", "Trabalho")),
            activeProfileId = "default",
        )
        assertThrows(IllegalArgumentException::class.java) {
            withReplacement.deleteProfile("default")
        }
        val deleted = withReplacement.deleteProfile("default", replacementProfileId = "work")
        assertEquals(listOf("work"), deleted.profiles.map { it.snapshot.profileId })
        assertTrue(deleted.profiles.single().isActive)
    }

    @Test
    fun `cria renomeia reordena e exclui pagina sem perder revisao ou ids`() {
        val originalSnapshot = profile("default", "Perfil", revision = 6)
        val main = originalSnapshot.activePage
        val secondary = main.copy(
            id = "secondary",
            title = "Secundária",
            order = 1,
            buttons = main.buttons.map { it.copy(id = "secondary-button") },
        )
        val original = ProfileManagementDraft.fromSnapshots(
            snapshots = listOf(originalSnapshot.copy(pages = listOf(main, secondary))),
        )

        val third = main.copy(
            id = "third",
            title = "Terceira",
            order = 0,
            buttons = main.buttons.map { it.copy(id = "third-button") },
        )
        val created = original.createPage("default", third, order = 1)
        assertEquals(
            listOf("main", "third", "secondary"),
            created.profiles.single().snapshot.pages.sortedBy { it.order }.map { it.id },
        )

        val renamed = created.renamePage("default", "third", " Página nova ")
        assertEquals(
            "Página nova",
            renamed.profiles.single().snapshot.pages.single { it.id == "third" }.title,
        )

        val reordered = renamed.reorderPage("default", "third", newOrder = 0)
        assertEquals(
            listOf("third", "main", "secondary"),
            reordered.profiles.single().snapshot.pages.sortedBy { it.order }.map { it.id },
        )
        assertEquals(6, reordered.profiles.single().snapshot.revision)

        val deleted = reordered.deletePage("default", "third")
        val result = deleted.profiles.single().snapshot
        assertEquals(listOf("main", "secondary"), result.pages.sortedBy { it.order }.map { it.id })
        assertEquals("main", result.activePage.id)
        assertEquals("secondary-button", result.pages.single { it.id == "secondary" }
            .buttons.single().id)
    }

    @Test
    fun `rejeita ids de pagina duplicados e ordens fora da faixa`() {
        val originalSnapshot = profile("default", "Perfil")
        val original = ProfileManagementDraft.fromSnapshots(listOf(originalSnapshot))
        val duplicateId = originalSnapshot.activePage.copy(order = 0)

        assertThrows(IllegalArgumentException::class.java) {
            original.createPage("default", duplicateId)
        }
        assertThrows(IllegalArgumentException::class.java) {
            original.reorderPage("default", "main", newOrder = 2)
        }
    }

    @Test
    fun `exige escolha explicita para conflito e registra retry reload ou cancel`() {
        val original = ProfileManagementDraft.fromSnapshots(
            snapshots = listOf(profile("default", "Perfil", revision = 4)),
        )

        val conflicted = original.markConflict("default", remoteRevision = 5)
        assertEquals(4, conflicted.conflict?.localRevision)
        assertEquals(5, conflicted.conflict?.remoteRevision)

        val retry = conflicted.resolveConflict(ConflictResolution.RETRY)
        assertEquals(ConflictResolution.RETRY, retry.conflict?.selectedResolution)

        val reload = retry.resolveConflict(ConflictResolution.RELOAD)
        assertEquals(ConflictResolution.RELOAD, reload.conflict?.selectedResolution)

        val cancelled = reload.resolveConflict(ConflictResolution.CANCEL)
        assertNull(cancelled.conflict)
        assertEquals(ConflictResolution.CANCEL, cancelled.lastConflictResolution)
    }

    @Test
    fun `nao resolve conflito sem conflito pendente`() {
        val draft = ProfileManagementDraft.fromSnapshots(listOf(profile("default", "Perfil")))

        assertThrows(IllegalArgumentException::class.java) {
            draft.resolveConflict(ConflictResolution.RETRY)
        }
    }

    @Test
    fun `valida ids revisoes e ordens ao criar o estado`() {
        val valid = profile("default", "Perfil", revision = 2)
        val duplicateOrder = valid.activePage.copy(id = "secondary", order = 0)

        assertThrows(IllegalArgumentException::class.java) {
            ProfileManagementDraft.fromSnapshots(
                snapshots = listOf(valid.copy(pages = listOf(valid.activePage, duplicateOrder))),
            )
        }
        assertThrows(IllegalArgumentException::class.java) {
            ProfileManagementDraft.fromSnapshots(listOf(valid.copy(revision = 0)))
        }
        assertThrows(IllegalArgumentException::class.java) {
            ProfileManagementDraft.fromSnapshots(listOf(valid.copy(profileId = "invalid id")))
        }
    }

    @Test
    fun `rejeita snapshot vazio ativo inexistente e ids de botoes duplicados globalmente`() {
        assertThrows(IllegalArgumentException::class.java) {
            ProfileManagementDraft.fromSnapshots(emptyList())
        }
        assertThrows(IllegalArgumentException::class.java) {
            ProfileManagementDraft.fromSnapshots(
                snapshots = listOf(profile("default", "Perfil")),
                activeProfileId = "missing",
            )
        }

        val duplicateButtonProfile = profile("work", "Trabalho").let { snapshot ->
            snapshot.copy(
                activePage = snapshot.activePage.copy(
                    buttons = snapshot.activePage.buttons.map { it.copy(id = "button") },
                ),
                pages = snapshot.pages.map { page ->
                    page.copy(buttons = page.buttons.map { it.copy(id = "button") })
                },
            )
        }
        assertThrows(IllegalArgumentException::class.java) {
            ProfileManagementDraft.fromSnapshots(
                snapshots = listOf(profile("default", "Perfil"), duplicateButtonProfile),
            )
        }
    }

    @Test
    fun `remove pagina usa a ordem declarada antes de normalizar`() {
        val original = profile("default", "Perfil")
        val first = original.activePage.copy(
            id = "first",
            order = 7,
            buttons = original.activePage.buttons.map { it.copy(id = "first-button") },
        )
        val active = original.activePage.copy(
            id = "active",
            order = 2,
            buttons = original.activePage.buttons.map { it.copy(id = "active-button") },
        )
        val last = original.activePage.copy(
            id = "last",
            order = 20,
            buttons = original.activePage.buttons.map { it.copy(id = "last-button") },
        )
        val draft = ProfileManagementDraft.fromSnapshots(
            listOf(original.copy(activePage = active, pages = listOf(last, active, first)))
        )

        val result = draft.deletePage("default", "active", replacementPageId = "first")
        val pages = result.profiles.single().snapshot.pages
        assertEquals(listOf("first", "last"), pages.map { it.id })
        assertEquals(listOf(0, 1), pages.map { it.order })
        assertEquals("first", result.profiles.single().snapshot.activePage.id)
    }

    @Test
    fun `rejeita ordem negativa na nova pagina`() {
        val original = ProfileManagementDraft.fromSnapshots(listOf(profile("default", "Perfil")))
        val invalid = original.profiles.single().snapshot.activePage.copy(
            id = "secondary",
            order = -1,
            buttons = original.profiles.single().snapshot.activePage.buttons
                .map { it.copy(id = "secondary-button") },
        )

        assertThrows(IllegalArgumentException::class.java) {
            original.createPage("default", invalid)
        }
    }

    private fun profile(
        id: String,
        name: String,
        revision: Int = 1,
    ): StreamDeckProfileSnapshot {
        val page = StreamDeckPage(
            id = "main",
            title = "Principal",
            rows = 1,
            columns = 1,
            buttons = listOf(
                StreamDeckButton(
                    id = if (id == "default") "button" else "$id-button",
                    row = 0,
                    column = 0,
                    title = "Atalho",
                    icon = null,
                    color = null,
                    action = StreamDeckHotkeyAction(listOf("ctrl"), "S"),
                ),
            ),
            order = 0,
        )
        return StreamDeckProfileSnapshot(
            profileId = id,
            profileName = name,
            revision = revision,
            activePage = page,
            pages = listOf(page),
        )
    }
}
