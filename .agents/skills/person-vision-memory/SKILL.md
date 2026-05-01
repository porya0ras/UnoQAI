---
name: person-vision-memory
description: Use when working on this project's camera person detection, person naming, camera label overlay, or Letta memory-backed visual identity behavior.
---

# Person Vision Memory

This project stores the camera person identity in Letta memory, not in local JSON files.

## Current Architecture

- Detection enters through `handle_detections` in `python/main.py`.
- Identity read/write helpers live in `python/person_identity.py`.
- The durable memory block label is `shared_user_memory`.
- The saved memory line format is:

```text
- Camera person identity: NAME
```

Use `save_detected_person_name(name)` to save the visible person's name.
Use `get_known_person_name()` to read it.

## UI Overlay

The Python app sends `classifications` socket messages with entries like:

```json
{"content": "person", "confidence": 0.82, "label": "Haleh"}
```

The browser handles that event in `assets/app.js` and displays the label in the camera overlay defined in `assets/index.html`.

## Important Limitation

The current Arduino `VideoImageClassification` callback reports object classes and confidence only. It does not provide face embeddings, face crops, stable person IDs, or bounding boxes. Treat the feature as "remember the named person when the detector sees a person", not true multi-person face recognition.

To support unknown-vs-known different people, add a face recognition pipeline or camera API that exposes usable face crops/embeddings before changing the memory model.
