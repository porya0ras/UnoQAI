#!/usr/bin/env python3
"""Generate the raw frame words (4 × 32-bit ints) for a given text.

Outputs the hex values that would be sent to Bridge.notify("draw", ...).
Useful for debugging or pre-computing frames.

Usage:
    python scripts/generate_frame_words.py <text>

Example:
    python scripts/generate_frame_words.py "OK"
"""

import json
import sys

from led_renderer import normalize_text, text_to_pixels, pixels_to_frame_words, text_width, WIDTH


def generate(text):
    normalized = normalize_text(text)
    rendered_width = text_width(normalized)
    will_scroll = rendered_width > WIDTH

    if will_scroll:
        total_frames = WIDTH + rendered_width + 1
        print(f"Text '{normalized}' will scroll — generating {total_frames} frames\n")
        frames = []
        for i in range(total_frames):
            start_x = WIDTH - i
            fw = pixels_to_frame_words(text_to_pixels(normalized, start_x=start_x))
            frames.append(fw)
            hex_values = [f"0x{w:08x}" for w in fw]
            print(f"  Frame {i + 1:3d}/{total_frames}: [{', '.join(hex_values)}]")

        print(f"\nTotal frames: {total_frames}")
        print(f"JSON array:")
        print(json.dumps(frames, indent=2))
    else:
        pixels = text_to_pixels(normalized)
        fw = pixels_to_frame_words(pixels)
        hex_values = [f"0x{w:08x}" for w in fw]
        print(f"Text:       {normalized!r}")
        print(f"Mode:       STATIC")
        print(f"Frame words: [{', '.join(hex_values)}]")
        print(f"\nJSON: {json.dumps(fw)}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: generate_frame_words.py <text>")
        print('Example: generate_frame_words.py "OK"')
        sys.exit(1)
    generate(sys.argv[1])
