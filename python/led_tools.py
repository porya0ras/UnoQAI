import json
import re
import led_matrix

LED_CLIENT_TOOLS = [
    {
        "name": "write_led_matrix_text",
        "description": (
            "Write short text on my Arduino UNO Q LED matrix. Use this whenever "
            "the user asks me to write, show, display, say, draw, or put letters "
            "or a word on my LEDs, matrix, face, light display, or little screen. "
            "Pass the user's requested text exactly; the client will truncate or "
            "scroll it to fit the tiny matrix."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "The exact text the user asked to show, for example HI, OK, YES, HALEH.",
                },
            },
            "required": ["text"],
        },
    },
    {
        "name": "clear_led_matrix",
        "description": (
            "Clear or turn off my Arduino UNO Q LED matrix when the user asks "
            "to clear, erase, switch off, or turn off the LEDs, matrix, face, "
            "or light display."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
]

LED_COMMAND_RE = re.compile(
    r"\b(?:draw|write|show|display|say|put)\b.*?[`\"']([^`\"']+)[`\"']",
    re.IGNORECASE,
)

def extract_direct_led_text(message):
    match = LED_COMMAND_RE.search(message)
    if match:
        return match.group(1).strip()
    return None

def execute_led_client_tool(tool_name, arguments):
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
