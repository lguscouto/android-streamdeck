package br.com.gustavo.streamdeck.ui.icons

import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.MenuBook
import androidx.compose.material.icons.automirrored.outlined.QueueMusic
import androidx.compose.material.icons.automirrored.outlined.VolumeDown
import androidx.compose.material.icons.automirrored.outlined.VolumeOff
import androidx.compose.material.icons.automirrored.outlined.VolumeUp
import androidx.compose.material.icons.outlined.Apps
import androidx.compose.material.icons.outlined.Build
import androidx.compose.material.icons.outlined.DeveloperBoard
import androidx.compose.material.icons.outlined.Keyboard
import androidx.compose.material.icons.outlined.Memory
import androidx.compose.material.icons.outlined.Language
import androidx.compose.material.icons.outlined.MusicNote
import androidx.compose.material.icons.outlined.PlayArrow
import androidx.compose.material.icons.outlined.Screenshot
import androidx.compose.material.icons.outlined.SkipNext
import androidx.compose.ui.graphics.vector.ImageVector

/**
 * Closed mapping between server-provided icon identifiers and tintable vectors.
 *
 * The server controls the identifier, never an arbitrary resource name or image
 * path. Unknown identifiers deliberately fall back to Build so a malformed
 * snapshot cannot crash composition.
 */
object CommandIconRegistry {
    fun iconFor(identifier: String?): ImageVector = when (identifier) {
        "keyboard" -> Icons.Outlined.Keyboard
        "play_pause" -> Icons.Outlined.PlayArrow
        "skip_next" -> Icons.Outlined.SkipNext
        "volume_off", "mute" -> Icons.AutoMirrored.Outlined.VolumeOff
        "volume_up" -> Icons.AutoMirrored.Outlined.VolumeUp
        "volume_down" -> Icons.AutoMirrored.Outlined.VolumeDown
        "screenshot", "print_screen" -> Icons.Outlined.Screenshot
        "spotify" -> Icons.AutoMirrored.Outlined.QueueMusic
        "chrome" -> Icons.Outlined.Language
        "book" -> Icons.AutoMirrored.Outlined.MenuBook
        "media" -> Icons.Outlined.MusicNote
        "application" -> Icons.Outlined.Apps
        "cpu" -> Icons.Outlined.DeveloperBoard
        "memory" -> Icons.Outlined.Memory
        "gpu" -> Icons.Outlined.DeveloperBoard
        else -> Icons.Outlined.Build
    }
}
