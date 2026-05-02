#!/usr/bin/env python3
"""Simulate the LED matrix scroll animation in the terminal.

Renders each frame as ASCII art with a short delay, mimicking
the real scroll behaviour on the 13×8 matrix.

Usage:
    python scripts/simulate_scroll.py <text> [delay_seconds]

Examples:
    python scripts/simulate_scroll.py "HELLO WORLD"
    python scripts/simulate_scroll.py "HELLO WORLD" 0.08
"""

import sys
import time

from led_renderer import (
    normalize_text, text_to_pixels, text_width,
    WIDTH, HEIGHT, SCROLL_DELAY_SECONDS,
)


def clear_screen():
    sys.stdout.write("\033[2J\033[H")
    sys.stdout.flush()


def render_frame(pixels, frame_num, total, normalized, delay):
    clear_screen()
    top = "┌" + "─" * (WIDTH * 2 + 1) + "┐"
    bot = "└" + "─" * (WIDTH * 2 + 1) + "┘"

    print(f"Simulating: {normalized!r}  (frame {frame_num}/{total}, delay={delay}s)")
    print(top)
    for row in pixels:
        cells = " ".join("█" if v else " " for v in row)
        print(f"│ {cells} │")
    print(bot)


def simulate(text, delay=None):
    normalized = normalize_text(text)
    rendered_width = text_width(normalized)
    delay = delay if delay is not None else SCROLL_DELAY_SECONDS

    if rendered_width <= WIDTH:
        pixels = text_to_pixels(normalized)
        render_frame(pixels, 1, 1, normalized, delay)
        print("\n✓ Text fits statically — no scrolling needed.")
        return

    total_frames = WIDTH + rendered_width + 1
    print(f"Scrolling {normalized!r} ({total_frames} frames, ~{total_frames * delay:.1f}s total)...")
    time.sleep(1)

    for i in range(total_frames):
        start_x = WIDTH - i
        pixels = text_to_pixels(normalized, start_x=start_x)
        render_frame(pixels, i + 1, total_frames, normalized, delay)
        time.sleep(delay)

    print("\n✓ Scroll complete.")


if __name__ == "__main__":
    if len(sys.argv) < 2 or len(sys.argv) > 3:
        print("Usage: simulate_scroll.py <text> [delay_seconds]")
        print('Example: simulate_scroll.py "HELLO WORLD" 0.08')
        sys.exit(1)

    text = sys.argv[1]
    delay = float(sys.argv[2]) if len(sys.argv) == 3 else None
    simulate(text, delay)
