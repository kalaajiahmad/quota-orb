"""Compact desktop view of the monitor's locally rendered frame.

This is a movable application window, not a native OS widget. It reads the
monitor status and does not open a provider session or a USB connection.
"""
import base64
import json
import re
from pathlib import Path
import time
import tkinter as tk

from .files import atomic_write
from .render import png_bytes
from .ui import BG, MUTED, TEXT


def rendered_pixels(status):
    """Accept only a complete 128 x 64 monochrome frame."""
    try:
        pixels = bytes.fromhex(status['rendered_frame'])
        return pixels if len(pixels) == 1024 else None
    except (KeyError, TypeError, ValueError):
        return None


def widget_status(status, now=None):
    now = time.time() if now is None else now
    if not status.get('running'):
        return 'MONITOR STOPPED'
    if now - status.get('updated_at', 0) > 6:
        return 'MONITOR NOT RESPONDING'
    if status.get('paused'):
        return 'PAUSED'
    return str(status.get('source', 'NO DATA'))


def load_preferences(runtime):
    try:
        data = json.loads((Path(runtime) / 'desktop-widget.json').read_text(encoding='utf-8'))
        if not isinstance(data, dict):
            return {}
        return data
    except (OSError, ValueError):
        return {}


def position_from_geometry(geometry):
    """Keep Tk's signed edge offsets, which round-trip across monitors."""
    if not isinstance(geometry, str):
        return None
    match = re.fullmatch(r'(?:\d+x\d+)?([+-]\d+[+-]\d+)', geometry)
    return match.group(1) if match else None


def save_preferences(runtime, enabled, x=None, y=None, position=None):
    data = {'enabled': bool(enabled)}
    if type(x) is int and type(y) is int:
        data.update(x=x, y=y)
    position = position_from_geometry(position)
    if position:
        data['position'] = position
    atomic_write(Path(runtime) / 'desktop-widget.json', json.dumps(data).encode('utf-8'))


class DesktopWidget:
    def __init__(self, parent, runtime, on_close, demo=False):
        self.runtime = Path(runtime)
        self.on_close = on_close
        self.demo = demo
        self.window = tk.Toplevel(parent)
        self.window.title('Quota Orb widget')
        self.window.configure(bg=BG)
        self.window.resizable(False, False)
        self.window.protocol('WM_DELETE_WINDOW', self.close)
        self.image = None
        self.frame = None
        self.save_timer = None
        self.label = tk.Label(self.window, bg=BG, fg=MUTED, font=('TkDefaultFont', 9))
        self.label.pack(anchor='w', padx=8, pady=(7, 2))
        self.screen = tk.Label(self.window, bg='#070f13', borderwidth=0)
        self.screen.pack(padx=8, pady=(0, 8))
        settings = load_preferences(self.runtime)
        x, y = settings.get('x'), settings.get('y')
        position = position_from_geometry(settings.get('position'))
        if position:
            self.window.geometry(position)
        elif type(x) is int and type(y) is int:
            # Migrate older absolute-coordinate preferences. Tk negative geometry
            # is relative to the far screen edge, not an absolute coordinate.
            self.window.update_idletasks()
            width, height = self.window.winfo_reqwidth(), self.window.winfo_reqheight()
            left = f'+{x}' if x >= 0 else f'-{self.window.winfo_screenwidth() - width - x}'
            top = f'+{y}' if y >= 0 else f'-{self.window.winfo_screenheight() - height - y}'
            self.window.geometry(left + top)
        self.window.bind('<Configure>', self.moved, add='+')
        self.update({}, None)
        if not demo:
            self.window.update_idletasks()
            self.persist(True)

    def moved(self, event):
        if event.widget is not self.window or self.demo:
            return
        if self.save_timer:
            self.window.after_cancel(self.save_timer)
        self.save_timer = self.window.after(500, self.save_position)

    def save_position(self):
        self.save_timer = None
        self.persist(True)

    def persist(self, enabled):
        try:
            save_preferences(self.runtime, enabled, self.window.winfo_x(), self.window.winfo_y(),
                             self.window.geometry())
        except OSError:
            # The widget stays usable even if its position cannot be remembered.
            pass

    def update(self, status, pixels):
        if pixels is not None and pixels != self.frame:
            self.frame = pixels
            self.image = tk.PhotoImage(data=base64.b64encode(png_bytes(pixels, 2)), master=self.window)
            self.screen.configure(image=self.image)
        elif self.image is None:
            self.image = tk.PhotoImage(data=base64.b64encode(png_bytes(bytes(1024), 2)), master=self.window)
            self.screen.configure(image=self.image)
        self.label.configure(text='DEMO · SIMULATED' if self.demo else widget_status(status), fg=TEXT)

    def close(self):
        if self.save_timer:
            self.window.after_cancel(self.save_timer)
            self.save_timer = None
        if not self.demo:
            self.persist(False)
        self.window.destroy()
        self.on_close()
