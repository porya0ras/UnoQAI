from arduino.app_utils import Bridge


WIDTH = 13
HEIGHT = 8
BRIGHTNESS = 7
FRAME_WORDS = 4

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


def normalize_text(text):
    return "".join(ch for ch in text.upper() if ch in FONT_3X5)[:3] or "?"


def text_to_pixels(text):
    text = normalize_text(text)
    pixels = [[0 for _ in range(WIDTH)] for _ in range(HEIGHT)]
    glyph_width = 3
    spacing = 1
    text_width = len(text) * glyph_width + max(0, len(text) - 1) * spacing
    start_x = max(0, (WIDTH - text_width) // 2)
    start_y = 1

    x = start_x
    for ch in text:
        glyph = FONT_3X5[ch]
        for gy, row in enumerate(glyph):
            for gx, value in enumerate(row):
                if value == "1":
                    px = x + gx
                    py = start_y + gy
                    if 0 <= px < WIDTH and 0 <= py < HEIGHT:
                        pixels[py][px] = BRIGHTNESS
        x += glyph_width + spacing

    return pixels


def pixels_to_board_bytes(pixels):
    return [pixels[y][x] for y in range(HEIGHT) for x in range(WIDTH)]


def pixels_to_frame_words(pixels):
    frame_words = [0 for _ in range(FRAME_WORDS)]
    for index, value in enumerate(pixels_to_board_bytes(pixels)):
        if value:
            frame_words[index // 32] |= 1 << (31 - (index % 32))
    return frame_words


def write_text(text):
    normalized = normalize_text(text)
    pixels = text_to_pixels(normalized)
    frame_words = pixels_to_frame_words(pixels)
    active_pixels = sum(1 for value in pixels_to_board_bytes(pixels) if value)
    Bridge.notify("draw", frame_words)
    print(
        f"Bridge notify draw text='{text}' normalized='{normalized}' "
        f"active_pixels={active_pixels} words={len(frame_words)} -> "
        f"{[hex(word) for word in frame_words]}"
    )
    return normalized


def clear():
    Bridge.notify("clear")
    print(f"Bridge notify clear")
