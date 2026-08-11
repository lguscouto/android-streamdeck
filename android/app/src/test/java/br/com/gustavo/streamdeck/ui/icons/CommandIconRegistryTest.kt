package br.com.gustavo.streamdeck.ui.icons

import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.Build
import androidx.compose.material.icons.outlined.SkipNext
import org.junit.Assert.assertSame
import org.junit.Test

class CommandIconRegistryTest {
    @Test
    fun `maps essential command identifiers to stable vectors`() {
        assertSame(Icons.Outlined.SkipNext, CommandIconRegistry.iconFor("skip_next"))
    }

    @Test
    fun `unknown identifier falls back without throwing`() {
        assertSame(Icons.Outlined.Build, CommandIconRegistry.iconFor("not-a-command"))
        assertSame(Icons.Outlined.Build, CommandIconRegistry.iconFor(null))
    }
}
