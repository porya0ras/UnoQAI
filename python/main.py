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
    get_known_person_name,
    is_waiting_for_name,
    mark_asked_for_person_name,
    mark_known_person_announced,
    save_detected_person_name,
    should_announce_known_person,
    should_ask_for_person_name,
)
import secrets
import string
import json

def generate_secret() -> str:
    characters = string.digits
    return ''.join(secrets.choice(characters) for _ in range(6))

secret = generate_secret()
camera = WebSocketCamera(secret=secret, encrypt=True)
detection_stream = VideoImageClassification(camera, confidence=0.5, debounce_sec=0.0)

current_vision_classes = []

def handle_detections(classifications: dict):
    global current_vision_classes
    if len(classifications) == 0:
        current_vision_classes = []
    else:
        current_vision_classes = list(classifications.keys())
    
    person_detected = False
    person_confidence = None
    known_person_name = get_known_person_name()
    entries = []
    for key, value in classifications.items():
        if key.lower() == "person":
            person_detected = True
            person_confidence = value
        entries.append({
            "content": key,
            "confidence": value,
            "label": known_person_name if key.lower() == "person" and known_person_name else key,
        })
    if entries:
        ui.send_message("classifications", message=json.dumps(entries))
    else:
        ui.send_message("classifications", message=json.dumps([]))

    if not person_detected:
        return

    if known_person_name:
        if should_announce_known_person():
            mark_known_person_announced()
            confidence_text = (
                f" ({person_confidence:.0%} confidence)"
                if isinstance(person_confidence, (int, float))
                else ""
            )
            send_agent_response(f"I see {known_person_name}{confidence_text}.")
        return

    if should_ask_for_person_name():
        mark_asked_for_person_name()
        send_agent_response("I see a person. What is their name?")

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
            save_detected_person_name(name)
            answer = f"I will remember this person as {name}."
            print(f"Saved detected person name in Letta memory: {name}")
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
print("Initializing Letta agents...")
main_agent_id, memory_manager_agent_id = get_agents()
print(f"Letta main agent: {main_agent_id}")
print(f"Letta memory manager agent: {memory_manager_agent_id}")

ui.on_connect(on_ui_connect)
ui.on_message("chat_message", on_chat_message)
schedule_idle_memory_manager_check()

App.run()
