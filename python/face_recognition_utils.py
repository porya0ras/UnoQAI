"""
Vision-based person identification using the Letta agent (OpenAI GPT-4o vision).

Sends camera frames AND saved reference photos of known people to the AI
in a single multimodal message — the AI does image-to-image comparison
(like a visual RAG: reference images are the "retrieved" context).

No dlib, cmake, or face_recognition library needed.
"""

import base64
import io

try:
    from PIL import Image
except ImportError:
    Image = None

from config import letta_client, KNOWN_FACES_DIR
from letta_messaging import get_agents


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
    """Downscale a JPEG to reduce token usage on the vision API."""
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


def save_person_image(name: str, jpeg_bytes: bytes) -> str | None:
    """Save a person's reference photo to disk.

    Args:
        name: Person's name (used as filename).
        jpeg_bytes: Raw JPEG image data.

    Returns:
        The filename saved, or None on failure.
    """
    if not jpeg_bytes:
        return None
    # Sanitise name for filesystem
    safe_name = "".join(c if c.isalnum() or c in (" ", "-", "_") else "_" for c in name)
    safe_name = safe_name.strip().replace(" ", "_").lower()
    filename = f"{safe_name}.jpg"
    filepath = KNOWN_FACES_DIR / filename
    try:
        resized = resize_for_vision(jpeg_bytes, max_width=512)
        filepath.write_bytes(resized)
        print(f"[vision] Saved reference photo: {filepath}")
        return filename
    except Exception as exc:
        print(f"[vision] Failed to save reference photo: {exc}")
        return None


def load_person_image(filename: str) -> bytes | None:
    """Load a person's reference photo from disk."""
    filepath = KNOWN_FACES_DIR / filename
    try:
        if filepath.exists():
            return filepath.read_bytes()
    except Exception:
        pass
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
    """Send new photo + all reference photos to AI for visual comparison.

    This is the core RAG-style identification: the AI sees the saved
    reference images of each known person alongside the new camera frame,
    and determines who (if anyone) the new person is.

    Args:
        jpeg_bytes: New camera frame (JPEG bytes).
        known_people: List of dicts with ``name`` and ``image_file`` keys.

    Returns:
        Matched person's name, or None if unknown.
    """
    if not jpeg_bytes or not known_people:
        return None

    # Build multimodal content: reference images + new image
    content_parts = []

    # First: text instruction
    names_list = ", ".join(p.get("name", "?") for p in known_people)
    content_parts.append({
        "type": "text",
        "text": (
            "[SYSTEM — vision identification task, do NOT reply to the user]\n"
            f"I have reference photos of these known people: {names_list}.\n"
            "The reference photos are labeled below. After them is a NEW "
            "camera photo. Compare the person in the NEW photo against the "
            "reference photos.\n"
            "If the person matches one of them, respond with ONLY their name "
            "(exactly as labeled). If no match, respond with exactly: UNKNOWN\n"
            "Do not add any other text."
        ),
    })

    # Add each known person's reference image
    ref_count = 0
    for person in known_people:
        img_file = person.get("image_file")
        name = person.get("name", "?")
        if not img_file:
            continue
        img_bytes = load_person_image(img_file)
        if not img_bytes:
            continue
        data_uri = jpeg_bytes_to_base64(img_bytes)
        if not data_uri:
            continue
        # Label before each reference image
        content_parts.append({
            "type": "text",
            "text": f"Reference photo of {name}:",
        })
        content_parts.append({
            "type": "image",
            "source": {"type": "url", "url": data_uri},
        })
        ref_count += 1

    if ref_count == 0:
        return None

    # Add the new camera frame
    new_resized = resize_for_vision(jpeg_bytes)
    new_data_uri = jpeg_bytes_to_base64(new_resized)
    if not new_data_uri:
        return None

    content_parts.append({
        "type": "text",
        "text": "NEW camera photo (identify this person):",
    })
    content_parts.append({
        "type": "image",
        "source": {"type": "url", "url": new_data_uri},
    })

    main_agent_id, _ = get_agents()

    try:
        response = letta_client.agents.messages.create(
            agent_id=main_agent_id,
            messages=[{"role": "user", "content": content_parts}],
        )
        result_text = _extract_response_text(response)
        if not result_text:
            return None

        result_text = result_text.strip().strip('"\'.')

        if result_text.upper() == "UNKNOWN":
            return None

        # Exact match
        for person in known_people:
            if person.get("name", "").lower() == result_text.lower():
                return person["name"]
        # Fuzzy: name contained in response
        for person in known_people:
            if person.get("name", "").lower() in result_text.lower():
                return person["name"]

        return None
    except Exception as exc:
        print(f"[vision] Failed to identify person: {exc}")
        return None


def describe_person(jpeg_bytes: bytes) -> str | None:
    """Ask the AI to describe a person's appearance from a camera frame.

    Returns:
        Short text description, or None on failure.
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
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "[SYSTEM — vision task, do NOT reply to the user]\n"
                            "Describe ONLY this person's distinctive visual "
                            "features in one short sentence (hair, facial hair, "
                            "glasses, age, clothing). No names. Under 30 words. "
                            "Respond with ONLY the description."
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
        print(f"[vision] Failed to describe person: {exc}")
        return None
