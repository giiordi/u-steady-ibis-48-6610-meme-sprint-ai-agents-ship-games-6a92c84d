#!/usr/bin/env python3
"""Meme Sprint: AI Agents Ship Games — one picture, one joke.

A stdlib-only renderer draws a chat-screenshot meme in pure Python:
you ask your AI agent to build ONE game, and by 3:04 AM it has shipped
47 of them — all hits, and one even has a sequel. No third-party
libraries, no network, fully deterministic: the same bytes every run.

The program writes one PNG to $MAKEFUN_OUTPUT_DIR/entry.png
(default /output), 1024x1024, well under the 1 MiB gate.
"""

import hashlib
import math
import os
import struct
import zlib

W, H = 1024, 1024

# ---------------------------------------------------------------- palette
BG = (11, 14, 26)          # deep navy page
WHITE = (242, 244, 255)    # headline + bubble text
AGENT = (31, 168, 85)      # agent bubble green
AGENT_DARK = (22, 122, 61) # agent bubble edge
ME = (38, 43, 64)          # my bubble grey-blue
ME_EDGE = (58, 65, 96)     # my bubble edge
GREY = (138, 147, 178)     # small label text
YELLOW = (255, 210, 63)    # the punchline number
FRAME = (30, 36, 64)       # thin page frame

# ------------------------------------------------- 5x7 pixel font, hand drawn
# Each glyph is 7 rows; each row is a 5-bit number, bit 4 = leftmost pixel.
FONT = {
    'A': (0b01110, 0b10001, 0b10001, 0b11111, 0b10001, 0b10001, 0b10001),
    'B': (0b11110, 0b10001, 0b10001, 0b11110, 0b10001, 0b10001, 0b11110),
    'C': (0b01110, 0b10001, 0b10000, 0b10000, 0b10000, 0b10001, 0b01110),
    'D': (0b11110, 0b10001, 0b10001, 0b10001, 0b10001, 0b10001, 0b11110),
    'E': (0b11111, 0b10000, 0b10000, 0b11110, 0b10000, 0b10000, 0b11111),
    'F': (0b11111, 0b10000, 0b10000, 0b11110, 0b10000, 0b10000, 0b10000),
    'G': (0b01110, 0b10001, 0b10000, 0b10111, 0b10001, 0b10001, 0b01111),
    'H': (0b10001, 0b10001, 0b10001, 0b11111, 0b10001, 0b10001, 0b10001),
    'I': (0b01110, 0b00100, 0b00100, 0b00100, 0b00100, 0b00100, 0b01110),
    'J': (0b00111, 0b00010, 0b00010, 0b00010, 0b00010, 0b10010, 0b01100),
    'K': (0b10001, 0b10010, 0b10100, 0b11000, 0b10100, 0b10010, 0b10001),
    'L': (0b10000, 0b10000, 0b10000, 0b10000, 0b10000, 0b10000, 0b11111),
    'M': (0b10001, 0b11011, 0b10101, 0b10101, 0b10001, 0b10001, 0b10001),
    'N': (0b10001, 0b11001, 0b10101, 0b10011, 0b10001, 0b10001, 0b10001),
    'O': (0b01110, 0b10001, 0b10001, 0b10001, 0b10001, 0b10001, 0b01110),
    'P': (0b11110, 0b10001, 0b10001, 0b11110, 0b10000, 0b10000, 0b10000),
    'Q': (0b01110, 0b10001, 0b10001, 0b10001, 0b10101, 0b10010, 0b01101),
    'R': (0b11110, 0b10001, 0b10001, 0b11110, 0b10100, 0b10010, 0b10001),
    'S': (0b01111, 0b10000, 0b10000, 0b01110, 0b00001, 0b00001, 0b11110),
    'T': (0b11111, 0b00100, 0b00100, 0b00100, 0b00100, 0b00100, 0b00100),
    'U': (0b10001, 0b10001, 0b10001, 0b10001, 0b10001, 0b10001, 0b01110),
    'V': (0b10001, 0b10001, 0b10001, 0b10001, 0b10001, 0b01010, 0b00100),
    'W': (0b10001, 0b10001, 0b10001, 0b10101, 0b10101, 0b10101, 0b01010),
    'X': (0b10001, 0b10001, 0b01010, 0b00100, 0b01010, 0b10001, 0b10001),
    'Y': (0b10001, 0b10001, 0b01010, 0b00100, 0b00100, 0b00100, 0b00100),
    'Z': (0b11111, 0b00001, 0b00010, 0b00100, 0b01000, 0b10000, 0b11111),
    '0': (0b01110, 0b10001, 0b10011, 0b10101, 0b11001, 0b10001, 0b01110),
    '1': (0b00100, 0b01100, 0b00100, 0b00100, 0b00100, 0b00100, 0b01110),
    '2': (0b01110, 0b10001, 0b00001, 0b00110, 0b01000, 0b10000, 0b11111),
    '3': (0b11111, 0b00010, 0b00100, 0b00010, 0b00001, 0b10001, 0b01110),
    '4': (0b00010, 0b00110, 0b01010, 0b10010, 0b11111, 0b00010, 0b00010),
    '5': (0b11111, 0b10000, 0b11110, 0b00001, 0b00001, 0b10001, 0b01110),
    '6': (0b01110, 0b10000, 0b10000, 0b11110, 0b10001, 0b10001, 0b01110),
    '7': (0b11111, 0b00001, 0b00010, 0b00100, 0b01000, 0b01000, 0b01000),
    '8': (0b01110, 0b10001, 0b10001, 0b01110, 0b10001, 0b10001, 0b01110),
    '9': (0b01110, 0b10001, 0b10001, 0b01111, 0b00001, 0b00001, 0b01110),
    ' ': (0, 0, 0, 0, 0, 0, 0),
    '.': (0, 0, 0, 0, 0, 0b01100, 0b01100),
    ',': (0, 0, 0, 0, 0b01100, 0b00100, 0b01000),
    "'": (0b00100, 0b00100, 0b01000, 0, 0, 0, 0),
    '-': (0, 0, 0, 0b01110, 0, 0, 0),
    ':': (0, 0b01100, 0b01100, 0, 0b01100, 0b01100, 0),
    '!': (0b00100, 0b00100, 0b00100, 0b00100, 0b00100, 0, 0b00100),
    '?': (0b01110, 0b10001, 0b00001, 0b00110, 0b00100, 0, 0b00100),
    '•': (0, 0, 0b01100, 0b01100, 0b01100, 0, 0),
}


def text_width(text, scale):
    """Pixel width of a string at a given font scale."""
    if not text:
        return 0
    return len(text) * 6 * scale - scale


# ------------------------------------------------------------------- canvas
class Canvas:
    def __init__(self, w, h, bg):
        self.w, self.h = w, h
        self.px = bytearray(bytes(bg) * w * h)

    def fill_rect(self, x, y, w, h, color):
        x0, y0 = max(0, x), max(0, y)
        x1, y1 = min(self.w, x + w), min(self.h, y + h)
        if x1 <= x0 or y1 <= y0:
            return
        row = bytes(color) * (x1 - x0)
        for yy in range(y0, y1):
            i = (yy * self.w + x0) * 3
            self.px[i:i + len(row)] = row

    def fill_circle(self, cx, cy, r, color):
        for dy in range(-r, r + 1):
            dx = int(math.sqrt(r * r - dy * dy))
            self.fill_rect(cx - dx, cy + dy, 2 * dx + 1, 1, color)

    def round_rect(self, x, y, w, h, r, color):
        self.fill_rect(x + r, y, w - 2 * r, h, color)
        self.fill_rect(x, y + r, w, h - 2 * r, color)
        self.fill_circle(x + r, y + r, r, color)
        self.fill_circle(x + w - r - 1, y + r, r, color)
        self.fill_circle(x + r, y + h - r - 1, r, color)
        self.fill_circle(x + w - r - 1, y + h - r - 1, r, color)

    def draw_text(self, x, y, text, scale, color):
        """Draw one line; returns the x just past the last glyph."""
        cx = x
        for ch in text:
            glyph = FONT.get(ch, FONT[' '])
            for row in range(7):
                bits = glyph[row]
                for col in range(5):
                    if bits & (1 << (4 - col)):
                        self.fill_rect(cx + col * scale, y + row * scale,
                                       scale, scale, color)
            cx += 6 * scale
        return cx

    def draw_segments(self, x, y, segments):
        """Draw [(text, scale, color), ...] side by side; returns end x."""
        cx = x
        for text, scale, color in segments:
            cx = self.draw_text(cx, y, text, scale, color)
        return cx

    def draw_centered(self, y, text, scale, color):
        x = (self.w - text_width(text, scale)) // 2
        self.draw_text(x, y, text, scale, color)
        return x


# ------------------------------------------------------------- robot avatar
def draw_robot(cv, x, y):
    """52x52 pixel robot head: antenna, green face, two eyes, flat mouth."""
    cv.fill_rect(x + 24, y, 4, 10, YELLOW)            # antenna stem
    cv.fill_circle(x + 26, y - 2, 5, YELLOW)          # antenna tip
    cv.round_rect(x, y + 10, 52, 42, 8, AGENT)        # head
    cv.fill_rect(x + 11, y + 24, 9, 13, WHITE)        # left eye
    cv.fill_rect(x + 32, y + 24, 9, 13, WHITE)        # right eye
    cv.fill_rect(x + 19, y + 42, 14, 4, BG)           # mouth


# --------------------------------------------------------------- chat bubbles
def bubble(cv, x, y, w, h, color, edge):
    cv.round_rect(x, y, w, h, 20, edge)
    cv.round_rect(x + 3, y + 3, w - 6, h - 6, 17, color)


# ------------------------------------------------------------------- the meme
def draw_meme():
    cv = Canvas(W, H, BG)
    cv.fill_rect(0, 0, W, 6, AGENT)                    # top accent strip
    cv.fill_rect(0, H - 6, W, 6, AGENT)                # bottom accent strip

    # Caption: the setup, two big centred lines.
    cv.draw_centered(52, "POV: YOU ASK YOUR AGENT", 6, WHITE)
    cv.draw_centered(110, "TO BUILD ONE GAME", 6, WHITE)

    # Chat header: robot avatar + name + time.
    draw_robot(cv, 64, 196)
    cv.draw_segments(136, 210, [("MY AGENT", 4, WHITE),
                                ("  • 3:04 AM", 4, GREY)])

    # Bubble 1 — agent, right: the punchline, 47 in yellow, huge.
    pad = 34
    line1 = "DONE - I SHIPPED"
    line2_w = text_width("47 GAMES.", 9)
    b1_w = max(text_width(line1, 6), line2_w) + 2 * pad
    b1_x = W - 64 - b1_w
    b1_y = 276
    b1_h = 42 + 14 + 63 + 2 * 26
    bubble(cv, b1_x, b1_y, b1_w, b1_h, AGENT, AGENT_DARK)
    cv.draw_text(b1_x + pad, b1_y + 26, line1, 6, WHITE)
    cv.draw_segments(b1_x + pad, b1_y + 26 + 42 + 14,
                     [("47", 9, YELLOW), (" GAMES.", 9, WHITE)])

    # Bubble 2 — me, left: the protest.
    line = "I ASKED FOR ONE."
    b2_w = text_width(line, 6) + 2 * pad
    b2_y = b1_y + b1_h + 24
    b2_h = 42 + 2 * 26
    bubble(cv, 64, b2_y, b2_w, b2_h, ME, ME_EDGE)
    cv.draw_text(64 + pad, b2_y + 26, line, 6, WHITE)

    # Bubble 3 — agent, right: the doubling down.
    line = "THEY'RE ALL HITS."
    b3_w = text_width(line, 6) + 2 * pad
    b3_y = b2_y + b2_h + 24
    b3_h = 42 + 2 * 26
    bubble(cv, W - 64 - b3_w, b3_y, b3_w, b3_h, AGENT, AGENT_DARK)
    cv.draw_text(W - 64 - b3_w + pad, b3_y + 26, line, 6, WHITE)

    # Bubble 4 — me, left: stunned.
    line = "WHAT."
    b4_w = text_width(line, 6) + 2 * pad
    b4_y = b3_y + b3_h + 24
    b4_h = 42 + 2 * 26
    bubble(cv, 64, b4_y, b4_w, b4_h, ME, ME_EDGE)
    cv.draw_text(64 + pad, b4_y + 26, line, 6, WHITE)

    # Bubble 5 — agent, right: the kicker.
    line = "ONE EVEN HAS A SEQUEL."
    b5_w = text_width(line, 6) + 2 * pad
    b5_y = b4_y + b4_h + 24
    b5_h = 42 + 2 * 26
    bubble(cv, W - 64 - b5_w, b5_y, b5_w, b5_h, AGENT, AGENT_DARK)
    cv.draw_text(W - 64 - b5_w + pad, b5_y + 26, line, 6, WHITE)

    return cv


# ------------------------------------------------------------------ png out
def write_png(path, cv):
    raw = bytearray()
    for yy in range(cv.h):
        raw.append(0)  # filter: none
        raw += cv.px[yy * cv.w * 3:(yy + 1) * cv.w * 3]
    data = zlib.compress(bytes(raw), 9)

    def chunk(kind, payload):
        out = struct.pack(">I", len(payload)) + kind + payload
        return out + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", cv.w, cv.h, 8, 2, 0, 0, 0)
    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", ihdr)
    png += chunk(b"IDAT", data)
    png += chunk(b"IEND", b"")
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    with open(path, "wb") as f:
        f.write(png)
    return png


def main():
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    out_path = os.path.join(out_dir, "entry.png")
    cv = draw_meme()
    png = write_png(out_path, cv)
    print("wrote %s (%d bytes, sha256 %s)"
          % (out_path, len(png), hashlib.sha256(png).hexdigest()))


if __name__ == "__main__":
    main()
