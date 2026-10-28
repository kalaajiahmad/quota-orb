"""The single user-facing entry point for setup and the desktop monitor."""
from pathlib import Path
import tkinter as tk
from tkinter import messagebox

from .lifecycle import ROOT, start_monitor
from .providers import preferences


def main():
    if not (ROOT / '.runtime/preferences.json').exists():
        from .onboarding import main as setup
        return setup()
    saved = preferences()
    try:
        start_monitor(saved['provider'], saved['port'])
    except Exception as error:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror('Quota Orb', str(error), parent=root)
        root.destroy()
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
