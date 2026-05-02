# LED Matrix — Technical Reference

Detailed reference for `led_matrix.py`. Read this file when you need to understand the pixel-level rendering pipeline, font definitions, or the Bridge notification protocol.

## Constants

| Constant | Value | Description |
|----------|-------|-------------|
| `WIDTH` | 13 | Matrix columns (pixels) |
| `HEIGHT` | 8 | Matrix rows (pixels) |
| `BRIGHTNESS` | 7 | Fixed brightness for lit pixels |
| `FRAME_WORDS` | 4 | Number of 32-bit words per frame bitmap |
| `SCROLL_DELAY_SECONDS` | 0.12 | Pause between scroll frames (seconds) |

## Font: FONT_3X5

Each glyph is 3 pixels wide × 5 pixels tall, stored as a list of 5 strings where `"1"` = lit and `"0"` = off.

Spacing between characters: **1 pixel**.

### Supported characters

```
A B C D E F G H I J K L M N O P Q R S T U V W X Y Z
0 1 2 3 4 5 6 7 8 9
(space) ? ! . -
```

### Full glyph definitions

```python
FONT_3X5 = {
    " ": ["000", "000", "000", "000", "000"],
    "?": ["111", "001", "011", "000", "010"],
    "!": ["010", "010", "010", "000", "010"],
    ".": ["000", "000", "000", "000", "010"],
    "-": ["000", "000", "111", "000", "000"],
    "0": ["111", "101", "101", "101", "111"],
    "1": ["010", "110", "010", "010", "111"],
    "2": ["111", "001", "111", "100", "111"],
    "3": ["111", "001", "111", "001", "111"],
    "4": ["101", "101", "111", "001", "001"],
    "5": ["111", "100", "111", "001", "111"],
    "6": ["111", "100", "111", "101", "111"],
    "7": ["111", "001", "010", "010", "010"],
    "8": ["111", "101", "111", "101", "111"],
    "9": ["111", "101", "111", "001", "111"],
    "A": ["010", "101", "111", "101", "101"],
    "B": ["110", "101", "110", "101", "110"],
    "C": ["111", "100", "100", "100", "111"],
    "D": ["110", "101", "101", "101", "110"],
    "E": ["111", "100", "110", "100", "111"],
    "F": ["111", "100", "110", "100", "100"],
    "G": ["111", "100", "101", "101", "111"],
    "H": ["101", "101", "111", "101", "101"],
    "I": ["111", "010", "010", "010", "111"],
    "J": ["001", "001", "001", "101", "111"],
    "K": ["101", "101", "110", "101", "101"],
    "L": ["100", "100", "100", "100", "111"],
    "M": ["101", "111", "111", "101", "101"],
    "N": ["101", "111", "111", "111", "101"],
    "O": ["111", "101", "101", "101", "111"],
    "P": ["111", "101", "111", "100", "100"],
    "Q": ["111", "101", "101", "111", "001"],
    "R": ["111", "101", "111", "110", "101"],
    "S": ["111", "100", "111", "001", "111"],
    "T": ["111", "010", "010", "010", "010"],
    "U": ["101", "101", "101", "101", "111"],
    "V": ["101", "101", "101", "101", "010"],
    "W": ["101", "101", "111", "111", "101"],
    "X": ["101", "101", "010", "101", "101"],
    "Y": ["101", "101", "010", "010", "010"],
    "Z": ["111", "001", "010", "100", "111"],
}
```

## Rendering pipeline

### 1. `normalize_text(text) → str`

Uppercases the input and strips any character not in `FONT_3X5`. If the result is empty, returns `"?"`.

### 2. `text_width(text) → int`

Calculates the pixel width of the rendered string:

```
width = len(text) × 3 + max(0, len(text) − 1) × 1
```

Each glyph is 3 px wide with 1 px spacing between glyphs.

### 3. `text_to_pixels(text, start_x=None) → list[list[int]]`

Returns an 8×13 grid (list of 8 rows, each a list of 13 ints). Lit pixels have value `BRIGHTNESS` (7), dark pixels are 0. Glyphs are placed starting at `start_y = 1` (row index). If `start_x` is `None`, text is horizontally centered.

### 4. `pixels_to_board_bytes(pixels) → list[int]`

Flattens the 2D pixel grid into a 1D list of 104 values (8 rows × 13 columns), row-major order.

### 5. `pixels_to_frame_words(pixels) → list[int]`

Converts the pixel grid to 4 × 32-bit integers. Each bit represents one pixel: 1 if lit, 0 if dark. Bit ordering: most-significant bit first within each word.

```python
frame_words[index // 32] |= 1 << (31 - (index % 32))
```

### 6. `notify_frame(frame_words, label)`

Sends the frame to the Arduino via `Bridge.notify("draw", frame_words)`.

## write_text(text) — Full flow

```
text
  → normalize_text()
  → text_width()
  ┌─ if width ≤ 13: static display
  │    → text_to_pixels() → pixels_to_frame_words() → notify_frame()
  │
  └─ if width > 13: scroll
       for frame_index in range(WIDTH + rendered_width + 1):
           start_x = WIDTH - frame_index
           → text_to_pixels(start_x=start_x) → pixels_to_frame_words() → notify_frame()
           sleep(0.12s)
```

Returns the normalized text string.

## clear()

Sends `Bridge.notify("clear")` with no payload. All LEDs turn off immediately.

## Bridge protocol

| Notification | Payload | Effect |
|-------------|---------|--------|
| `"draw"` | `[int, int, int, int]` — 4 frame words | Render bitmap on the 13×8 matrix |
| `"clear"` | *(none)* | Blank the entire matrix |

The Bridge communicates with the Arduino over serial via `arduino.app_utils.Bridge`.

## Integration with Letta

The `main.py` application registers `write_led_matrix_text` and `clear_led_matrix` as **client-side tools** with the Letta agent. When the agent invokes one of these tools:

1. The Letta server emits an `approval_request_message`.
2. `resolve_client_tool_requests()` in `main.py` intercepts the request.
3. `execute_led_client_tool()` calls the corresponding `led_matrix` function.
4. The result is sent back to Letta as an approval response with status `"success"` or `"error"`.

This keeps hardware control on the client side while letting the agent decide when to use the LED.
