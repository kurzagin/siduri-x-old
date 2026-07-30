# Vision pipeline

OBS is the capture boundary. The local foundation now accepts bounded frame bytes through a fixture-first observation pipeline. It suppresses duplicate frames, can apply in-memory pixel redaction to ordinary 8-bit RGB/RGBA PNG frames before provider processing, treats OCR as untrusted text, and publishes versioned observations with confidence, provider/model metadata, evidence IDs, and expiry. A real OCR/vision provider and configured redaction rectangles remain operator-dependent; raw full-screen persistence is disabled by default.

Automatic triggering uses a separate bounded policy: unchanged frames are suppressed, a minimum interval is enforced, and a rolling per-minute capture budget prevents accidental continuous capture.
