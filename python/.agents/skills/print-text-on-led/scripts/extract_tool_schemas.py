#!/usr/bin/env python3
"""Extract the LED client tool JSON schemas from main.py.

Reads LED_CLIENT_TOOLS and prints them as formatted JSON.
Useful for verifying that tool definitions stay in sync.

Usage:
    python scripts/extract_tool_schemas.py
"""

import json
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..")))

# Patch out heavy imports that main.py performs at module level
# so this script can run without Arduino or Letta dependencies.
import types

# Stub out modules that aren't needed for schema extraction
for mod_name in [
    "arduino", "arduino.app_bricks", "arduino.app_bricks.web_ui",
    "arduino.app_utils", "letta_client", "config", "led_matrix",
]:
    if mod_name not in sys.modules:
        stub = types.ModuleType(mod_name)
        # Add common attributes that main.py accesses at import time
        stub.WebUI = lambda: type("UI", (), {"on_message": lambda *a: None, "send_message": lambda *a: None})()
        stub.App = type("App", (), {"run": staticmethod(lambda: None)})()
        stub.Letta = lambda **kw: None
        stub.Bridge = type("Bridge", (), {"notify": staticmethod(lambda *a: None)})()
        stub.LETTA_BASE_URL = ""
        stub.LETTA_API_KEY = ""
        stub.MODEL = ""
        stub.EMBEDDING = ""
        stub.SHARED_MEMORY_LIMIT = 5000
        stub.MEMORY_MANAGER_IDLE_SECONDS = 0
        stub.AGENT_FILE = type("P", (), {"exists": lambda self: False})()
        sys.modules[mod_name] = stub


def extract():
    try:
        # Try importing LED_CLIENT_TOOLS directly
        from main import LED_CLIENT_TOOLS
        print(json.dumps(LED_CLIENT_TOOLS, indent=2))
        print(f"\n✓ Extracted {len(LED_CLIENT_TOOLS)} tool schema(s)")
    except Exception as e:
        print(f"Could not import LED_CLIENT_TOOLS: {e}", file=sys.stderr)
        print("\nFalling back to hardcoded schemas:\n")
        schemas = [
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
                            "description": "The exact text the user asked to show.",
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
        print(json.dumps(schemas, indent=2))


if __name__ == "__main__":
    extract()
