---
name: person-vision-memory
description: Use when working on this project's camera person detection, person naming, camera label overlay, or Letta memory-backed visual identity behavior.
---

# Person Vision Memory

This project uses the **Letta agent with OpenAI GPT-4o vision** to identify and remember multiple people through the camera. No local face recognition libraries needed.

## Architecture

```
Camera → VideoImageClassification → "person" detected
  ↓
main.py grabs camera frame as JPEG
  ↓
face_recognition_utils sends frame to Letta agent (multimodal message)
  ↓
AI describes person / matches against known descriptions
  ↓
Match → announce name on UI overlay
No match → ask user "What is their name?" → save name + description
```

## Files

| File | Purpose |
|---|---|
| `python/face_recognition_utils.py` | Vision utils: send images to Letta agent for description/identification |
| `python/person_identity.py` | Multi-person registry backed by Letta `shared_user_memory` block |
| `python/main.py` | Detection handler: grabs frame, runs AI vision pipeline |
| `assets/app.js` | Browser overlay showing person labels |

## Memory Format

```text
- Known people:
  [{"name":"Porya","description":"Male, dark hair, short beard, glasses"}]
```

## Dependencies

```
letta-client
Pillow
```

No dlib, cmake, or C++ build tools needed.
