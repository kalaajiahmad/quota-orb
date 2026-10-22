"""Minimal read-only client for the documented Codex app-server protocol."""
import json
import os
from pathlib import Path
import queue
import shutil
import subprocess
import threading
import time

from .model import SourceError


def find_codex(explicit=None):
    if explicit:
        path = Path(explicit).expanduser().resolve()
        if path.is_file():
            return str(path)
        raise SourceError("Configured Codex executable does not exist")
    path = shutil.which("codex")
    if path:
        return path
    base = Path(os.environ.get("LOCALAPPDATA", "")) / "OpenAI" / "Codex" / "bin"
    candidates = list(base.glob("*/codex.exe"))
    if candidates:
        return str(max(candidates, key=lambda p: p.stat().st_mtime))
    raise SourceError("Codex CLI not found. Install Codex or pass --codex PATH")


class CodexClient:
    def __init__(self, executable=None, timeout=25):
        self.executable = executable
        self.timeout = timeout
        self.process = None
        self.messages = queue.Queue()
        self.request_id = 0

    def start(self):
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        # Let Codex own its existing login and token renewal. Never open auth.json.
        self.process = subprocess.Popen(
            [find_codex(self.executable), "app-server", "--listen", "stdio://"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, encoding="utf-8", creationflags=flags,
        )
        messages = self.messages
        process = self.process

        def reader():
            try:
                for line in process.stdout:
                    try:
                        message = json.loads(line)
                        if isinstance(message, dict):
                            messages.put(message)
                    except ValueError:
                        continue
            finally:
                messages.put({"_closed": True})

        threading.Thread(target=reader, daemon=True).start()
        self.call("initialize", {"clientInfo": {"name": "quota_orb", "title": "Quota Orb", "version": "1.0.0"}})
        self.send({"method": "initialized", "params": {}})
        return self

    def send(self, message):
        if self.process is None or self.process.poll() is not None:
            raise SourceError("Codex app-server exited")
        try:
            self.process.stdin.write(json.dumps(message) + "\n")
            self.process.stdin.flush()
        except (BrokenPipeError, OSError) as exc:
            raise SourceError("Codex app-server pipe closed") from exc

    def call(self, method, params=None):
        # Intentionally no inference, reset, login/logout, or messaging methods.
        if method not in {"initialize", "account/rateLimits/read"}:
            raise SourceError("Only initialization and account limit reads are permitted")
        self.request_id += 1
        message = {"id": self.request_id, "method": method}
        if params is not None:
            message["params"] = params
        self.send(message)
        deadline = time.monotonic() + self.timeout
        while True:
            try:
                response = self.messages.get(timeout=max(0, deadline - time.monotonic()))
            except queue.Empty as exc:
                raise SourceError("Codex request timed out; check the existing Codex login and network") from exc
            if response.get("_closed"):
                raise SourceError("Codex app-server exited before replying")
            if response.get("id") != self.request_id:
                # Unrelated notifications do not prove a successful account refresh.
                continue
            if "error" in response:
                code = response["error"].get("code", "unknown")
                raise SourceError(f"Codex rejected the account request (RPC {code}); check ChatGPT sign-in")
            result = response.get("result")
            if not isinstance(result, dict):
                raise SourceError("Malformed Codex response")
            return result

    def read_limits(self):
        return self.call("account/rateLimits/read")

    def close(self):
        process, self.process = self.process, None
        if process is None:
            return
        if process.stdin:
            try:
                process.stdin.close()
            except OSError:
                pass
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=3)
        for stream in (process.stdout, process.stderr):
            if stream:
                stream.close()

    def __enter__(self):
        try:
            return self.start()
        except BaseException:
            self.close()
            raise

    def __exit__(self, *args):
        self.close()
