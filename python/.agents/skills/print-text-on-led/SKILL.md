---
name: print-text-on-led
description: Use this skill whenever the user wants to display, write, show, draw, or put text on the Arduino UNO Q LED matrix, or when they want to clear, erase, or turn off the LED matrix. This covers scrolling long messages, showing short words, and blanking the display. If the user mentions LEDs, the matrix, or the "face" display, use this skill.
license: MIT
compatibility: Requires an Arduino UNO Q board connected via arduino.app_utils.Bridge. Python 3.10+.
metadata:
  author: porya0ras
  version: "1.0"
---

## Overview

The Arduino UNO Q has a **13 × 8 LED matrix** controlled through `led_matrix.py`. Text is rendered with a built-in 3×5 pixel font supporting A-Z, 0-9, and a handful of punctuation characters. Short text (≤ 13 px wide) is displayed statically, centered on the matrix. Longer text automatically scrolls left-to-right across the display.

Two Letta client-side tools expose this hardware to the agent:

| Tool name               | Purpose                        |
|--------------------------|-------------------------------|
| `write_led_matrix_text`  | Show text on the LED matrix    |
| `clear_led_matrix`       | Turn off / blank the display   |

For the full font map and low-level API details, see [reference.md](reference.md).

## Displaying text

1. Receive the user's requested text (e.g. "HI", "HELLO WORLD").
2. Call the `write_led_matrix_text` client tool with `{"text": "<user text>"}`.
3. The tool normalizes the text to uppercase and drops unsupported characters.
4. If the rendered width fits within 13 pixels the text is shown statically, centered.
5. If the rendered width exceeds 13 pixels the text scrolls automatically (≈ 0.12 s per frame).
6. Report back to the user what was displayed.

```python
# Direct usage (inside the Python app, not from the agent)
import led_matrix

led_matrix.write_text("HI")      # static, centered
led_matrix.write_text("HELLO!")   # scrolls automatically
```

## Clearing the display

1. Call the `clear_led_matrix` client tool with `{}` (no parameters).
2. This sends a `clear` notification via the Bridge and blanks every LED.
3. Confirm to the user that the display was cleared.

```python
# Direct usage
import led_matrix

led_matrix.clear()
```

## Client tool definitions

When registering tools with the Letta agent, use these JSON schemas:

```json
{
  "name": "write_led_matrix_text",
  "description": "Write short text on my Arduino UNO Q LED matrix. Use this whenever the user asks me to write, show, display, say, draw, or put letters or a word on my LEDs, matrix, face, light display, or little screen. Pass the user's requested text exactly; the client will truncate or scroll it to fit the tiny matrix.",
  "parameters": {
    "type": "object",
    "properties": {
      "text": {
        "type": "string",
        "description": "The exact text the user asked to show, for example HI, OK, YES, HALEH."
      }
    },
    "required": ["text"]
  }
}
```

```json
{
  "name": "clear_led_matrix",
  "description": "Clear or turn off my Arduino UNO Q LED matrix when the user asks to clear, erase, switch off, or turn off the LEDs, matrix, face, or light display.",
  "parameters": {
    "type": "object",
    "properties": {},
    "required": []
  }
}
```

## Direct LED shortcut (regex fast-path)

`main.py` also provides a regex-based shortcut that bypasses the Letta round-trip. If the user message matches a pattern like `show "HI"` or `write 'HELLO'`, the text is extracted and sent directly to `led_matrix.write_text()`. This is faster but skips agent reasoning.

Pattern: `\b(?:draw|write|show|display|say|put)\b.*?[`"']([^`"']+)[`"']`

## Gotchas

- **Supported characters only:** The font covers A-Z, 0-9, space, `?`, `!`, `.`, and `-`. Any other character is silently dropped during normalization. If every character is dropped, a single `?` is displayed.
- **Case insensitive:** Input is uppercased automatically; do not worry about casing.
- **Brightness is fixed:** All lit pixels use brightness level 7. There is no per-pixel dimming.
- **Scroll blocking:** `write_text()` blocks the calling thread for the entire scroll duration. For long messages this can take several seconds.
- **Bridge dependency:** `Bridge.notify("draw", ...)` and `Bridge.notify("clear")` communicate with the Arduino over serial. If the Bridge is not connected, calls will fail silently or raise.

## Quick reference

| Task | Function / Tool | Notes |
|------|----------------|-------|
| Show short text | `write_led_matrix_text` | Centered, static |
| Show long text | `write_led_matrix_text` | Auto-scrolls |
| Clear display | `clear_led_matrix` | Blanks all LEDs |
| Normalize text | `led_matrix.normalize_text()` | Uppercase + filter |
| Measure width | `led_matrix.text_width()` | In pixels |

## Bundled scripts

The `scripts/` directory contains self-contained CLI utilities that work **without Arduino hardware**. Run from the skill directory.

| Script | Purpose |
|--------|---------|
| `scripts/preview_text.py` | ASCII preview of how text renders on the 13×8 grid |
| `scripts/validate_text.py` | Check character support, rendering mode, scroll duration |
| `scripts/check_supported_chars.py` | List every character in the font with glyph previews |
| `scripts/generate_frame_words.py` | Output raw 4×32-bit frame words (hex + JSON) |
| `scripts/simulate_scroll.py` | Terminal animation simulating the real scroll |
| `scripts/extract_tool_schemas.py` | Print the Letta client tool JSON schemas |

### Usage examples

```bash
# Preview how "HI" looks on the matrix
python scripts/preview_text.py "HI"

# Validate a message before sending
python scripts/validate_text.py "Hello World!"

# List all supported characters
python scripts/check_supported_chars.py

# Get frame words for debugging
python scripts/generate_frame_words.py "OK"

# Watch a scroll animation in the terminal
python scripts/simulate_scroll.py "HELLO WORLD" 0.08

# Extract tool schemas as JSON
python scripts/extract_tool_schemas.py
```

## Next steps

- For the full 3×5 font map and pixel-level API, see [reference.md](reference.md).
- Use the [scripts/](scripts/) for offline testing and debugging without hardware.
