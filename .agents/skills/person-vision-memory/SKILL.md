---
name: person-vision-memory
description: Use when working on this project's camera person detection, person naming, camera label overlay, or Letta memory-backed visual identity behavior.
---

# Person Vision Memory

Uses the **Letta agent (GPT-4o vision)** with a **visual RAG** approach: saved reference photos of known people are sent alongside new camera frames to the AI for image-to-image comparison.

## How It Works

1. Person detected → camera frame captured as JPEG
2. Load reference photos of ALL known people from `known_faces/` directory
3. Send all reference photos + new photo to AI in one multimodal message
4. AI compares visually → returns name or "UNKNOWN"
5. Unknown person → ask user for name → save photo + name to disk & Letta memory

## Storage

- **Images on disk**: `known_faces/porya.jpg`, `known_faces/haleh.jpg`, ...
- **Metadata in Letta memory**: `[{"name":"Porya","description":"...","image_file":"porya.jpg"}]`

## Files

| File | Purpose |
|---|---|
| `python/face_recognition_utils.py` | Visual RAG: sends reference images + new image to Letta agent |
| `python/person_identity.py` | Multi-person registry: saves images to disk, metadata to Letta memory |
| `python/main.py` | Detection handler & chat flow |
| `python/config.py` | `KNOWN_FACES_DIR` path |

## Dependencies

```
letta-client
Pillow
```

No dlib, cmake, or C++ build tools needed.
