"""
Person identity management backed by Letta shared memory.

Supports multiple known people, each stored with a name and text description
in the Letta ``shared_user_memory`` block.  The AI agent describes the person
visually, and subsequent matches use the stored descriptions to identify
returning individuals.
"""

import json
import re
import time
import threading

from config import letta_client
from letta_messaging import get_agents


# ── Constants ────────────────────────────────────────────────────────────────

ASK_COOLDOWN_SECONDS = 120        # Don't re-ask for a name within this window
ANNOUNCE_COOLDOWN_SECONDS = 30    # Don't repeat "I see X" too often
CACHE_SECONDS = 10                # How long to cache known-people from Letta
SHARED_MEMORY_LABEL = "shared_user_memory"
KNOWN_PEOPLE_MARKER = "Known people:"

# ── Module-level state ───────────────────────────────────────────────────────

state = {
    "pending_name": False,             # True while waiting for the user to type a name
    "pending_description": None,       # AI-generated description of the unidentified person
    "pending_jpeg": None,              # JPEG bytes of the pending face (for re-describe)
    "last_ask_at": 0.0,                # Timestamp of the last "who is this?" prompt
    "last_announce_at": {},            # {name: timestamp} of last announcement per person
    "known_people_cache": None,        # Cached list of known people dicts
    "last_cache_at": 0.0,
}
_state_lock = threading.Lock()


# ── Letta memory I/O ─────────────────────────────────────────────────────────

def get_shared_memory_value() -> str:
    main_agent_id, _ = get_agents()
    block = letta_client.agents.blocks.retrieve(
        agent_id=main_agent_id,
        block_label=SHARED_MEMORY_LABEL,
    )
    return getattr(block, "value", "") or ""


def update_shared_memory_value(value: str):
    main_agent_id, _ = get_agents()
    letta_client.agents.blocks.update(
        agent_id=main_agent_id,
        block_label=SHARED_MEMORY_LABEL,
        value=value,
    )


# ── Read / write known people from Letta memory ──────────────────────────────

def _parse_known_people(memory_text: str) -> list[dict]:
    """Parse the known-people JSON block from the shared memory text.

    Expected format inside the memory block::

        - Known people:
          [{"name": "Porya", "description": "Male, dark hair, beard"}, ...]
    """
    marker_lower = KNOWN_PEOPLE_MARKER.lower()
    lines = memory_text.splitlines()
    for i, line in enumerate(lines):
        stripped = line.strip().lstrip("-* ").strip()
        if stripped.lower().startswith(marker_lower):
            # The JSON array may start on the same line or the next line
            after_marker = stripped[len(KNOWN_PEOPLE_MARKER):].strip()
            if after_marker:
                json_text = after_marker
            elif i + 1 < len(lines):
                json_text = lines[i + 1].strip()
            else:
                return []
            # Collect multi-line JSON until we parse a valid list
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
    """Serialize the known-people list to a compact JSON string."""
    compact = []
    for p in people:
        compact.append({
            "name": p["name"],
            "description": p.get("description", ""),
        })
    return json.dumps(compact, separators=(",", ":"))


def _write_known_people_to_memory(people: list[dict]):
    """Replace the known-people section in Letta memory with *people*."""
    memory_text = get_shared_memory_value()
    people_json = _serialize_known_people(people)
    new_section = f"- {KNOWN_PEOPLE_MARKER}\n  {people_json}"

    # Try to replace existing section
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
            # Skip old JSON continuation lines (indented or starting with '[')
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


def get_known_people() -> list[dict]:
    """Return the list of known people (cached)."""
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


# ── Convenience accessors ─────────────────────────────────────────────────────

def get_known_person_name() -> str | None:
    """Return the first known person's name (legacy single-person compat)."""
    people = get_known_people()
    if people:
        return people[0].get("name")
    return None


# ── Ask / announce flow ───────────────────────────────────────────────────────

def is_waiting_for_name() -> bool:
    with _state_lock:
        return bool(state.get("pending_name"))


def get_pending_description() -> str | None:
    """Return the AI description of the person we asked about."""
    with _state_lock:
        return state.get("pending_description")


def get_pending_jpeg() -> bytes | None:
    """Return the JPEG bytes of the pending (unidentified) person."""
    with _state_lock:
        return state.get("pending_jpeg")


def should_ask_for_person_name() -> bool:
    with _state_lock:
        if state.get("pending_name"):
            return False
    if time.time() - state.get("last_ask_at", 0.0) < ASK_COOLDOWN_SECONDS:
        return False
    return True


def mark_asked_for_person_name(
    description: str | None = None,
    jpeg_bytes: bytes | None = None,
):
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
        if "last_announce_at" not in state:
            state["last_announce_at"] = {}
        state["last_announce_at"][name] = time.time()


# ── Save / learn ──────────────────────────────────────────────────────────────

def save_detected_person(name: str, description: str | None = None):
    """Save a newly-identified person to Letta memory.

    If *description* is None, the pending description from the ask-flow is used.
    """
    if description is None:
        description = get_pending_description() or ""

    people = get_known_people()

    # Check if this person already exists (update description)
    found = False
    for p in people:
        if p.get("name", "").lower() == name.lower():
            if description:
                p["description"] = description
            found = True
            break

    if not found:
        people.append({"name": name, "description": description})

    _write_known_people_to_memory(people)

    with _state_lock:
        state["known_people_cache"] = people
        state["last_cache_at"] = time.time()
        state["pending_name"] = False
        state["pending_description"] = None
        state["pending_jpeg"] = None
        # Reset announce so the name gets said immediately
        if "last_announce_at" not in state:
            state["last_announce_at"] = {}
        state["last_announce_at"][name] = 0.0


# ── Name extraction from user message ────────────────────────────────────────

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
    return " ".join(word[:1].upper() + word[1:] for word in words)
