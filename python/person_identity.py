import re
import time

from config import letta_client
from letta_messaging import get_agents


ASK_COOLDOWN_SECONDS = 120
ANNOUNCE_COOLDOWN_SECONDS = 45
CACHE_SECONDS = 10
SHARED_MEMORY_LABEL = "shared_user_memory"
PERSON_MEMORY_PREFIX = "Camera person identity:"

state = {
    "pending_name": False,
    "last_ask_at": 0.0,
    "last_announce_at": 0.0,
    "known_person_name_cache": None,
    "last_cache_at": 0.0,
}


def get_known_person_name():
    if time.time() - state.get("last_cache_at", 0.0) < CACHE_SECONDS:
        return state.get("known_person_name_cache")
    try:
        name = read_person_name_from_memory()
        state["known_person_name_cache"] = name
        state["last_cache_at"] = time.time()
        return name
    except Exception as exc:
        print(f"Could not read person identity from Letta memory: {exc}")
        return state.get("known_person_name_cache")


def get_shared_memory_value():
    main_agent_id, _ = get_agents()
    block = letta_client.agents.blocks.retrieve(
        agent_id=main_agent_id,
        block_label=SHARED_MEMORY_LABEL,
    )
    return getattr(block, "value", "") or ""


def update_shared_memory_value(value):
    main_agent_id, _ = get_agents()
    letta_client.agents.blocks.update(
        agent_id=main_agent_id,
        block_label=SHARED_MEMORY_LABEL,
        value=value,
    )


def read_person_name_from_memory():
    memory_value = get_shared_memory_value()
    prefix = PERSON_MEMORY_PREFIX.lower()
    for line in memory_value.splitlines():
        normalized = line.strip().lstrip("-* ").strip()
        if normalized.lower().startswith(prefix):
            name = normalized[len(PERSON_MEMORY_PREFIX):].strip()
            return name or None
    return None


def write_person_name_to_memory(name):
    memory_value = get_shared_memory_value()
    person_line = f"- {PERSON_MEMORY_PREFIX} {name}"
    lines = []
    replaced = False
    prefix = PERSON_MEMORY_PREFIX.lower()

    for line in memory_value.splitlines():
        normalized = line.strip().lstrip("-* ").strip()
        if normalized.lower().startswith(prefix):
            if not replaced:
                lines.append(person_line)
                replaced = True
            continue
        lines.append(line)

    if not replaced:
        if lines and any(line.strip() for line in lines):
            lines.append(person_line)
        else:
            lines = [person_line]

    update_shared_memory_value("\n".join(lines).strip())


def is_waiting_for_name():
    return bool(state.get("pending_name"))


def should_ask_for_person_name():
    if get_known_person_name() or state.get("pending_name"):
        return False
    return time.time() - state.get("last_ask_at", 0.0) >= ASK_COOLDOWN_SECONDS


def mark_asked_for_person_name():
    state["pending_name"] = True
    state["last_ask_at"] = time.time()


def should_announce_known_person():
    if not get_known_person_name():
        return False
    return time.time() - state.get("last_announce_at", 0.0) >= ANNOUNCE_COOLDOWN_SECONDS


def mark_known_person_announced():
    state["last_announce_at"] = time.time()


def extract_person_name(message):
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


def clean_person_name(raw_name):
    name = raw_name.strip().strip(".!?,;:")
    if not name:
        return None
    words = name.split()
    if len(words) > 4 or len(name) > 48:
        return None
    return " ".join(word[:1].upper() + word[1:] for word in words)


def save_detected_person_name(name):
    write_person_name_to_memory(name)
    state["known_person_name_cache"] = name
    state["last_cache_at"] = time.time()
    state["pending_name"] = False
    state["last_announce_at"] = 0.0
