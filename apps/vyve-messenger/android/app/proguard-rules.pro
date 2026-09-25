# VYVE Messenger — ProGuard / R8 rules (minifyEnabled=true on release).
# Library consumer rules (Retrofit, OkHttp, SQLCipher, Hilt) ship inside
# their own AARs; the rules below cover what they cannot know about.

# --- kotlinx-serialization ---
# @Serializable classes: keep the generated serializers and their fields.
-keepattributes *Annotation*, InnerClasses
-dontnote kotlinx.serialization.AnnotationsKt
-keepclassmembers class kotlinx.serialization.json.** { *; }
-keepclasseswithmembernames class com.cybrus.vyve.** {
    kotlinx.serialization.KSerializer serializer(...);
}
# Keep all @Serializable DTOs in the net layer (field names are the wire contract).
-keep @kotlinx.serialization.Serializable class com.cybrus.vyve.net.** { *; }

# --- Retrofit ---
-keepclasseswithmembers class * {
    @retrofit2.http.* <methods>;
}
-keep class retrofit2.** { *; }
-dontwarn retrofit2.**
# Retrofit 3 response-type keeper (optional; harmless if absent).
-keep class retrofit2.ResponseTypeKeeper { *; }

# --- OkHttp / Okio ---
-dontwarn okhttp3.**
-dontwarn okio.**
-keep class okhttp3.** { *; }

# --- Hilt / Dagger (generated components) ---
-keep class dagger.hilt.** { *; }
-keep class * extends dagger.hilt.internal.GeneratedComponent { *; }

# --- SQLCipher (native) ---
-keep class net.zetetic.database.sqlcipher.** { *; }

# --- Timber ---
-dontwarn org.jetbrains.annotations.**

# --- DataStore / protobuf (kept by its own consumer rules; silence only) ---
-dontwarn androidx.datastore.**

# Remove logging calls below INFO in release builds.
-assumenosideeffects class timber.log.Timber {
    public static *** v(...);
    public static *** d(...);
    public static *** i(...);
}
