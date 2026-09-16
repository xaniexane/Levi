"""LEVI-native static file server — pill-free self-hosting.

``python -m levi.serve`` (or ``levi serve``) serves a static directory over
HTTP with SPA fallback, correct MIME types, and no directory listing.
Stdlib only. Localhost-first: the default bind is 127.0.0.1 and binding
anywhere else prints an honest warning.
"""
