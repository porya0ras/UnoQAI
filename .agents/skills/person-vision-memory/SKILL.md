---
name: person-vision-memory
description: Use when working on this project's camera person detection, person naming, camera label overlay, or Letta memory-backed visual identity behavior.
---

# Person Vision Memory

This project uses **face_recognition** (dlib-backed, 128-d face embeddings) combined with **Letta shared memory** to identify and remember multiple people through the camera.

## Architecture

```
Camera → VideoImageClassification → "person" detected
  ↓
main.py grabs camera frame → face_recognition_utils encodes face
  ↓
Compare encoding against known people stored in Letta memory
  ↓
Match found → announce name on UI overlay
No match   → ask user "What is their name?" → save name + encoding
```

## Files

| File | Purpose |
|---|---|
| `python/face_recognition_utils.py` | Pure utilities: encode face from JPEG, compare against known encodings |
| `python/person_identity.py` | Multi-person registry backed by Letta `shared_user_memory` block |
| `python/main.py` | Detection handler: grabs frame, runs face pipeline, manages ask/announce flow |
| `python/config.py` | `FACE_MATCH_THRESHOLD` (default 0.6) |
| `assets/app.js` | Browser overlay showing person labels |

## Memory Format

The durable memory block label is `shared_user_memory`. Known people are stored as:

```text
- Known people:
  [{"name":"Porya","encoding":[0.012,-0.034,...]},{"name":"Haleh","encoding":[...]}]
```

Each encoding is a 128-float array (face_recognition standard). Rounded to 4 decimal places to save space.

## Key Functions

### face_recognition_utils.py
- `is_available()` — True when face_recognition + Pillow are installed
- `encode_face_from_jpeg(jpeg_bytes)` — Extract 128-d encoding from JPEG
- `find_best_match(unknown_encoding, known_people)` — Cosine/Euclidean match

### person_identity.py
- `get_known_people()` — Read list of known people from Letta memory (cached)
- `save_detected_person(name, encoding)` — Save name + encoding to Letta memory
- `is_waiting_for_name()` / `get_pending_encoding()` — Track the ask-flow state
- `should_ask_for_person_name()` / `should_announce_known_person(name)` — Cooldown logic
- `extract_person_name(message)` — Parse user's reply for a name

## UI Overlay

The Python app sends `classifications` socket messages with entries like:

```json
{"content": "person", "confidence": 0.82, "label": "Porya"}
```

Multiple persons are supported — the overlay joins labels with `·`.

## Graceful Degradation

If `face_recognition` is not installed (e.g., missing dlib/cmake), the system falls back to the ask-once-and-remember behaviour without face matching. The `is_available()` check gates all face processing.

## Dependencies

```
face_recognition
numpy
Pillow
```

> **Note:** `face_recognition` requires `dlib`, which needs `cmake` and C++ build tools. Install with:
> ```bash
> sudo apt install cmake build-essential
> pip install face_recognition
> ```
