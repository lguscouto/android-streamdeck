package com.antigravity.streamdeck.ui.components

import android.graphics.Color as AndroidColor
import android.os.Build
import androidx.compose.animation.core.*
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.interaction.collectIsPressedAsState
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.scale
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import coil.compose.AsyncImage
import coil.decode.GifDecoder
import coil.decode.ImageDecoderDecoder
import coil.decode.SvgDecoder
import coil.request.ImageRequest
import com.antigravity.streamdeck.data.model.ButtonModel

@Composable
fun DeckButton(
    button: ButtonModel,
    serverIp: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier
) {
    val context = LocalContext.current
    val interactionSource = remember { MutableInteractionSource() }
    val isPressed by interactionSource.collectIsPressedAsState()
    val scale by animateFloatAsState(if (isPressed) 0.90f else 1.0f, label = "buttonScale")

    val currentState = button.state ?: "OFF"
    val stateConfig = button.states?.get(currentState)

    val labelText = stateConfig?.label ?: button.label
    val rawBgColor = stateConfig?.backgroundColor ?: button.backgroundColor ?: "#1E1E2E"
    val rawIconUrl = stateConfig?.iconUrl ?: button.iconUrl

    val baseBgColor = remember(rawBgColor) {
        try {
            Color(AndroidColor.parseColor(rawBgColor))
        } catch (e: Exception) {
            Color(0xFF1E1E2E)
        }
    }

    val infiniteTransition = rememberInfiniteTransition(label = "pulse")
    val pulseAlpha by infiniteTransition.animateFloat(
        initialValue = 0.4f,
        targetValue = 1.0f,
        animationSpec = infiniteRepeatable(
            animation = tween(1000, easing = LinearEasing),
            repeatMode = RepeatMode.Reverse
        ),
        label = "pulseAlpha"
    )

    val isStateOn = currentState == "ON"
    val borderColor = if (isStateOn) Color(0xFF00F0FF).copy(alpha = pulseAlpha) else Color(0x33FFFFFF)
    val borderWidth = if (isStateOn) 2.5.dp else 1.dp

    val fullIconUrl = remember(rawIconUrl, serverIp) {
        if (rawIconUrl == null) null
        else if (rawIconUrl.startsWith("http")) rawIconUrl
        else "http://$serverIp:5000$rawIconUrl"
    }

    val gradientBrush = remember(baseBgColor) {
        Brush.verticalGradient(
            colors = listOf(
                baseBgColor.copy(alpha = 0.95f),
                baseBgColor.copy(alpha = 0.65f)
            )
        )
    }

    val imageRequest = remember(fullIconUrl) {
        if (fullIconUrl == null) null
        else {
            ImageRequest.Builder(context)
                .data(fullIconUrl)
                .decoderFactory(
                    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
                        ImageDecoderDecoder.Factory()
                    } else {
                        GifDecoder.Factory()
                    }
                )
                .decoderFactory(SvgDecoder.Factory())
                .crossfade(true)
                .build()
        }
    }

    val colSpan = button.colSpan ?: 1
    val rowSpan = button.rowSpan ?: 1
    val ratio = colSpan.toFloat() / rowSpan.toFloat()

    Box(
        modifier = modifier
            .scale(scale)
            .aspectRatio(ratio)
            .clip(RoundedCornerShape(16.dp))
            .background(gradientBrush)
            .border(borderWidth, borderColor, RoundedCornerShape(16.dp))
            .clickable(
                interactionSource = interactionSource,
                indication = null,
                onClick = onClick
            )
            .padding(8.dp),
        contentAlignment = Alignment.Center
    ) {
        Column(
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center
        ) {
            if (imageRequest != null) {
                AsyncImage(
                    model = imageRequest,
                    contentDescription = labelText,
                    modifier = Modifier.size(38.dp)
                )
                Spacer(modifier = Modifier.height(4.dp))
            }

            Text(
                text = labelText,
                color = Color.White,
                fontSize = 12.sp,
                fontWeight = FontWeight.Bold,
                textAlign = TextAlign.Center,
                maxLines = 2
            )
        }
    }
}
