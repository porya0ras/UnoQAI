"""
Person identity management backed by Letta shared memory + image files on disk.

Each known person is stored with:
- name: their name
- description: AI-generated text description of their appearance
- image_file: filename of their reference photo in known_faces/

The Letta shared_user_memory block stores the compact JSON metadata.
The actual images live on disk in KNOWN_FACES_DIR.
"""

import json
import re
import time
import threading

from config import letta_client
from letta_messaging import get_agents

# ── Constants ────────────────────────────────────────────────────────────────

ASK_COOLDOWN_SECONDS = 120
ANNOUNCE_COOLDOWN_SECONDS = 30
CACHE_SECONDS = 10
SHARED_MEMORY_LABEL = "shared_user_memory"
KNOWN_PEOPLE_MARKER = "Known people:"

# ── Module-level state ───────────────────────────────────────────────────────

state = {
    "pending_name": False,
    "pending_description": None,
    "pending_jpeg": None,
    "last_ask_at": 0.0,
    "last_announce_at": {},
    "known_people_cache": None,
    "last_cache_at": 0.0,
}
_state_lock = threading.Lock()

# ── Letta memory I/O ─────────────────────────────────────────────────────────

def get_shared_memory_value() -> str:
    main_agent_id, _ = get_agents()
    block = letta_client.agents.blocks.retrieve(
        agent_id=main_agent_id, block_label=SHARED_MEMORY_LABEL,
    )
    return getattr(block, "value", "") or ""

def update_shared_memory_value(value: str):
    main_agent_id, _ = get_agents()
    letta_client.agents.blocks.update(
        agent_id=main_agent_id, block_label=SHARED_MEMORY_LABEL, value=value,
    )

# ── Parse / serialize known people ────────────────────────────────────────────

def _parse_known_people(memory_text: str) -> list[dict]:
    marker_lower = KNOWN_PEOPLE_MARKER.lower()
    lines = memory_text.splitlines()
    for i, line in enumerate(lines):
        stripped = line.strip().lstrip("-* ").strip()
        if stripped.lower().startswith(marker_lower):
            after_marker = stripped[len(KNOWN_PEOPLE_MARKER):].strip()
            if after_marker:
                json_text = after_marker
            elif i + 1 < len(lines):
                json_text = lines[i + 1].strip()
            else:
                return []
            for end in range(i + 1, len(lines) + 1):
                try:
                    data = json.loads(json_text)
                    if isinstance(data, list):
                        return data
                except (json.JSONDecodeError, ValueError):
                    if end < len(lines):
                        json_text += "\n" + lines[end].strip()
                    else:
                        break
            return []
    return []

def _serialize_known_people(people: list[dict]) -> str:
    compact = []
    for p in people:
        entry = {"name": p["name"]}
        if p.get("description"):
            entry["description"] = p["description"]
        if p.get("image_file"):
            entry["image_file"] = p["image_file"]
        compact.append(entry)
    return json.dumps(compact, separators=(",", ":"))

def _write_known_people_to_memory(people: list[dict]):
    memory_text = get_shared_memory_value()
    people_json = _serialize_known_people(people)
    new_section = f"- {KNOWN_PEOPLE_MARKER}\n  {people_json}"

    marker_lower = KNOWN_PEOPLE_MARKER.lower()
    output_lines = []
    skip_json = False
    replaced = False
    for line in memory_text.splitlines():
        stripped = line.strip().lstrip("-* ").strip()
        if stripped.lower().startswith(marker_lower):
            output_lines.append(new_section)
            replaced = True
            skip_json = True
            continue
        if skip_json:
            s = line.strip()
            if s.startswith("[") or s.startswith("{") or s.startswith("]") or s.startswith('"'):
                continue
            skip_json = False
        output_lines.append(line)

    if not replaced:
        if output_lines and any(l.strip() for l in output_lines):
            output_lines.append(new_section)
        else:
            output_lines = [new_section]

    update_shared_memory_value("\n".join(output_lines).strip())

# ── Read known people ─────────────────────────────────────────────────────────

def get_known_people() -> list[dict]:
    with _state_lock:
        if time.time() - state.get("last_cache_at", 0.0) < CACHE_SECONDS:
            cached = state.get("known_people_cache")
            if cached is not None:
                return cached
    try:
        memory_text = get_shared_memory_value()
        people = _parse_known_people(memory_text)
        with _state_lock:
            state["known_people_cache"] = people
            state["last_cache_at"] = time.time()
        return people
    except Exception as exc:
        print(f"Could not read known people from Letta memory: {exc}")
        with _state_lock:
            return state.get("known_people_cache") or []

def get_known_person_name() -> str | None:
    people = get_known_people()
    return people[0].get("name") if people else None

# ── Ask / announce flow ───────────────────────────────────────────────────────

def is_waiting_for_name() -> bool:
    with _state_lock:
        return bool(state.get("pending_name"))

def get_pending_description() -> str | None:
    with _state_lock:
        return state.get("pending_description")

def get_pending_jpeg() -> bytes | None:
    with _state_lock:
        return state.get("pending_jpeg")

def should_ask_for_person_name() -> bool:
    with _state_lock:
        if state.get("pending_name"):
            return False
    return time.time() - state.get("last_ask_at", 0.0) >= ASK_COOLDOWN_SECONDS

def mark_asked_for_person_name(description=None, jpeg_bytes=None):
    with _state_lock:
        state["pending_name"] = True
        state["last_ask_at"] = time.time()
        state["pending_description"] = description
        state["pending_jpeg"] = jpeg_bytes

def should_announce_known_person(name: str) -> bool:
    with _state_lock:
        last = state.get("last_announce_at", {}).get(name, 0.0)
    return time.time() - last >= ANNOUNCE_COOLDOWN_SECONDS

def mark_known_person_announced(name: str):
    with _state_lock:
        state.setdefault("last_announce_at", {})[name] = time.time()

# ── Save / learn ──────────────────────────────────────────────────────────────

def save_detected_person(name: str, description=None, image_file=None):
    """Save a newly-identified person with their reference photo."""
    import face_recognition_utils

    if description is None:
        description = get_pending_description() or ""

    # Save the reference image to disk
    if image_file is None:
        jpeg_bytes = get_pending_jpeg()
        if jpeg_bytes:
            image_file = face_recognition_utils.save_person_image(name, jpeg_bytes)

    people = get_known_people()

    # Update existing or append new
    found = False
    for p in people:
        if p.get("name", "").lower() == name.lower():
            if description:
                p["description"] = description
            if image_file:
                p["image_file"] = image_file
            found = True
            break
    if not found:
        people.append({
            "name": name,
            "description": description,
            "image_file": image_file or "",
        })

    _write_known_people_to_memory(people)

    with _state_lock:
        state["known_people_cache"] = people
        state["last_cache_at"] = time.time()
        state["pending_name"] = False
        state["pending_description"] = None
        state["pending_jpeg"] = None
        state.setdefault("last_announce_at", {})[name] = 0.0

# ── Name extraction ──────────────────────────────────────────────────────────

def extract_person_name(message: str) -> str | None:
    text = message.strip()
    patterns = [
        r"^(?:this|that|he|she|they|it)\s+is\s+(.+)$",
        r"^(?:his|her|their|the)\s+name\s+is\s+(.+)$",
        r"^name\s+is\s+(.+)$",
        r"^call\s+(?:him|her|them|this person)\s+(.+)$",
    ]
    for pattern in patterns:
        match = re.match(pattern, text, flags=re.IGNORECASE)
        if match:
            return clean_person_name(match.group(1))
    return clean_person_name(text)

def clean_person_name(raw_name: str) -> str | None:
    name = raw_name.strip().strip(".!?,;:")
    if not name:
        return None
    words = name.split()
    if len(words) > 4 or len(name) > 48:
        return None
    return " ".join(w[:1].upper() + w[1:] for w in words)
