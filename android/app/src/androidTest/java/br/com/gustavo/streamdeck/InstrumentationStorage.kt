package br.com.gustavo.streamdeck

import android.content.Context
import android.content.Intent

const val INSTRUMENTATION_STORAGE_NAMESPACE = "instrumentation"

fun instrumentationActivityIntent(context: Context): Intent =
    Intent(context, MainActivity::class.java).putExtra(
        MainActivity.TEST_STORAGE_NAMESPACE_EXTRA,
        INSTRUMENTATION_STORAGE_NAMESPACE,
    )