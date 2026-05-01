"""
Vision-based person identification using the Letta agent (OpenAI GPT-4o vision).

Instead of local face_recognition / dlib embeddings, this module sends camera
frames directly to the Letta agent as multimodal messages.  The agent uses its
AI vision capabilities to describe and identify people, storing text
descriptions (not numerical embeddings) in its shared memory block.

This eliminates the need for dlib, cmake, face_recognition, or any native
C++ build tools.
"""

import base64
import io
import json

try:
    from PIL import Image
except ImportError:
    Image = None

from config import letta_client
from letta_messaging import get_agents


def is_available() -> bool:
    """Return True when vision identification can work (Pillow installed)."""
    return Image is not None


def jpeg_bytes_to_base64(jpeg_bytes: bytes) -> str | None:
    """Convert raw JPEG bytes to a base64-encoded data URI string."""
    if not jpeg_bytes:
        return None
    b64 = base64.b64encode(jpeg_bytes).decode("utf-8")
    return f"data:image/jpeg;base64,{b64}"


def resize_for_vision(jpeg_bytes: bytes, max_width: int = 512) -> bytes:
    """Downscale a JPEG image to reduce token usage on the vision API.

    Args:
        jpeg_bytes: Raw JPEG data.
        max_width: Maximum width in pixels (height scales proportionally).

    Returns:
        Resized JPEG bytes, or original if Pillow is unavailable or image
        is already small enough.
    """
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


def describe_person(jpeg_bytes: bytes) -> str | None:
    """Send a camera frame to the AI and get a visual description of the person.

    Returns:
        A short text description of the person's appearance, or None on failure.
    """
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
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "[SYSTEM — vision task, do NOT reply to the user]\n"
                                "Look at this camera image. A person has been detected. "
                                "Describe ONLY the person's distinctive visual features "
                                "in a single short sentence (hair colour/style, facial hair, "
                                "glasses, approximate age, clothing colour). "
                                "Do NOT include names. Keep it under 30 words. "
                                "Respond with ONLY the description, nothing else."
                            ),
                        },
                        {
                            "type": "image",
                            "source": {
                                "type": "url",
                                "url": data_uri,
                            },
                        },
                    ],
                },
            ],
        )
        # Extract text from Letta response
        for msg in getattr(response, "messages", []):
            if getattr(msg, "message_type", None) == "assistant_message":
                return getattr(msg, "content", None)
            content = getattr(msg, "content", None)
            if content and isinstance(content, str):
                return content
        return None
    except Exception as exc:
        print(f"[vision] Failed to describe person: {exc}")
        return None


def identify_person(jpeg_bytes: bytes, known_people: list[dict]) -> str | None:
    """Send a camera frame + known people descriptions to the AI for matching.

    Args:
        jpeg_bytes: Raw JPEG image data from the camera.
        known_people: List of dicts with keys ``name`` and ``description``.

    Returns:
        The name of the matched person, or None if unknown / no match.
    """
    if not jpeg_bytes:
        return None

    resized = resize_for_vision(jpeg_bytes)
    data_uri = jpeg_bytes_to_base64(resized)
    if not data_uri:
        return None

    # Build a roster of known people for the prompt
    if not known_people:
        return None

    roster_lines = []
    for i, person in enumerate(known_people, 1):
        name = person.get("name", "?")
        desc = person.get("description", "no description")
        roster_lines.append(f"  {i}. {name}: {desc}")
    roster = "\n".join(roster_lines)

    main_agent_id, _ = get_agents()

    try:
        response = letta_client.agents.messages.create(
            agent_id=main_agent_id,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "[SYSTEM — vision task, do NOT reply to the user]\n"
                                "Look at this camera image. Compare the person in the image "
                                "against these known people:\n"
                                f"{roster}\n\n"
                                "If the person matches one of them, respond with ONLY their "
                                "name (exactly as listed). If the person does NOT match any "
                                "of them, respond with exactly: UNKNOWN\n"
                                "Do not add any other text."
                            ),
                        },
                        {
                            "type": "image",
                            "source": {
                                "type": "url",
                                "url": data_uri,
                            },
                        },
                    ],
                },
            ],
        )
        # Extract response text
        result_text = None
        for msg in getattr(response, "messages", []):
            if getattr(msg, "message_type", None) == "assistant_message":
                result_text = getattr(msg, "content", None)
                break
            content = getattr(msg, "content", None)
            if content and isinstance(content, str):
                result_text = content
                break

        if not result_text:
            return None

        result_text = result_text.strip().strip('"').strip("'").strip(".")

        # Check if the AI said UNKNOWN
        if result_text.upper() == "UNKNOWN":
            return None

        # Verify the returned name matches one of our known people
        for person in known_people:
            if person.get("name", "").lower() == result_text.lower():
                return person["name"]

        # Fuzzy: check if the result contains a known name
        for person in known_people:
            if person.get("name", "").lower() in result_text.lower():
                return person["name"]

        return None
    except Exception as exc:
        print(f"[vision] Failed to identify person: {exc}")
        return None
