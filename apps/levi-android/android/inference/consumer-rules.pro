# Keep the JNI entry points; everything else may be shrunk.
-keep class dev.levi.inference.LlamaBridge { *; }
-keep class dev.levi.inference.LlamaBridge$TokenCallback { *; }
