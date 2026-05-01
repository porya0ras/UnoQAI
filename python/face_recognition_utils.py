"""
Face recognition utilities.

Provides helpers to extract face encodings from raw JPEG frames
and to compare an unknown encoding against a list of known encodings.
Uses the `face_recognition` library (dlib-backed, 128-d embeddings).
"""

import io
import numpy as np

try:
    import face_recognition
except ImportError:
    face_recognition = None

try:
    from PIL import Image
except ImportError:
    Image = None

from config import FACE_MATCH_THRESHOLD


def is_available() -> bool:
    """Return True when the face_recognition library is importable."""
    return face_recognition is not None and Image is not None


def encode_face_from_jpeg(jpeg_bytes: bytes) -> np.ndarray | None:
    """Extract a single 128-d face encoding from raw JPEG bytes.

    Args:
        jpeg_bytes: Raw JPEG image data.

    Returns:
        A 128-element numpy array, or None if no face is detected.
    """
    if not is_available() or not jpeg_bytes:
        return None

    try:
        pil_image = Image.open(io.BytesIO(jpeg_bytes)).convert("RGB")
        # Downscale for speed — 1/2 resolution is a good balance
        w, h = pil_image.size
        if w > 640:
            scale = 640 / w
            pil_image = pil_image.resize(
                (int(w * scale), int(h * scale)), Image.LANCZOS
            )
        rgb_array = np.array(pil_image)
    except Exception:
        return None

    # Detect face locations, then compute encodings
    face_locations = face_recognition.face_locations(rgb_array, model="hog")
    if not face_locations:
        return None

    encodings = face_recognition.face_encodings(rgb_array, face_locations)
    if not encodings:
        return None

    # Return the first (largest / most prominent) face
    return encodings[0]


def find_best_match(
    unknown_encoding: np.ndarray,
    known_people: list[dict],
) -> str | None:
    """Compare *unknown_encoding* against a list of known people.

    Args:
        unknown_encoding: 128-d numpy array of the face to identify.
        known_people: List of dicts with keys ``name`` and ``encoding``
            (each encoding is a list/array of 128 floats).

    Returns:
        The name of the best match, or None if no match is close enough.
    """
    if not known_people or unknown_encoding is None:
        return None

    known_encodings = []
    known_names = []
    for entry in known_people:
        enc = entry.get("encoding")
        name = entry.get("name")
        if enc is not None and name:
            known_encodings.append(np.array(enc, dtype=np.float64))
            known_names.append(name)

    if not known_encodings:
        return None

    distances = face_recognition.face_distance(known_encodings, unknown_encoding)
    best_idx = int(np.argmin(distances))
    if distances[best_idx] <= FACE_MATCH_THRESHOLD:
        return known_names[best_idx]

    return None
