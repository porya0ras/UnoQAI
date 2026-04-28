from arduino.app_utils import App
from ui_instance import ui, send_agent_error, send_agent_response
from led_tools import extract_direct_led_text
import led_matrix
from letta_messaging import ask_letta
from background_tasks import schedule_memory_update, schedule_idle_memory_manager_check, cancel_idle_memory_manager_check
from config import LETTA_BASE_URL, MEMORY_MANAGER_IDLE_SECONDS

def on_chat_message(_sid, data):
    try:
        message = data.get("message", "").strip()

        if not message:
            send_agent_error("Message is empty")
            return

        cancel_idle_memory_manager_check()
        print(f"User: {message}")

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

        answer = ask_letta(message)

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

ui.on_message("chat_message", on_chat_message)
schedule_idle_memory_manager_check()

App.run()
