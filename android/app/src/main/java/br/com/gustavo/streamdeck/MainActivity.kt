package br.com.gustavo.streamdeck

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            StreamDeckApp()
        }
    }

    companion object {
        const val TEST_STORAGE_NAMESPACE_EXTRA =
            "br.com.gustavo.streamdeck.extra.TEST_STORAGE_NAMESPACE"
    }
}