package br.com.gustavo.streamdeck.ui.theme

import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Shapes
import androidx.compose.ui.unit.dp

object CommandShapes {
    val key = RoundedCornerShape(18.dp)
    val card = RoundedCornerShape(16.dp)
    val field = RoundedCornerShape(12.dp)
    val pill = RoundedCornerShape(50)
}

val CommandShapeScheme = Shapes(
    extraSmall = RoundedCornerShape(8.dp),
    small = RoundedCornerShape(12.dp),
    medium = CommandShapes.card,
    large = RoundedCornerShape(24.dp),
    extraLarge = RoundedCornerShape(28.dp),
)
