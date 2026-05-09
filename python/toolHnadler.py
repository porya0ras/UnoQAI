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

        return f"Unknown client tool: {tool_name}", "error"

    except Exception as e:
        return str(e), "error"
