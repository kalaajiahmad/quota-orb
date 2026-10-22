"""Pixel-exact OLED renderer. Standard library only; same bytes go to USB/PNG."""
import struct
import zlib

from .model import countdown, freshness
from .files import atomic_write

# Original 5x7 bitmap alphabet, rows top to bottom; no host font dependency.
GLYPHS = {
    " ": "00000/00000/00000/00000/00000/00000/00000",
    "0": "01110/10001/10011/10101/11001/10001/01110",
    "1": "00100/01100/00100/00100/00100/00100/01110",
    "2": "01110/10001/00001/00010/00100/01000/11111",
    "3": "11110/00001/00001/01110/00001/00001/11110",
    "4": "00010/00110/01010/10010/11111/00010/00010",
    "5": "11111/10000/10000/11110/00001/00001/11110",
    "6": "01110/10000/10000/11110/10001/10001/01110",
    "7": "11111/00001/00010/00100/01000/01000/01000",
    "8": "01110/10001/10001/01110/10001/10001/01110",
    "9": "01110/10001/10001/01111/00001/00001/01110",
    "A": "01110/10001/10001/11111/10001/10001/10001",
    "B": "11110/10001/10001/11110/10001/10001/11110",
    "C": "01111/10000/10000/10000/10000/10000/01111",
    "D": "11110/10001/10001/10001/10001/10001/11110",
    "E": "11111/10000/10000/11110/10000/10000/11111",
    "F": "11111/10000/10000/11110/10000/10000/10000",
    "G": "01111/10000/10000/10111/10001/10001/01111",
    "H": "10001/10001/10001/11111/10001/10001/10001",
    "I": "01110/00100/00100/00100/00100/00100/01110",
    "J": "00111/00010/00010/00010/10010/10010/01100",
    "K": "10001/10010/10100/11000/10100/10010/10001",
    "L": "10000/10000/10000/10000/10000/10000/11111",
    "M": "10001/11011/10101/10101/10001/10001/10001",
    "N": "10001/11001/10101/10011/10001/10001/10001",
    "O": "01110/10001/10001/10001/10001/10001/01110",
    "P": "11110/10001/10001/11110/10000/10000/10000",
    "Q": "01110/10001/10001/10001/10101/10010/01101",
    "R": "11110/10001/10001/11110/10100/10010/10001",
    "S": "01111/10000/10000/01110/00001/00001/11110",
    "T": "11111/00100/00100/00100/00100/00100/00100",
    "U": "10001/10001/10001/10001/10001/10001/01110",
    "V": "10001/10001/10001/10001/10001/01010/00100",
    "W": "10001/10001/10001/10101/10101/10101/01010",
    "X": "10001/10001/01010/00100/01010/10001/10001",
    "Y": "10001/10001/01010/00100/00100/00100/00100",
    "Z": "11111/00001/00010/00100/01000/10000/11111",
    "%": "11001/11010/00010/00100/01000/01011/10011",
    "-": "00000/00000/00000/11111/00000/00000/00000",
    ":": "00000/00100/00100/00000/00100/00100/00000",
    "/": "00001/00010/00010/00100/01000/01000/10000",
    "?": "01110/10001/00001/00010/00100/00000/00100",
    ".": "00000/00000/00000/00000/00000/00110/00110",
}


class Canvas:
    width, height = 128, 64

    def __init__(self):
        self.data = bytearray(1024)

    def pixel(self, x, y, on=True):
        if 0 <= x < 128 and 0 <= y < 64:
            index, mask = x + (y // 8) * 128, 1 << (y % 8)
            if on:
                self.data[index] |= mask
            else:
                self.data[index] &= ~mask

    def rect(self, x, y, width, height, fill=True):
        for dy in range(height):
            for dx in range(width):
                if fill or dy in (0, height - 1) or dx in (0, width - 1):
                    self.pixel(x + dx, y + dy)

    def text(self, x, y, text, scale=1, limit=128):
        for char in text.upper():
            if x + 5 * scale > limit:
                break
            for dy, row in enumerate(GLYPHS.get(char, GLYPHS["?"]).split("/")):
                for dx, bit in enumerate(row):
                    if bit == "1":
                        self.rect(x + dx * scale, y + dy * scale, scale, scale)
            x += 6 * scale

    def robot(self, x, y, tick=0, sad=False):
        self.rect(x + 3, y + 4, 21, 16, False)
        self.rect(x + 12, y, 2, 4)
        self.rect(x + 11, y, 4, 2)
        self.rect(x, y + 9, 2, 6)
        self.rect(x + 25, y + 9, 2, 6)
        blink = tick % 11 == 10
        self.rect(x + 7, y + 9, 3, 1 if blink else 4)
        self.rect(x + 17, y + 9, 3, 1 if blink else 4)
        if sad:
            self.rect(x + 11, y + 16, 5, 1)
        else:
            self.pixel(x + 10, y + 15)
            self.rect(x + 11, y + 16, 5, 1)
            self.pixel(x + 16, y + 15)


def render(snapshot, now, page=0, error=False, stale_seconds=150, tick=None, provider='codex'):
    c = Canvas()
    status = freshness(snapshot, now, error, stale_seconds)
    tick = int(now) if tick is None else tick
    window = snapshot.windows[page % len(snapshot.windows)] if snapshot else None
    if window and window.blocked and status == "LIVE":
        status = "BLOCKED"
    if window and window.resets_at is not None and window.resets_at <= now and status == "LIVE":
        status = "CHECK"
    c.text(0, 0, provider.upper())
    sx = 128 - len(status) * 6 + 1
    c.text(sx, 0, status)
    if status != "LIVE" or tick % 2 == 0:
        c.rect(sx - 7, 2, 3, 3, status == "LIVE")
    c.rect(0, 10, 128, 1)
    if window:
        # Model-specific buckets are identified instead of being conflated with Codex.
        label = window.label if window.bucket in {"codex", "claude"} else f"{window.bucket} {window.label}"
        c.text(0, 14, label, limit=104)
        if len(snapshot.windows) > 1:
            c.text(109, 14, f"{page % len(snapshot.windows) + 1}/{len(snapshot.windows)}")
        # Floor remaining so fractional allowances are never overstated.
        percent = str(int(window.remaining))
        c.text(0, 25, percent, scale=3)
        edge = len(percent) * 18 + 1
        c.text(edge, 25, "%", scale=2)
        c.text(edge, 40, "LEFT")
        c.robot(100, 24, tick, status not in {"LIVE", "CHECK"})
        c.rect(0, 49, 128, 5, False)
        width = int(124 * window.remaining / 100)
        if width:
            c.rect(2, 51, width, 1)
        footer = countdown(window.resets_at, now)
        c.text(0, 57, footer)
        age = max(0, int(now - snapshot.fetched_at))
        age_text = f"{age}S" if age < 1000 else f"{min(age // 60, 999)}M"
        if len(footer) <= 14:
            c.text(128 - len(age_text) * 6 + 1, 57, age_text)
    else:
        c.text(0, 22, "WAITING FOR")
        c.text(0, 34, provider.upper()+" DATA")
        c.robot(100, 24, tick, True)
        c.text(0, 57, "CHECK PC BRIDGE")
    return bytes(c.data)


def png_bytes(frame, scale=4):
    if len(frame) != 1024 or not 1 <= scale <= 16:
        raise ValueError("Expected a 128x64 page-packed frame and scale 1..16")
    rows = bytearray()
    for y in range(64):
        row = bytearray()
        for x in range(128):
            on = frame[x + (y // 8) * 128] & (1 << (y % 8))
            row.extend((bytes((220, 249, 240)) if on else bytes((7, 15, 19))) * scale)
        rows.extend((b"\0" + row) * scale)

    def chunk(name, data):
        return struct.pack(">I", len(data)) + name + data + struct.pack(">I", zlib.crc32(name + data))

    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 128 * scale, 64 * scale, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(bytes(rows))) + chunk(b"IEND", b""))


def save_png(path, frame, scale=4):
    atomic_write(path,png_bytes(frame,scale))
