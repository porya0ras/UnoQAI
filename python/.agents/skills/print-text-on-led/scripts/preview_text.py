#!/usr/bin/env python3
"""Preview how text will render on the 13×8 LED matrix.

Prints an ASCII grid showing which pixels would be lit,
without requiring an Arduino connection.

Usage:
    python scripts/preview_text.py <text>

Example:
    python scripts/preview_text.py "HI"
"""

import sys

from led_renderer import normalize_text, text_to_pixels, text_width, WIDTH, HEIGHT


def preview(text):
    normalized = normalize_text(text)
    rendered_width = text_width(normalized)
    will_scroll = rendered_width > WIDTH

    print(f"Input:      {text!r}")
    print(f"Normalized: {normalized!r}")
    print(f"Width:      {rendered_width} px  (matrix is {WIDTH} px wide)")
    print(f"Mode:       {'SCROLL' if will_scroll else 'STATIC (centered)'}")
    print()

    pixels = text_to_pixels(normalized)
    top_border = "┌" + "─" * (WIDTH * 2 + 1) + "┐"
    bot_border = "└" + "─" * (WIDTH * 2 + 1) + "┘"

    print(top_border)
    for row in pixels:
        cells = " ".join("█" if v else "·" for v in row)
        print(f"│ {cells} │")
    print(bot_border)

    active = sum(1 for row in pixels for v in row if v)
    print(f"\nActive pixels: {active} / {WIDTH * HEIGHT}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: preview_text.py <text>")
        print('Example: preview_text.py "HELLO"')
        sys.exit(1)
    preview(sys.argv[1])
