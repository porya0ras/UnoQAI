import json
from tools import led_matrix

def execute_tool(tool_name, arguments):
    try:
        if isinstance(arguments, str):
            arguments = json.loads(arguments or "{}")

        if tool_name == "write_led_matrix_text":
            rendered_text = led_matrix.write_text(arguments.get("text", ""))
            print(f"LED matrix text: {rendered_text}")
            return f"Wrote '{rendered_text}' on my LED matrix.", "success"

        if tool_name == "clear_led_matrix":
            led_matrix.clear()
            print("LED matrix cleared")
            return "Cleared my LED matrix.", "success"

        if tool_name == "get_camera_status":
            # Stub: in a real scenario, this would check the camera hardware or service
            return "Camera is active and streaming.", "success"

        if tool_name == "get_latest_detections":
            # Stub: return some mock detected objects
            return "Latest detections: Person (95%), Drone (80%).", "success"

        return f"Unknown client tool: {tool_name}", "error"

    except Exception as e:
        return str(e), "error"
