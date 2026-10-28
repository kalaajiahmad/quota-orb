import argparse
from dataclasses import asdict
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import queue
import signal
import subprocess
import sys
import threading
import time

from .codex import CodexClient
from .model import SourceError, normalize, freshness
from .render import render, save_png
from .claude import ClaudeFileClient
from .layout import LayoutStore, render_layout
from .widgets import Context
from .files import atomic_write

MUTEX_NAME = 'Local\\QuotaOrbBridge'


def atomic_json(path, data):
    atomic_write(path,(json.dumps(data,indent=2)+'\n').encode('utf-8'))


class UsageWorker(threading.Thread):
    def __init__(self, stop, interval=60, codex=None, provider='codex', runtime=Path('.runtime')):
        super().__init__(daemon=True)
        self.stop_event, self.interval, self.codex = stop, interval, codex
        self.lock = threading.Lock()
        self.snapshot, self.error = None, None
        self.provider, self.runtime = provider, Path(runtime)

    def get(self):
        with self.lock:
            return self.snapshot, self.error

    def run(self):
        client = None
        try:
            while not self.stop_event.is_set():
                try:
                    if client is None:
                        client = (CodexClient(self.codex) if self.provider == 'codex'
                                  else ClaudeFileClient(self.runtime/'claude-usage.json'))
                        client.start()
                    if self.stop_event.is_set():
                        break
                    snapshot = normalize(client.read_limits(), now=getattr(client,'observed_at',None))
                    with self.lock:
                        self.snapshot, self.error = snapshot, None
                    logging.info("Account refreshed: %s", "; ".join(f"{w.bucket}/{w.label}: {w.used:g}% used" for w in snapshot.windows))
                    wait = self.interval
                except (SourceError, OSError, ValueError) as exc:
                    with self.lock:
                        self.error = str(exc)
                    logging.warning("Usage source unavailable: %s", exc)
                    if client:
                        client.close()
                        client = None
                    wait = min(self.interval, 15)
                self.stop_event.wait(wait)
        finally:
            if client:
                client.close()


class UsageSession:
    """Pause cancels polling; resume waits for the old client to close first."""
    def __init__(self, factory):
        self.factory = factory
        self.worker = None
        self.stop_event = None
        self.paused = False

    def tick(self):
        if not self.paused and (self.worker is None or
                self.stop_event.is_set() and not self.worker.is_alive()):
            self.stop_event = threading.Event()
            self.worker = self.factory(self.stop_event)
            self.worker.start()

    def toggle(self):
        self.paused = not self.paused
        if self.paused and self.stop_event:
            self.stop_event.set()

    def get(self):
        return self.worker.get() if self.worker else (None, None)

    @property
    def transitioning(self):
        return bool(self.stop_event and self.stop_event.is_set() and self.worker.is_alive())

    def close(self):
        if self.stop_event:
            self.stop_event.set()
            self.worker.join(timeout=40)


def main():
    parser = argparse.ArgumentParser(description="Quota Orb — live account limits on a Heltec USB OLED")
    parser.add_argument("--port", help="COM port (auto-detect one CP210x adapter by default)")
    parser.add_argument("--codex", help="Path to a Codex executable")
    parser.add_argument("--provider", choices=['codex','claude'], default='codex')
    parser.add_argument("--poll", type=int, default=60, help="Account poll interval, 30 seconds minimum")
    parser.add_argument("--duration", type=int, default=0, help="Stop after N seconds; 0 runs continuously")
    parser.add_argument("--preview-only", action="store_true", help="Read live data and render without USB")
    parser.add_argument("--demo", action="store_true", help="Render labeled fixture preview; never contact USB/Codex")
    parser.add_argument("--once", action="store_true", help="Read one live snapshot and exit; no USB")
    parser.add_argument("--page", type=int, default=0, help="Initial quota window index")
    parser.add_argument("--quiet", action="store_true", help="Write rotating log only, for background operation")
    parser.add_argument("--output", type=Path, default=Path("artifacts/live.png"))
    parser.add_argument("--runtime", type=Path, default=Path(".runtime"))
    args = parser.parse_args()
    if args.poll < 30:
        parser.error("--poll must be at least 30 seconds")
    args.runtime.mkdir(parents=True, exist_ok=True)
    handlers = [RotatingFileHandler(args.runtime / "bridge.log", maxBytes=524288, backupCount=3, encoding="utf-8")]
    if not args.quiet:
        handlers.append(logging.StreamHandler())
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", handlers=handlers)
    if args.demo:
        snapshot = normalize({"rateLimits": {"limitId": "codex", "primary": {
            "usedPercent": 28, "windowDurationMins": 10080, "resetsAt": 2_000_000_000 + 311040}}}, now=2_000_000_000)
        save_png(args.output, render(snapshot, 2_000_000_000, tick=0))
        print(f"DEMO fixture saved to {args.output}")
        return 0
    if args.once:
        if args.provider != 'codex':
            parser.error('--once currently supports Codex; Claude uses local status-line events')
        with CodexClient(args.codex) as client:
            snapshot = normalize(client.read_limits())
        save_png(args.output, render(snapshot, time.time(), args.page))
        print(json.dumps(asdict(snapshot), indent=2))
        return 0

    # A local kernel mutex prevents two bridges fighting for one USB device.
    mutex = None
    if os.name == "nt":
        import ctypes
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
        kernel.CreateMutexW.restype = ctypes.c_void_p
        mutex = kernel.CreateMutexW(None, False, MUTEX_NAME)
        if not mutex:
            raise OSError("Could not create bridge process mutex")
        if ctypes.get_last_error() == 183:
            kernel.CloseHandle.argtypes = [ctypes.c_void_p]
            kernel.CloseHandle(mutex)
            logging.error("A Quota Orb bridge is already running")
            return 1

    lock_file = None
    if os.name != "nt":
        import fcntl
        lock_file = (args.runtime / "bridge.lock").open("a+")
        try:
            fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            lock_file.close()
            logging.error("A Quota Orb bridge is already running")
            return 1

    stop = threading.Event()
    def request_stop(*_):
        stop.set()
    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)
    stop_file = args.runtime / "stop"
    stop_file.unlink(missing_ok=True)
    atomic_json(args.runtime / "process.json", {"pid": os.getpid(), "started_at": time.time()})
    commands = queue.Queue()
    tray = None
    session = UsageSession(lambda event: UsageWorker(event,
        args.poll if args.provider == 'codex' else 2, args.codex, args.provider, args.runtime))
    from .usb import Display
    display = Display(args.port)
    page, next_connect, acks, first, last_status = args.page, 0, 0, time.monotonic(), None
    setup_window = None
    preview_window = None
    confirmed_frame = None
    layouts = LayoutStore(args.runtime/'layout.json')
    try:
        if os.name == 'nt':
            from .tray import Tray
            tray = Tray(commands, args.provider)
            tray.start()  # No account/USB access before a visible icon is registered.
        while not stop.is_set():
            tick_start = time.monotonic()
            if stop_file.exists() or args.duration and tick_start - first >= args.duration:
                break
            open_display = args.runtime / 'open-display'
            try:
                open_display.unlink()
            except FileNotFoundError:
                pass
            except OSError:
                logging.warning('Desktop request is busy; retrying next frame')
            else:
                commands.put('display')
            while not commands.empty():
                command = commands.get_nowait()
                if command == 'quit':
                    stop.set()
                elif command == 'toggle':
                    session.toggle()
                    if session.paused:
                        display.close()
                elif command == 'setup' and (setup_window is None or setup_window.poll() is not None):
                    program = Path(sys.executable).with_name('pythonw.exe') if os.name == 'nt' else sys.executable
                    setup_window = subprocess.Popen([str(program), '-m', 'bridge.onboarding'],
                        cwd=Path(__file__).resolve().parents[1], creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
                elif command == 'display' and (preview_window is None or preview_window.poll() is not None):
                    program = Path(sys.executable).with_name('pythonw.exe') if os.name == 'nt' else sys.executable
                    preview_window = subprocess.Popen([str(program), '-m', 'bridge.display',
                        '--runtime', str(args.runtime.resolve())],
                        cwd=Path(__file__).resolve().parents[1], creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
                elif command == 'display':
                    (args.runtime/'show-display').touch()
            if os.name != 'nt' and preview_window is not None and preview_window.poll() is not None:
                logging.info('Desktop window closed; stopping monitor')
                stop.set()
            if tray and tray.failed.is_set():
                raise OSError('Notification icon failed; monitoring has stopped')
            if stop.is_set():
                break
            session.tick()
            snapshot, error = session.get()
            now = time.time()
            if display.button_presses:
                page += display.button_presses
                display.button_presses = 0
            frame = render(snapshot, now, page, error is not None, max(150, args.poll * 2.5), provider=args.provider)
            layout = layouts.read()
            layout_mode = layout['mode']
            if layout_mode == 'custom':
                try:
                    frame = render_layout(layout, Context(snapshot,now,page,error is not None,
                        max(150,args.poll*2.5),args.provider))
                except Exception:
                    layout_mode = 'classic'
                    layouts.error = 'Widget rendering failed; using the classic display'
                    logging.warning(layouts.error)
            if not args.preview_only and not session.paused and not session.transitioning:
                try:
                    if display.serial is None and tick_start >= next_connect:
                        hello = display.connect()
                        logging.info("OLED connected on %s: %s", display.port, hello)
                    if display.serial:
                        display.send(frame)
                        acks += 1
                        confirmed_frame = {'pixels': frame.hex(), 'ack': display.last_ack,
                            'acknowledged_at': time.time()}
                except (OSError, ValueError) as exc:
                    logging.warning("USB unavailable: %s", exc)
                    display.close()
                    next_connect = time.monotonic() + 3
            save_png(args.output, frame)
            status = {"pid": os.getpid(), "running": True, "updated_at": now,
                "desktop_request_version": 1,
                "provider": args.provider,
                "source": ('PAUSED' if session.paused else 'RESUMING' if session.transitioning else
                    freshness(snapshot, now, error is not None, max(150, args.poll * 2.5))),
                "paused": session.paused, "transitioning": session.transitioning,
                "tray_registered": bool(tray and tray.registered),
                "last_fetch": snapshot.fetched_at if snapshot else None,
                "source_error": error, "port": display.port,
                "usb_connected": display.serial is not None, "frames_acknowledged": acks,
                "last_ack": display.last_ack, "snapshot": asdict(snapshot) if snapshot else None}
            status['display_frame'] = confirmed_frame
            status['rendered_frame'] = frame.hex()
            status.update(layout_mode=layout_mode, layout_error=layouts.error)
            atomic_json(args.runtime / "status.json", status)
            if tray:
                tray.update(status)
            state = (status["source"], status["usb_connected"])
            if state != last_status:
                logging.info("Display state: %s; USB %s", state[0], "connected" if state[1] else "disconnected")
                last_status = state
            stop.wait(max(0, 1 - (time.monotonic() - tick_start)))
    finally:
        stop.set()
        if tray:
            tray.update({"stopping": True})
        display.close()
        session.close()
        if tray:
            tray.close()
        status_path = args.runtime / "status.json"
        if status_path.exists():
            stopped = json.loads(status_path.read_text(encoding="utf-8"))
            stopped.update(running=False, usb_connected=False, tray_registered=False, stopped_at=time.time())
            atomic_json(status_path, stopped)
        (args.runtime / "process.json").unlink(missing_ok=True)
        stop_file.unlink(missing_ok=True)
        try:
            (args.runtime / 'open-display').unlink(missing_ok=True)
        except OSError:
            logging.warning('Could not clear the desktop request during shutdown')
        if mutex:
            kernel.CloseHandle.argtypes = [ctypes.c_void_p]
            kernel.CloseHandle(mutex)
        if lock_file:
            lock_file.close()
        logging.info("Bridge stopped; firmware will show USB OFFLINE within six seconds")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        logging.exception('Monitor failed')
        if os.name == 'nt' and sys.stderr is None:
            import ctypes
            ctypes.windll.user32.MessageBoxW(None,
                'Quota Orb could not run and has stopped. Open setup or inspect the local bridge log.',
                'Quota Orb | Monitor stopped', 0x10)
        raise
