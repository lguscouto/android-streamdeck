package br.com.gustavo.streamdeck.ui.onboarding

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.ArrowBack
import androidx.compose.material.icons.automirrored.outlined.ArrowForward
import androidx.compose.material.icons.automirrored.outlined.VolumeDown
import androidx.compose.material.icons.automirrored.outlined.VolumeOff
import androidx.compose.material.icons.automirrored.outlined.VolumeUp
import androidx.compose.material.icons.outlined.Apps
import androidx.compose.material.icons.outlined.GridView
import androidx.compose.material.icons.outlined.Language
import androidx.compose.material.icons.outlined.Link
import androidx.compose.material.icons.outlined.PlayArrow
import androidx.compose.material.icons.outlined.QrCode2
import androidx.compose.material.icons.outlined.Security
import androidx.compose.material.icons.outlined.Screenshot
import androidx.compose.material.icons.outlined.SkipNext

import androidx.compose.material3.Button
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import br.com.gustavo.streamdeck.R
import br.com.gustavo.streamdeck.ui.icons.CommandIconRegistry
import br.com.gustavo.streamdeck.ui.theme.CommandColors
import br.com.gustavo.streamdeck.ui.theme.CommandShapes
import br.com.gustavo.streamdeck.ui.theme.CommandSpacing

/** First-run tutorial that ends at the existing secure pairing form. */
@Composable
fun WelcomeTutorialScreen(
    onFinish: () -> Unit,
) {
    var page by rememberSaveable { mutableIntStateOf(0) }
    val lastPage = TUTORIAL_PAGES.lastIndex
    val model = TUTORIAL_PAGES[page]
    val resources = LocalContext.current.resources

    BackHandler {
        if (page > 0) page -= 1 else onFinish()
    }

    Surface(
        modifier = Modifier.fillMaxSize(),
        color = MaterialTheme.colorScheme.background,
    ) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(horizontal = CommandSpacing.md, vertical = CommandSpacing.sm),
            verticalArrangement = Arrangement.spacedBy(CommandSpacing.sm),
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(
                    text = stringResource(R.string.onboarding_brand),
                    modifier = Modifier.weight(1f),
                    style = MaterialTheme.typography.labelLarge,
                    color = MaterialTheme.colorScheme.primary,
                    fontWeight = FontWeight.Bold,
                )
                TextButton(onClick = onFinish) {
                    Text(stringResource(R.string.onboarding_skip))
                }
            }

            Column(
                modifier = Modifier
                    .weight(1f)
                    .fillMaxWidth()
                    .verticalScroll(rememberScrollState()),
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.Center,
            ) {
                TutorialIllustration(page = page)
                Spacer(modifier = Modifier.height(CommandSpacing.md))
                Text(
                    text = stringResource(model.titleRes),
                    style = MaterialTheme.typography.headlineMedium,
                    textAlign = TextAlign.Center,
                    fontWeight = FontWeight.Bold,
                )
                Text(
                    text = stringResource(model.descriptionRes),
                    modifier = Modifier
                        .padding(top = CommandSpacing.xs)
                        .fillMaxWidth(),
                    style = MaterialTheme.typography.bodyLarge,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    textAlign = TextAlign.Center,
                )
                if (page == 1) {
                    PairingSteps()
                }
                if (page == lastPage) {
                    EssentialControlsSummary()
                }
            }

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.Center,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                TUTORIAL_PAGES.indices.forEach { index ->
                    Box(
                        modifier = Modifier
                            .padding(horizontal = 4.dp)
                            .size(if (index == page) 10.dp else 8.dp)
                            .clip(CircleShape)
                            .background(
                                if (index == page) {
                                    MaterialTheme.colorScheme.primary
                                } else {
                                    MaterialTheme.colorScheme.outlineVariant
                                },
                            )
                            .semantics {
                                contentDescription = resources.getString(
                                    R.string.onboarding_page_dot_description,
                                    index + 1,
                                    TUTORIAL_PAGES.size,
                                )
                            },
                    )
                }
            }
            Text(
                text = stringResource(
                    R.string.onboarding_page_indicator,
                    page + 1,
                    TUTORIAL_PAGES.size,
                ),
                modifier = Modifier.fillMaxWidth(),
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                textAlign = TextAlign.Center,
            )

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(CommandSpacing.xs),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                if (page > 0) {
                    OutlinedButton(
                        modifier = Modifier.weight(1f),
                        onClick = { page -= 1 },
                    ) {
                        Icon(Icons.AutoMirrored.Outlined.ArrowBack, contentDescription = null)
                        Spacer(modifier = Modifier.width(CommandSpacing.xs))
                        Text(stringResource(R.string.onboarding_back))
                    }
                }
                val actionLabel = stringResource(
                    if (page == lastPage) {
                        R.string.onboarding_start_pairing
                    } else {
                        R.string.onboarding_next
                    },
                )
                Button(
                    modifier = Modifier
                        .weight(1f)
                        .semantics { contentDescription = actionLabel },
                    onClick = {
                        if (page == lastPage) onFinish() else page += 1
                    },
                ) {
                    Text(actionLabel)
                    if (page < lastPage) {
                        Spacer(modifier = Modifier.width(CommandSpacing.xs))
                        Icon(Icons.AutoMirrored.Outlined.ArrowForward, contentDescription = null)
                    }
                }
            }
        }
    }
}

@Composable
private fun TutorialIllustration(page: Int) {
    when (page) {
        0 -> MiniDeckIllustration()
        1 -> {
            Surface(
                shape = RoundedCornerShape(28.dp),
                color = MaterialTheme.colorScheme.primaryContainer,
                contentColor = MaterialTheme.colorScheme.onPrimaryContainer,
            ) {
                Row(
                    modifier = Modifier.padding(horizontal = 28.dp, vertical = 24.dp),
                    horizontalArrangement = Arrangement.spacedBy(CommandSpacing.md),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Icon(Icons.Outlined.Security, contentDescription = null, modifier = Modifier.size(48.dp))
                    Icon(Icons.Outlined.Link, contentDescription = null, modifier = Modifier.size(32.dp))
                    Icon(Icons.Outlined.QrCode2, contentDescription = null, modifier = Modifier.size(48.dp))
                }
            }
        }
        else -> MiniDeckIllustration()
    }
}

@Composable
private fun MiniDeckIllustration() {
    val icons = listOf(
        "play_pause", "skip_next", "volume_off",
        "spotify", "chrome", "volume_up",
        "volume_down", "screenshot", "empty",
    )
    Surface(
        modifier = Modifier.size(224.dp),
        shape = RoundedCornerShape(28.dp),
        color = CommandColors.Graphite,
        contentColor = CommandColors.Mist,
    ) {
        LazyVerticalGrid(
            columns = GridCells.Fixed(3),
            modifier = Modifier.padding(12.dp),
            userScrollEnabled = false,
            horizontalArrangement = Arrangement.spacedBy(8.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            items(icons) { identifier ->
                val accent = when (identifier) {
                    "spotify" -> CommandColors.Spotify
                    "volume_up", "volume_down" -> CommandColors.Pulse
                    "screenshot" -> CommandColors.Capture
                    "chrome" -> CommandColors.Warning
                    else -> CommandColors.Media
                }
                Surface(
                    modifier = Modifier.size(58.dp),
                    shape = CommandShapes.key,
                    color = CommandColors.Slate,
                    border = androidx.compose.foundation.BorderStroke(1.dp, accent.copy(alpha = 0.78f)),
                ) {
                    if (identifier != "empty") {
                        Icon(
                            imageVector = CommandIconRegistry.iconFor(identifier),
                            contentDescription = null,
                            modifier = Modifier.padding(14.dp),
                            tint = accent,
                        )
                    } else {
                        Icon(
                            imageVector = Icons.Outlined.GridView,
                            contentDescription = null,
                            modifier = Modifier.padding(16.dp),
                            tint = CommandColors.Steel,
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun PairingSteps() {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(top = CommandSpacing.md),
        verticalArrangement = Arrangement.spacedBy(CommandSpacing.xs),
    ) {
        listOf(
            R.string.onboarding_pairing_step_one,
            R.string.onboarding_pairing_step_two,
            R.string.onboarding_pairing_step_three,
        ).forEach { stepRes ->
            Text(
                text = stringResource(stepRes),
                modifier = Modifier.fillMaxWidth(),
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                textAlign = TextAlign.Start,
            )
        }
        Text(
            text = stringResource(R.string.onboarding_private_network),
            modifier = Modifier.padding(top = 2.dp),
            style = MaterialTheme.typography.labelMedium,
            color = MaterialTheme.colorScheme.primary,
        )
    }
}

@Composable
private fun EssentialControlsSummary() {
    val summaryDescription = stringResource(R.string.onboarding_controls_summary)
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(top = CommandSpacing.md)
            .semantics { contentDescription = summaryDescription },
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(CommandSpacing.xs),
    ) {
        Row(
            horizontalArrangement = Arrangement.Center,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            listOf(
                Icons.Outlined.PlayArrow,
                Icons.Outlined.SkipNext,
                Icons.AutoMirrored.Outlined.VolumeOff,
                Icons.AutoMirrored.Outlined.VolumeUp,
                Icons.AutoMirrored.Outlined.VolumeDown,
                Icons.Outlined.Screenshot,
                Icons.Outlined.Apps,
                Icons.Outlined.Language,
            ).forEach { icon ->
                Icon(
                    imageVector = icon,
                    contentDescription = null,
                    modifier = Modifier
                        .padding(horizontal = 3.dp)
                        .size(22.dp),
                    tint = MaterialTheme.colorScheme.primary,
                )
            }
        }
        Text(
            text = stringResource(R.string.onboarding_spotify_note),
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            textAlign = TextAlign.Center,
        )
    }
}
