package br.com.gustavo.streamdeck.ui.settings

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.Close
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.role
import androidx.compose.ui.semantics.semantics
import br.com.gustavo.streamdeck.ui.theme.CommandShapes
import br.com.gustavo.streamdeck.ui.theme.CommandSpacing

@Composable
fun SettingsScreen(
    preferences: StreamDeckPreferences,
    onPreferencesChange: (StreamDeckPreferences) -> Unit,
    onClose: () -> Unit,
) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(horizontal = CommandSpacing.md, vertical = CommandSpacing.sm),
        verticalArrangement = Arrangement.spacedBy(CommandSpacing.sm),
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text("Configurações", style = MaterialTheme.typography.headlineSmall)
                Text(
                    "Preferências do Command Surface",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            IconButton(onClick = onClose) {
                Icon(Icons.Outlined.Close, contentDescription = "Voltar para o deck")
            }
        }

        SettingsCard(title = "Tema") {
            Text(
                "Escolha a aparência do aplicativo. A opção sistema acompanha o Android.",
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            ThemePreference.entries.forEach { option ->
                ChoiceRow(
                    selected = preferences.theme == option,
                    label = when (option) {
                        ThemePreference.SYSTEM -> "Usar tema do sistema"
                        ThemePreference.DARK -> "Obsidiana escuro"
                        ThemePreference.LIGHT -> "Superfície clara"
                    },
                    onClick = { onPreferencesChange(preferences.copy(theme = option)) },
                )
            }
        }

        SettingsCard(title = "Densidade do deck") {
            Text(
                "Controla espaçamento e áreas de toque das teclas.",
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            DeckDensity.entries.forEach { option ->
                ChoiceRow(
                    selected = preferences.density == option,
                    label = when (option) {
                        DeckDensity.COMPACT -> "Compacta — mais comandos na tela"
                        DeckDensity.COMFORTABLE -> "Confortável — equilíbrio padrão"
                        DeckDensity.SPACIOUS -> "Espaçosa — áreas de toque maiores"
                    },
                    onClick = { onPreferencesChange(preferences.copy(density = option)) },
                )
            }
        }

        SettingsCard(title = "Acessibilidade e feedback") {
            ToggleRow(
                checked = preferences.reduceMotion,
                label = "Reduzir movimento",
                supportingText = "Desativa a animação de pressão das teclas.",
                onCheckedChange = {
                    onPreferencesChange(preferences.copy(reduceMotion = it))
                },
            )
            HorizontalDivider()
            ToggleRow(
                checked = preferences.hapticsEnabled,
                label = "Feedback tátil",
                supportingText = "Vibra brevemente ao pressionar uma tecla.",
                onCheckedChange = {
                    onPreferencesChange(preferences.copy(hapticsEnabled = it))
                },
            )
        }

        Surface(
            modifier = Modifier.fillMaxWidth(),
            shape = CommandShapes.card,
            color = MaterialTheme.colorScheme.surfaceVariant,
        ) {
            Text(
                "As preferências são salvas localmente neste dispositivo e não são enviadas ao servidor.",
                modifier = Modifier.padding(CommandSpacing.sm),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

@Composable
private fun SettingsCard(
    title: String,
    content: @Composable () -> Unit,
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = CommandShapes.card,
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
    ) {
        Column(
            modifier = Modifier.padding(CommandSpacing.md),
            verticalArrangement = Arrangement.spacedBy(CommandSpacing.xs),
        ) {
            Text(title, style = MaterialTheme.typography.titleMedium)
            content()
        }
    }
}

@Composable
private fun ChoiceRow(
    selected: Boolean,
    label: String,
    onClick: () -> Unit,
) {
    Surface(
        modifier = Modifier
            .fillMaxWidth()
            .semantics { role = Role.RadioButton },
        onClick = onClick,
        shape = CommandShapes.card,
        color = if (selected) {
            MaterialTheme.colorScheme.primaryContainer
        } else {
            MaterialTheme.colorScheme.surfaceVariant
        },
    ) {
        Row(
            modifier = Modifier.padding(horizontal = CommandSpacing.xs, vertical = 2.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            RadioButton(selected = selected, onClick = null)
            Text(label, modifier = Modifier.padding(start = CommandSpacing.xs))
        }
    }
}

@Composable
private fun ToggleRow(
    checked: Boolean,
    label: String,
    supportingText: String,
    onCheckedChange: (Boolean) -> Unit,
) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column(modifier = Modifier.weight(1f)) {
            Text(label, style = MaterialTheme.typography.bodyLarge)
            Text(
                supportingText,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
        Switch(checked = checked, onCheckedChange = onCheckedChange)
    }
}
