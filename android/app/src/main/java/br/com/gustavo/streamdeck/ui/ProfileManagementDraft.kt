package br.com.gustavo.streamdeck.ui

import br.com.gustavo.streamdeck.network.StreamDeckPage
import br.com.gustavo.streamdeck.network.StreamDeckProfileSnapshot

/** Metadata shown by the profile management draft without exposing button actions. */
data class ProfileMetadata(
    val profileId: String,
    val profileName: String,
    val revision: Int,
    val isActive: Boolean,
    val pageCount: Int,
) {
    val id: String get() = profileId
    val name: String get() = profileName
}

data class ManagedProfile(
    val snapshot: StreamDeckProfileSnapshot,
    val isActive: Boolean,
)

enum class ConflictResolution {
    RETRY,
    RELOAD,
    CANCEL,
}

data class ProfileConflict(
    val profileId: String,
    val localRevision: Int,
    val remoteRevision: Int,
    val selectedResolution: ConflictResolution? = null,
)

data class ProfileManagementDraft(
    val profiles: List<ManagedProfile>,
    val conflict: ProfileConflict? = null,
    val lastConflictResolution: ConflictResolution? = null,
) {
    init {
        require(profiles.isNotEmpty()) { "At least one profile is required" }
        require(profiles.count { it.isActive } == 1) {
            "Exactly one profile must be active"
        }
    }

    init {
        require(profiles.map { it.snapshot.profileId }.distinct().size == profiles.size) {
            "Profile identifiers must be unique"
        }
        require(profiles.count { it.isActive } <= 1) {
            "Only one profile may be active"
        }
        profiles.forEach { profile ->
            requireStableId(profile.snapshot.profileId, "Profile identifier")
            validateSnapshot(profile.snapshot)
        }
        val buttonIds = mutableSetOf<String>()
        profiles.forEach { profile ->
            profile.snapshot.pages.forEach { page ->
                page.buttons.forEach { button ->
                    require(buttonIds.add(button.id)) {
                        "Button identifiers must be unique across profiles"
                    }
                }
            }
        }
    }

    fun listProfileMetadata(): List<ProfileMetadata> = profiles.map { profile ->
        ProfileMetadata(
            profileId = profile.snapshot.profileId,
            profileName = profile.snapshot.profileName,
            revision = profile.snapshot.revision,
            isActive = profile.isActive,
            pageCount = profile.snapshot.pages.size,
        )
    }

    fun renameProfile(profileId: String, newName: String): ProfileManagementDraft {
        val normalizedName = normalizedName(newName, "Profile name")
        val index = profiles.indexOfFirst { it.snapshot.profileId == profileId }
        require(index >= 0) { "Profile not found" }
        val updatedProfiles = profiles.toMutableList()
        val current = updatedProfiles[index]
        updatedProfiles[index] = current.copy(
            snapshot = current.snapshot.copy(profileName = normalizedName),
        )
        return copy(profiles = updatedProfiles)
    }

    fun createProfile(
        profileId: String,
        profileName: String,
        initialPage: br.com.gustavo.streamdeck.network.StreamDeckPage,
        revision: Int = 1,
    ): ProfileManagementDraft {
        requireStableId(profileId, "Profile identifier")
        require(profiles.none { it.snapshot.profileId == profileId }) {
            "Profile identifier must be unique"
        }
        require(revision >= 1) { "Profile revision must be positive" }
        val snapshot = StreamDeckProfileSnapshot(
            profileId = profileId,
            profileName = normalizedName(profileName, "Profile name"),
            revision = revision,
            activePage = copyPageWithScopedButtons(initialPage, profileId),
            pages = listOf(copyPageWithScopedButtons(initialPage, profileId)),
        )
        val shouldActivate = profiles.none { it.isActive }
        return copy(
            profiles = profiles + ManagedProfile(snapshot, isActive = shouldActivate),
        )
    }

    fun duplicateProfile(
        sourceProfileId: String,
        newProfileId: String,
        newProfileName: String,
    ): ProfileManagementDraft {
        requireStableId(newProfileId, "Profile identifier")
        require(profiles.none { it.snapshot.profileId == newProfileId }) {
            "Profile identifier must be unique"
        }
        val source = profileAt(sourceProfileId)
        val copiedPages = source.snapshot.pages.map { page ->
            copyPageWithScopedButtons(page, newProfileId)
        }
        val duplicated = source.snapshot.copy(
            profileId = newProfileId,
            profileName = normalizedName(newProfileName, "Profile name"),
            revision = 1,
            activePage = copiedPages.single { it.id == source.snapshot.activePage.id },
            pages = copiedPages,
        )
        return copy(profiles = profiles + ManagedProfile(duplicated, isActive = false))
    }

    fun activateProfile(profileId: String): ProfileManagementDraft {
        require(profiles.any { it.snapshot.profileId == profileId }) { "Profile not found" }
        return copy(
            profiles = profiles.map { profile ->
                profile.copy(isActive = profile.snapshot.profileId == profileId)
            },
        )
    }

    fun deleteProfile(
        profileId: String,
        replacementProfileId: String? = null,
    ): ProfileManagementDraft {
        val deleted = profileAt(profileId)
        require(profiles.size > 1) { "Cannot delete the last profile" }
        if (deleted.isActive) {
            require(!replacementProfileId.isNullOrBlank()) {
                "Active profile deletion requires a replacement"
            }
        }
        replacementProfileId?.let { replacementId ->
            require(replacementId != profileId) { "Replacement profile must differ" }
            require(profiles.any { it.snapshot.profileId == replacementId }) {
                "Replacement profile not found"
            }
        }
        val remaining = profiles.filterNot { it.snapshot.profileId == profileId }
        if (!deleted.isActive) {
            return copy(profiles = remaining)
        }
        val nextActiveId = replacementProfileId
            ?: throw IllegalArgumentException("Active profile deletion requires a replacement")
        return copy(
            profiles = remaining.map { profile ->
                profile.copy(isActive = profile.snapshot.profileId == nextActiveId)
            },
        )
    }

    fun markConflict(
        profileId: String,
        remoteRevision: Int,
    ): ProfileManagementDraft {
        val localRevision = profileAt(profileId).snapshot.revision
        require(remoteRevision >= 1) { "Profile revision must be positive" }
        return copy(
            conflict = ProfileConflict(
                profileId = profileId,
                localRevision = localRevision,
                remoteRevision = remoteRevision,
            ),
            lastConflictResolution = null,
        )
    }

    fun resolveConflict(resolution: ConflictResolution): ProfileManagementDraft {
        val pending = conflict ?: throw IllegalArgumentException("No profile conflict is pending")
        return if (resolution == ConflictResolution.CANCEL) {
            copy(conflict = null, lastConflictResolution = resolution)
        } else {
            copy(
                conflict = pending.copy(selectedResolution = resolution),
                lastConflictResolution = resolution,
            )
        }
    }

    fun createPage(
        profileId: String,
        page: StreamDeckPage,
        order: Int = page.order,
    ): ProfileManagementDraft {
        val profile = profileAt(profileId)
        val currentPages = orderedPages(profile.snapshot.pages)
        require(order in 0..currentPages.size) { "Page order is outside allowed range" }
        require(currentPages.none { it.id == page.id }) { "Page identifier must be unique" }
        val validatedPage = validatePage(page)
        val updatedPages = currentPages.toMutableList().apply {
            add(order, validatedPage)
        }
        return updateProfile(profileId) { snapshot ->
            snapshotWithPages(snapshot, normalizePages(updatedPages))
        }
    }

    fun renamePage(
        profileId: String,
        pageId: String,
        newTitle: String,
    ): ProfileManagementDraft {
        val title = normalizedName(newTitle, "Page title")
        return updateProfile(profileId) { snapshot ->
            val pages = snapshot.pages.map { page ->
                if (page.id == pageId) page.copy(title = title) else page
            }
            require(pages.any { it.id == pageId }) { "Page not found" }
            snapshotWithPages(snapshot, pages)
        }
    }

    fun reorderPage(
        profileId: String,
        pageId: String,
        newOrder: Int,
    ): ProfileManagementDraft {
        val profile = profileAt(profileId)
        val currentPages = orderedPages(profile.snapshot.pages)
        val currentIndex = currentPages.indexOfFirst { it.id == pageId }
        require(currentIndex >= 0) { "Page not found" }
        require(newOrder in currentPages.indices) { "Page order is outside allowed range" }
        val reordered = currentPages.toMutableList().apply {
            add(newOrder, removeAt(currentIndex))
        }
        return updateProfile(profileId) { snapshot ->
            snapshotWithPages(snapshot, normalizePages(reordered))
        }
    }

    fun deletePage(profileId: String, pageId: String): ProfileManagementDraft {
        val profile = profileAt(profileId)
        return deletePage(profileId, pageId, replacementPageId = null)
    }

    fun deletePage(
        profileId: String,
        pageId: String,
        replacementPageId: String?,
    ): ProfileManagementDraft {
        val profile = profileAt(profileId)
        val currentPages = orderedPages(profile.snapshot.pages)
        require(currentPages.size > 1) { "Profile must have at least one page" }
        val deleted = currentPages.singleOrNull { it.id == pageId }
            ?: throw IllegalArgumentException("Page not found")
        if (deleted.id == profile.snapshot.activePage.id) {
            require(!replacementPageId.isNullOrBlank()) {
                "Active page deletion requires a replacement"
            }
        }
        replacementPageId?.let { replacementId ->
            require(replacementId != pageId) { "Replacement page must differ" }
            require(currentPages.any { it.id == replacementId }) {
                "Replacement page not found"
            }
        }
        val remaining = currentPages.filterNot { it.id == pageId }
        val normalized = normalizePages(remaining)
        return updateProfile(profileId) { snapshot ->
            val nextActivePageId = if (snapshot.activePage.id == pageId) {
                replacementPageId
                    ?: throw IllegalArgumentException(
                        "Active page deletion requires a replacement"
                    )
            } else snapshot.activePage.id
            val nextActivePage = normalized.single { it.id == nextActivePageId }
            snapshot.copy(activePage = nextActivePage, pages = normalized)
        }
    }

    private fun updateProfile(
        profileId: String,
        transform: (StreamDeckProfileSnapshot) -> StreamDeckProfileSnapshot,
    ): ProfileManagementDraft {
        val index = profiles.indexOfFirst { it.snapshot.profileId == profileId }
        require(index >= 0) { "Profile not found" }
        val updatedProfiles = profiles.toMutableList()
        val current = updatedProfiles[index]
        updatedProfiles[index] = current.copy(snapshot = transform(current.snapshot))
        return copy(profiles = updatedProfiles)
    }

    private fun profileAt(profileId: String): ManagedProfile = profiles
        .singleOrNull { it.snapshot.profileId == profileId }
        ?: throw IllegalArgumentException("Profile not found")

    companion object {
        fun fromSnapshots(
            snapshots: List<StreamDeckProfileSnapshot>,
            activeProfileId: String? = snapshots.firstOrNull()?.profileId,
        ): ProfileManagementDraft {
            require(snapshots.isNotEmpty()) { "At least one profile is required" }
            require(activeProfileId != null && snapshots.any { it.profileId == activeProfileId }) {
                "Active profile not found"
            }
            return ProfileManagementDraft(
                profiles = snapshots.map { snapshot ->
                    ManagedProfile(
                        snapshot = snapshot,
                        isActive = snapshot.profileId == activeProfileId,
                    )
                },
            )
        }
    }
}

private fun normalizedName(value: String, label: String): String = value.trim()
    .also {
        require(it.isNotEmpty()) { "$label must not be blank" }
        require(it.length <= 120) { "$label is too long" }
    }

private fun orderedPages(pages: List<StreamDeckPage>): List<StreamDeckPage> = pages.sortedBy { it.order }

private fun normalizePages(pages: List<StreamDeckPage>): List<StreamDeckPage> = pages
    .mapIndexed { index, page -> page.copy(order = index) }

private fun copyPageWithScopedButtons(page: StreamDeckPage, scope: String): StreamDeckPage {
    val buttons = page.buttons.map { button ->
        val scopedId = "$scope-${button.id}"
        requireStableId(scopedId, "Button identifier")
        button.copy(id = scopedId)
    }
    return page.copy(buttons = buttons)
}

private fun snapshotWithPages(
    snapshot: StreamDeckProfileSnapshot,
    pages: List<StreamDeckPage>,
): StreamDeckProfileSnapshot {
    val activePage = pages.singleOrNull { it.id == snapshot.activePage.id }
        ?: pages.first()
    return snapshot.copy(activePage = activePage, pages = pages)
}

private fun validateSnapshot(snapshot: StreamDeckProfileSnapshot) {
    require(snapshot.revision >= 1) { "Profile revision must be positive" }
    normalizedName(snapshot.profileName, "Profile name")
    require(snapshot.pages.isNotEmpty()) { "Profile must have at least one page" }
    val pageIds = mutableSetOf<String>()
    val pageOrders = mutableSetOf<Int>()
    snapshot.pages.forEach { page ->
        require(pageIds.add(page.id)) { "Profile page identifiers must be unique" }
        require(pageOrders.add(page.order)) {
            "Profile page orders must be unique"
        }
        validatePage(page)
    }
    require(snapshot.pages.count { it.id == snapshot.activePage.id } == 1) {
        "Profile active page is missing"
    }
}

private fun validatePage(page: StreamDeckPage): StreamDeckPage {
    requireStableId(page.id, "Page identifier")
    require(page.order >= 0) { "Page order must not be negative" }
    val title = normalizedName(page.title, "Page title")
    require(page.rows in 1..64) { "Page rows are outside allowed range" }
    require(page.columns in 1..64) { "Page columns are outside allowed range" }
    require(page.buttons.isNotEmpty()) { "Page must have at least one button" }
    val buttonIds = mutableSetOf<String>()
    val occupiedCells = mutableSetOf<Pair<Int, Int>>()
    page.buttons.forEach { button ->
        requireStableId(button.id, "Button identifier")
        require(buttonIds.add(button.id)) { "Page button identifiers must be unique" }
        require(button.row in 0 until page.rows && button.column in 0 until page.columns) {
            "Button is outside configured grid"
        }
        require(occupiedCells.add(button.row to button.column)) {
            "Grid button positions must be unique"
        }
    }
    return page.copy(title = title)
}

private fun requireStableId(value: String, label: String) {
    require(STABLE_ID.matches(value)) { "$label is not a stable identifier" }
}

private val STABLE_ID = Regex("^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
