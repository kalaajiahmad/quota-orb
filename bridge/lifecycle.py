"""Start and stop the local monitor using its heartbeat and request files."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / '.runtime'


def _process_alive(pid):
    if os.name == 'nt':
        import ctypes
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
        kernel.OpenProcess.restype = ctypes.c_void_p
        kernel.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        kernel.WaitForSingleObject.restype = ctypes.c_uint32
        kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        handle = kernel.OpenProcess(0x00100000, False, pid)  # SYNCHRONIZE
        if not handle:
            return False
        try:
            return kernel.WaitForSingleObject(handle, 0) == 0x102  # WAIT_TIMEOUT
        finally:
            kernel.CloseHandle(handle)
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _healthy_status(runtime=RUNTIME):
    try:
        status = json.loads((runtime / 'status.json').read_text(encoding='utf-8'))
        age = time.time() - status['updated_at']
        pid = status['pid']
        if not status['running'] or not -5 <= age <= 6 or type(pid) is not int or pid <= 0:
            return None
        return status if _process_alive(pid) else None
    except (OSError, ValueError, KeyError, TypeError):
        return None


def start_monitor(provider='codex', port=None, show=True):
    if provider not in ('codex', 'claude'):
        raise ValueError('Unsupported provider')
    if os.name == 'nt':
        command = ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass',
                   '-File', str(ROOT / 'scripts/Start.ps1'), '-Provider', provider]
        if port:
            command.extend(['-Port', port])
        if not port:
            command.append('-PreviewOnly')
        if show:
            command.append('-ShowWindow')
        subprocess.run(command, cwd=ROOT, check=True, creationflags=subprocess.CREATE_NO_WINDOW)
        return
    RUNTIME.mkdir(parents=True, exist_ok=True)
    status = _healthy_status()
    process = None
    if status is None:
        command = [sys.executable, '-m', 'bridge', '--quiet', '--provider', provider]
        if port:
            command.extend(['--port', port])
        else:
            command.append('--preview-only')
        with (RUNTIME / 'stderr.log').open('a', encoding='utf-8') as errors:
            process = subprocess.Popen(command, cwd=ROOT, stdin=subprocess.DEVNULL,
                                       stdout=subprocess.DEVNULL, stderr=errors, start_new_session=True)
        deadline = time.monotonic() + 25
        while time.monotonic() < deadline:
            status = _healthy_status()
            if status:
                break
            if process.poll() is not None:
                raise RuntimeError('Monitor exited. Inspect .runtime/bridge.log and stderr.log.')
            time.sleep(.2)
        if not status:
            (RUNTIME / 'stop').touch()
            raise RuntimeError('Monitor did not confirm startup; shutdown requested.')
    if show:
        if status.get('desktop_request_version') != 1:
            raise RuntimeError('The running monitor needs to be restarted before opening the display.')
        (RUNTIME / 'open-display').touch()


def stop_monitor():
    if not _healthy_status():
        return
    (RUNTIME / 'stop').touch()
    deadline = time.monotonic() + 48
    while time.monotonic() < deadline:
        if not (RUNTIME / 'process.json').exists():
            return
        time.sleep(.2)
    raise RuntimeError('Monitor did not acknowledge shutdown; inspect .runtime/bridge.log.')
