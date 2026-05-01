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
    extract_person_name, get_known_people, is_waiting_for_name,
    get_pending_description, mark_asked_for_person_name,
    mark_known_person_announced, save_detected_person,
    should_announce_known_person, should_ask_for_person_name,
)
import face_recognition_utils
import secrets, string, json, threading

def generate_secret() -> str:
    return ''.join(secrets.choice(string.digits) for _ in range(6))

secret = generate_secret()
camera = WebSocketCamera(secret=secret, encrypt=True)
detection_stream = VideoImageClassification(camera, confidence=0.5, debounce_sec=0.0)
current_vision_classes = []
_vision_lock = threading.Lock()

def _capture_jpeg() -> bytes | None:
    try:
        frame = camera.capture()
        if frame is None:
            return None
        from arduino.app_utils.image.adjustments import compress_to_jpeg
        jpeg_frame = compress_to_jpeg(frame)
        if jpeg_frame is None:
            return None
        return jpeg_frame.tobytes()
    except Exception as exc:
        print(f"[vision] Frame capture error: {exc}")
        return None

def _try_identify_person() -> tuple[str | None, str | None, bytes | None]:
    if not face_recognition_utils.is_available():
        return None, None, None
    jpeg_bytes = _capture_jpeg()
    if not jpeg_bytes:
        return None, None, None
    known_people = get_known_people()
    if known_people:
        matched_name = face_recognition_utils.identify_person(jpeg_bytes, known_people)
        if matched_name:
            return matched_name, None, jpeg_bytes
    description = face_recognition_utils.describe_person(jpeg_bytes)
    return None, description, jpeg_bytes

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

    if not person_detected:
        entries = [{"content": k, "confidence": v, "label": k} for k, v in classifications.items()]
        ui.send_message("classifications", message=json.dumps(entries if entries else []))
        return

    if not _vision_lock.acquire(blocking=False):
        return
    try:
        matched_name, description, jpeg_bytes = _try_identify_person()
    finally:
        _vision_lock.release()

    label = matched_name or "Unknown"
    entries = []
    for key, value in classifications.items():
        if key.lower() == "person":
            entries.append({"content": key, "confidence": value, "label": label})
        else:
            entries.append({"content": key, "confidence": value, "label": key})
    ui.send_message("classifications", message=json.dumps(entries))

    if matched_name:
        if should_announce_known_person(matched_name):
            mark_known_person_announced(matched_name)
            conf = f" ({person_confidence:.0%} confidence)" if isinstance(person_confidence, (int, float)) else ""
            send_agent_response(f"I see {matched_name}{conf}.")
        return

    if should_ask_for_person_name():
        mark_asked_for_person_name(description=description, jpeg_bytes=jpeg_bytes)
        send_agent_response("I see a person I don't recognise. What is their name?")

def handle_camera_status(evt_type, data):
    ui.send_message(evt_type, data)
    if camera.status == "connected" and detection_stream is not None:
        detection_stream.on_detect_all(handle_detections)

camera.on_status_changed(handle_camera_status)

def on_ui_connect(sid):
    ui.send_message("welcome", {
        "client_name": camera.name, "secret": secret,
        "status": camera.status, "protocol": camera.protocol,
        "ip": camera.ip, "port": camera.port,
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
            ui.send_message("classifications", message=json.dumps(
                [{"content": "person", "confidence": None, "label": name}]
            ))
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
print(f"Vision identification available: {face_recognition_utils.is_available()}")
print("Initializing Letta agents...")
main_agent_id, memory_manager_agent_id = get_agents()
print(f"Letta main agent: {main_agent_id}")
print(f"Letta memory manager agent: {memory_manager_agent_id}")

ui.on_connect(on_ui_connect)
ui.on_message("chat_message", on_chat_message)
schedule_idle_memory_manager_check()

App.run()
