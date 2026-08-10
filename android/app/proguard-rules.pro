# ProGuard/R8 keep rules for Android Stream Deck release builds.
#
# STATUS: isMinifyEnabled=false today, so R8 is NOT active in the release
# build. This file exists so that enabling minification in the future cannot
# silently break the build with missing keep rules. Review this file AND run
# a release smoke before enabling R8 (see docs/phase-9-delivery.md).

# The application's own model/network classes are referenced reflectively by
# OkHttp/Retrofit-style serializers only where explicit; keep the package root
# as a minimal safety net for Compose/Kotlin metadata.
-keep class br.com.gustavo.streamdeck.** { *; }

# OkHttp 4.x: keep HTTP/WebSocket internals used at runtime.
-keep class okhttp3.** { *; }
-dontwarn okhttp3.**
-dontwarn okio.**

# org.json: no shrinking conversions required when serialization uses toWire().
-keep class org.json.** { *; }

# Kotlin coroutines and Compose runtime metadata.
-keep class kotlin.coroutines.** { *; }
-keepattributes SourceFile,LineNumberTable
-keepattributes *Annotation*