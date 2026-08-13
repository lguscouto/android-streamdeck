package br.com.gustavo.streamdeck.ui.icons

import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.Build
import androidx.compose.material.icons.outlined.DeveloperBoard
import androidx.compose.material.icons.outlined.Memory
import androidx.compose.material.icons.outlined.SkipNext
import org.junit.Assert.assertSame
import org.junit.Test

class CommandIconRegistryTest {
    @Test
    fun `maps essential command identifiers to stable vectors`() {
        assertSame(Icons.Outlined.SkipNext, CommandIconRegistry.iconFor("skip_next"))
        assertSame(Icons.Outlined.DeveloperBoard, CommandIconRegistry.iconFor("cpu"))
        assertSame(Icons.Outlined.Memory, CommandIconRegistry.iconFor("memory"))
        assertSame(Icons.Outlined.DeveloperBoard, CommandIconRegistry.iconFor("gpu"))
    }

    @Test
    fun `unknown identifier falls back without throwing`() {
        assertSame(Icons.Outlined.Build, CommandIconRegistry.iconFor("not-a-command"))
        assertSame(Icons.Outlined.Build, CommandIconRegistry.iconFor(null))
    }
}
