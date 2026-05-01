from arduino.app_utils import App
from ui_instance import ui, send_agent_error, send_agent_response
from led_tools import extract_direct_led_text
import led_matrix
from letta_messaging import ask_letta, get_agents
from background_tasks import schedule_memory_update, schedule_idle_memory_manager_check, cancel_idle_memory_manager_check
from config import LETTA_BASE_URL, MEMORY_MANAGER_IDLE_SECONDS
from arduino.app_bricks.video_imageclassification import VideoImageClassification
from arduino.app_peripherals.camera import WebSocketCamera
from person_identity import (
    extract_person_name,
    get_known_people,
    is_waiting_for_name,
    get_pending_encoding,
    mark_asked_for_person_name,
    mark_known_person_announced,
    save_detected_person,
    should_announce_known_person,
    should_ask_for_person_name,
)
import face_recognition_utils
import secrets
import string
import json
import threading

def generate_secret() -> str:
    characters = string.digits
    return ''.join(secrets.choice(characters) for _ in range(6))

secret = generate_secret()
camera = WebSocketCamera(secret=secret, encrypt=True)
detection_stream = VideoImageClassification(camera, confidence=0.5, debounce_sec=0.0)

current_vision_classes = []
_face_lock = threading.Lock()


def _try_identify_person() -> tuple[str | None, object]:
    """Grab a frame from the camera, extract a face encoding, and try to match.

    Returns:
        (matched_name_or_None, face_encoding_or_None)
    """
    if not face_recognition_utils.is_available():
        return None, None

    try:
        frame = camera.capture()
        if frame is None:
            return None, None

        # compress_to_jpeg is used internally by the camera loop; we do the
        # same here to get raw JPEG bytes for face_recognition.
        from arduino.app_utils.image.adjustments import compress_to_jpeg
        jpeg_bytes = compress_to_jpeg(frame)
        if jpeg_bytes is None:
            return None, None
        jpeg_bytes = jpeg_bytes.tobytes()
    except Exception as exc:
        print(f"[face] Frame capture error: {exc}")
        return None, None

    encoding = face_recognition_utils.encode_face_from_jpeg(jpeg_bytes)
    if encoding is None:
        return None, None

    known_people = get_known_people()
    matched_name = face_recognition_utils.find_best_match(encoding, known_people)
    return matched_name, encoding


def handle_detections(classifications: dict):
    global current_vision_classes
    if len(classifications) == 0:
        current_vision_classes = []
    else:
        current_vision_classes = list(classifications.keys())

    person_detected = False
    person_confidence = None
    for key, value in classifications.items():
        if key.lower() == "person":
            person_detected = True
            person_confidence = value

    # ── Build overlay entries ─────────────────────────────────────────────
    if not person_detected:
        # Send non-person classifications as-is
        entries = [
            {"content": k, "confidence": v, "label": k}
            for k, v in classifications.items()
        ]
        ui.send_message("classifications", message=json.dumps(entries if entries else []))
        return

    # ── Person detected → try face recognition ───────────────────────────
    # Use a lock to prevent overlapping face-recognition work
    if not _face_lock.acquire(blocking=False):
        return
    try:
        matched_name, encoding = _try_identify_person()
    finally:
        _face_lock.release()

    # ── Build overlay with person label ───────────────────────────────────
    label = matched_name or "Unknown"
    entries = []
    for key, value in classifications.items():
        if key.lower() == "person":
            entries.append({
                "content": key,
                "confidence": value,
                "label": label,
            })
        else:
            entries.append({
                "content": key,
                "confidence": value,
                "label": key,
            })
    ui.send_message("classifications", message=json.dumps(entries))

    # ── React: announce known person or ask for name ──────────────────────
    if matched_name:
        if should_announce_known_person(matched_name):
            mark_known_person_announced(matched_name)
            confidence_text = (
                f" ({person_confidence:.0%} confidence)"
                if isinstance(person_confidence, (int, float))
                else ""
            )
            send_agent_response(f"I see {matched_name}{confidence_text}.")
        return

    # Unknown face (or no face_recognition library) → ask for name
    if should_ask_for_person_name():
        mark_asked_for_person_name(encoding)
        send_agent_response("I see a person I don't recognise. What is their name?")

def handle_camera_status(evt_type, data):
    ui.send_message(evt_type, data)
    if camera.status == "connected" and detection_stream is not None:
        detection_stream.on_detect_all(handle_detections)

camera.on_status_changed(handle_camera_status)

def on_ui_connect(sid):
    ui.send_message("welcome", {
        "client_name": camera.name,
        "secret": secret,
        "status": camera.status,
        "protocol": camera.protocol,
        "ip": camera.ip,
        "port": camera.port
    })

def on_chat_message(_sid, data):
    try:
        message = data.get("message", "").strip()

        if not message:
            send_agent_error("Message is empty")
            return

        cancel_idle_memory_manager_check()
        print(f"User: {message}")

        if is_waiting_for_name():
            name = extract_person_name(message)
            if not name:
                send_agent_response("Please tell me just the person's name.")
                schedule_idle_memory_manager_check()
                return
            save_detected_person(name)
            answer = f"I will remember this person as {name}."
            print(f"Saved detected person in Letta memory: {name}")
            print(f"Agent: {answer}")
            send_agent_response(answer)
            ui.send_message(
                "classifications",
                message=json.dumps(
                    [
                        {
                            "content": "person",
                            "confidence": None,
                            "label": name,
                        }
                    ]
                ),
            )
            schedule_idle_memory_manager_check()
            return

        direct_led_text = extract_direct_led_text(message)
        if direct_led_text:
            rendered_text = led_matrix.write_text(direct_led_text)
            answer = f"I displayed '{rendered_text}' on my LED matrix."
            print(f"LED matrix direct text: {rendered_text}")
            print(f"Agent: {answer}")
            send_agent_response(answer)
            schedule_memory_update(message, answer)
            schedule_idle_memory_manager_check()
            return

        vision_str = ", ".join(current_vision_classes) if current_vision_classes else "nothing"
        answer = ask_letta(message, vision_context=vision_str)

        print(f"Agent: {answer}")
        send_agent_response(answer)
        schedule_memory_update(message, answer)
        schedule_idle_memory_manager_check()

    except Exception as e:
        print(f"Error: {e}")
        send_agent_error(e)
        schedule_idle_memory_manager_check()

print("Starting UNO Q WebUI Letta app...")
print(f"Letta URL: {LETTA_BASE_URL}")
print(f"Memory manager idle check: {MEMORY_MANAGER_IDLE_SECONDS}s")
print(f"Face recognition available: {face_recognition_utils.is_available()}")
print("Initializing Letta agents...")
main_agent_id, memory_manager_agent_id = get_agents()
print(f"Letta main agent: {main_agent_id}")
print(f"Letta memory manager agent: {memory_manager_agent_id}")

ui.on_connect(on_ui_connect)
ui.on_message("chat_message", on_chat_message)
schedule_idle_memory_manager_check()

App.run()
