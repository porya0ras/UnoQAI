"""
Vision-based person identification using the Letta agent (OpenAI GPT-4o).

Visual RAG approach: saved reference thumbnails of known people (stored as
base64 in Letta memory) are sent alongside new camera frames to the AI in
a single multimodal message for image-to-image comparison.

Everything lives in Letta memory — no files on disk.
"""

import base64
import io

try:
    from PIL import Image
except ImportError:
    Image = None

from config import letta_client
from letta_messaging import get_agents

# Thumbnail size for reference images stored in memory.
# 80x80 quality-30 JPEG ≈ 600-900 bytes → ~800-1200 base64 chars per person.
THUMB_SIZE = 80
THUMB_QUALITY = 30


def is_available() -> bool:
    """Return True when vision identification can work (Pillow installed)."""
    return Image is not None


def jpeg_bytes_to_base64(jpeg_bytes: bytes) -> str | None:
    """Convert raw JPEG bytes to a base64 data URI string."""
    if not jpeg_bytes:
        return None
    b64 = base64.b64encode(jpeg_bytes).decode("utf-8")
    return f"data:image/jpeg;base64,{b64}"


def resize_for_vision(jpeg_bytes: bytes, max_width: int = 512) -> bytes:
    """Downscale a JPEG for sending to the vision API."""
    if not Image or not jpeg_bytes:
        return jpeg_bytes
    try:
        img = Image.open(io.BytesIO(jpeg_bytes))
        w, h = img.size
        if w <= max_width:
            return jpeg_bytes
        scale = max_width / w
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=75)
        return buf.getvalue()
    except Exception:
        return jpeg_bytes


def make_thumbnail_b64(jpeg_bytes: bytes) -> str | None:
    """Create a tiny thumbnail and return as raw base64 (no data URI prefix).

    The thumbnail is small enough to store inside the Letta memory block.
    """
    if not Image or not jpeg_bytes:
        return None
    try:
        img = Image.open(io.BytesIO(jpeg_bytes)).convert("RGB")
        img.thumbnail((THUMB_SIZE, THUMB_SIZE), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=THUMB_QUALITY)
        return base64.b64encode(buf.getvalue()).decode("utf-8")
    except Exception:
        return None


def _extract_response_text(response) -> str | None:
    """Extract text content from a Letta agent response."""
    for msg in getattr(response, "messages", []):
        if getattr(msg, "message_type", None) == "assistant_message":
            return getattr(msg, "content", None)
        content = getattr(msg, "content", None)
        if content and isinstance(content, str):
            return content
    return None


def identify_person(jpeg_bytes: bytes, known_people: list[dict]) -> str | None:
    """Send new photo + all reference thumbnails to AI for visual comparison.

    Args:
        jpeg_bytes: New camera frame (JPEG bytes).
        known_people: List with ``name`` and ``image_b64`` keys.

    Returns:
        Matched person's name, or None if unknown.
    """
    if not jpeg_bytes or not known_people:
        return None

    content_parts = []
    names_list = ", ".join(p.get("name", "?") for p in known_people)
    content_parts.append({
        "type": "text",
        "text": (
            "[SYSTEM — vision identification, do NOT reply to the user]\n"
            f"Known people: {names_list}.\n"
            "Below are their reference photos, then a NEW camera photo.\n"
            "If the NEW photo matches a known person, respond with ONLY "
            "their name. Otherwise respond: UNKNOWN\n"
            "No other text."
        ),
    })

    ref_count = 0
    for person in known_people:
        b64 = person.get("image_b64")
        name = person.get("name", "?")
        if not b64:
            continue
        content_parts.append({
            "type": "text",
            "text": f"[{name}]:",
        })
        content_parts.append({
            "type": "image",
            "source": {"type": "url", "url": f"data:image/jpeg;base64,{b64}"},
        })
        ref_count += 1

    if ref_count == 0:
        return None

    new_resized = resize_for_vision(jpeg_bytes)
    new_uri = jpeg_bytes_to_base64(new_resized)
    if not new_uri:
        return None

    content_parts.append({"type": "text", "text": "NEW photo:"})
    content_parts.append({
        "type": "image",
        "source": {"type": "url", "url": new_uri},
    })

    main_agent_id, _ = get_agents()
    try:
        response = letta_client.agents.messages.create(
            agent_id=main_agent_id,
            messages=[{"role": "user", "content": content_parts}],
        )
        result = _extract_response_text(response)
        if not result:
            return None
        result = result.strip().strip('"\'.')
        if result.upper() == "UNKNOWN":
            return None
        for p in known_people:
            if p.get("name", "").lower() == result.lower():
                return p["name"]
        for p in known_people:
            if p.get("name", "").lower() in result.lower():
                return p["name"]
        return None
    except Exception as exc:
        print(f"[vision] Identify failed: {exc}")
        return None


def describe_person(jpeg_bytes: bytes) -> str | None:
    """Ask the AI to describe a person's appearance."""
    if not jpeg_bytes:
        return None
    resized = resize_for_vision(jpeg_bytes)
    data_uri = jpeg_bytes_to_base64(resized)
    if not data_uri:
        return None

    main_agent_id, _ = get_agents()
    try:
        response = letta_client.agents.messages.create(
            agent_id=main_agent_id,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "[SYSTEM — vision task, do NOT reply to the user]\n"
                            "Describe ONLY this person's distinctive features "
                            "in one short sentence (hair, facial hair, glasses, "
                            "age, clothing). No names. Under 30 words."
                        ),
                    },
                    {
                        "type": "image",
                        "source": {"type": "url", "url": data_uri},
                    },
                ],
            }],
        )
        return _extract_response_text(response)
    except Exception as exc:
        print(f"[vision] Describe failed: {exc}")
        return None
