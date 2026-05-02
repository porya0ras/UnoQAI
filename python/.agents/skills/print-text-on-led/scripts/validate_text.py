#!/usr/bin/env python3
"""Validate text for LED matrix compatibility.

Checks which characters are supported, which will be dropped,
and whether the text will scroll or display statically.

Usage:
    python scripts/validate_text.py <text>

Example:
    python scripts/validate_text.py "Hello World!"
"""

import sys

from led_renderer import FONT_3X5, normalize_text, text_width, WIDTH


def validate(text):
    upper = text.upper()
    supported = []
    unsupported = []

    for ch in upper:
        if ch in FONT_3X5:
            supported.append(ch)
        else:
            unsupported.append(ch)

    normalized = normalize_text(text)
    rendered_width = text_width(normalized)

    print(f"Input:        {text!r}")
    print(f"Uppercased:   {upper!r}")
    print(f"Normalized:   {normalized!r}")
    print()

    if unsupported:
        unique = sorted(set(unsupported))
        print(f"⚠  Unsupported characters (will be dropped): {unique}")
    else:
        print("✓  All characters are supported")

    print()
    print(f"Rendered width: {rendered_width} px")
    print(f"Matrix width:   {WIDTH} px")

    if rendered_width <= WIDTH:
        print("✓  Text fits — will display STATICALLY (centered)")
    else:
        total_frames = WIDTH + rendered_width + 1
        duration = total_frames * 0.12
        print(f"→  Text overflows — will SCROLL ({total_frames} frames, ~{duration:.1f}s)")

    if not supported:
        print("\n⚠  No valid characters! A single '?' will be displayed.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: validate_text.py <text>")
        print('Example: validate_text.py "Hello World!"')
        sys.exit(1)
    validate(sys.argv[1])
