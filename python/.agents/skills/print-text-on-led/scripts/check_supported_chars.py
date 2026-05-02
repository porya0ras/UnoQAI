#!/usr/bin/env python3
"""List all characters supported by the LED matrix font.

Prints every character in FONT_3X5 along with its glyph preview.

Usage:
    python scripts/check_supported_chars.py
"""

from led_renderer import FONT_3X5


def show_supported_chars():
    chars = sorted(FONT_3X5.keys())
    print(f"Supported characters ({len(chars)} total):\n")

    for ch in chars:
        glyph = FONT_3X5[ch]
        label = repr(ch) if ch == " " else ch
        rows = ["".join("█" if c == "1" else " " for c in row) for row in glyph]
        print(f"  {label:>5}  │ {rows[0]} │")
        for row in rows[1:]:
            print(f"       │ {row} │")
        print()

    print("Characters: " + " ".join(ch if ch != " " else "⎵" for ch in chars))


if __name__ == "__main__":
    show_supported_chars()
