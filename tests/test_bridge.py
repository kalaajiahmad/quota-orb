import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import zlib

from bridge.codex import CodexClient
from bridge.model import SourceError, countdown, freshness, normalize
from bridge.render import Canvas, png_bytes, render
from bridge.usb import Display, packet
from bridge.__main__ import UsageWorker


def fixture(used=28, **kwargs):
    window = {"usedPercent": used, "windowDurationMins": 10080, "resetsAt": 2000}
    window.update(kwargs)
    return {"rateLimits": {"limitId": "codex", "primary": window, "secondary": None}}


class ModelTests(unittest.TestCase):
    def test_synthetic_weekly_shape(self):
        s = normalize(fixture(), now=1000)
        self.assertEqual(len(s.windows), 1)
        self.assertEqual(s.windows[0].label, "WEEKLY")
        self.assertEqual(s.windows[0].remaining, 72)

    def test_multi_bucket_is_authoritative_and_codex_first(self):
        data = fixture(99)
        other = fixture(30)["rateLimits"]
        other["secondary"] = {"usedPercent": 20, "windowDurationMins": 300, "resetsAt": 1900}
        data["rateLimitsByLimitId"] = {"other": other, "codex": fixture(8)["rateLimits"]}
        windows = normalize(data).windows
        self.assertEqual([w.used for w in windows], [8, 30, 20])
        self.assertEqual(windows[-1].label, "5 HOUR")
        data["rateLimitsByLimitId"] = {}
        with self.assertRaises(SourceError):
            normalize(data)

    def test_null_is_not_zero_and_no_invented_window(self):
        for value in (None, True, "5", -1, 101, float("nan")):
            with self.subTest(value=value), self.assertRaises(SourceError):
                normalize(fixture(value))
        with self.assertRaises(SourceError):
            normalize({"rateLimits": None})

    def test_missing_reset_and_duration(self):
        w = normalize(fixture(5, windowDurationMins=None, resetsAt=None)).windows[0]
        self.assertEqual(w.label, "PRIMARY")
        self.assertEqual(countdown(w.resets_at, 1000), "RESET UNKNOWN")

    def test_freshness_and_failed_refresh_keep_last_value(self):
        s = normalize(fixture(), now=1000)
        self.assertEqual(freshness(s, 1149), "LIVE")
        self.assertEqual(freshness(s, 1151), "STALE")
        self.assertEqual(freshness(s, 1001, error=True), "STALE")
        self.assertEqual(freshness(None, 1001), "NO DATA")
        self.assertEqual(s.windows[0].remaining, 72)

    def test_blocked_and_past_reset_do_not_replenish(self):
        data = fixture(90)
        data["ordinaryUsageAllowed"] = False
        s = normalize(data, now=1000)
        self.assertEqual(freshness(s, 1001), "BLOCKED")
        self.assertEqual(countdown(2000, 2001), "AWAITING RESET")
        self.assertEqual(s.windows[0].remaining, 10)

    def test_reset_rounding(self):
        self.assertEqual(countdown(1001, 1000), "RESET 0H 01M")
        self.assertEqual(countdown(1000 + 86400, 1000), "RESET 1D 00H")


class RenderingTests(unittest.TestCase):
    def test_page_layout_matches_ssd1306(self):
        c = Canvas()
        for x, y in [(0, 0), (127, 7), (0, 8), (127, 63)]:
            c.pixel(x, y)
        self.assertEqual(c.data[0], 1)
        self.assertEqual(c.data[127], 128)
        self.assertEqual(c.data[128], 1)
        self.assertEqual(c.data[1023], 128)

    def test_all_states_and_extreme_percentages_render(self):
        for used in (0, 0.1, 4, 99, 100):
            for error in (False, True):
                self.assertEqual(len(render(normalize(fixture(used), now=1000), 1001, error=error)), 1024)
        self.assertEqual(len(render(None, 1000)), 1024)

    def test_png_has_exact_dimensions_and_valid_chunks(self):
        png = png_bytes(bytes(1024), scale=4)
        self.assertEqual(png[:8], b"\x89PNG\r\n\x1a\n")
        self.assertEqual(struct.unpack(">II", png[16:24]), (512, 256))
        offset = 8
        while offset < len(png):
            length = struct.unpack(">I", png[offset:offset + 4])[0]
            chunk = png[offset + 4:offset + 8 + length]
            checksum = struct.unpack(">I", png[offset + 8 + length:offset + 12 + length])[0]
            self.assertEqual(zlib.crc32(chunk), checksum)
            offset += 12 + length


class UsbTests(unittest.TestCase):
    def test_packet_and_crc(self):
        pixels = bytes(range(256)) * 4
        data, crc = packet(pixels, 12)
        fields = data.decode().strip().split(" ")
        self.assertEqual(fields[:3], ["F", "12", f"{zlib.crc32(pixels):08x}"])
        self.assertEqual(bytes.fromhex(fields[3]), pixels)
        with self.assertRaises(ValueError):
            packet(b"bad", 1)

    def test_rejects_mismatched_ack_and_nack(self):
        from unittest.mock import Mock
        d = Display("COM99")
        d.serial = Mock()
        for response in ({"type": "ack", "seq": 1, "crc": 0}, {"type": "nack", "seq": 1}):
            d.sequence = 0
            with patch.object(d, "read", return_value=response), self.assertRaises(OSError):
                d.send(bytes(1024))


class ClientTests(unittest.TestCase):
    def test_only_read_methods_are_allowed(self):
        c = CodexClient()
        for method in ("turn/start", "account/logout", "account/rateLimitResetCredit/consume"):
            with self.assertRaises(SourceError):
                c.call(method)

    def test_subprocess_response_and_clean_shutdown(self):
        # Exercise real stdio framing/reader thread with a deterministic subprocess.
        program = ('import sys,json\n'
                   'for line in sys.stdin:\n'
                   ' m=json.loads(line)\n'
                   ' if "id" in m: print(json.dumps({"id":m["id"],"result":{"ok":True}}),flush=True)\n')
        process = subprocess.Popen([sys.executable, "-u", "-c", program], stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE, text=True, encoding="utf-8")
        c = CodexClient(timeout=2)
        with patch("bridge.codex.find_codex", return_value=sys.executable), patch("bridge.codex.subprocess.Popen", return_value=process):
            with c:
                self.assertEqual(c.read_limits(), {"ok": True})
        self.assertIsNotNone(process.poll())


class WorkerTests(unittest.TestCase):
    def test_failed_refresh_retains_last_good_then_recovers(self):
        states = []

        class ControlledStop:
            stopped = False

            def is_set(self):
                return self.stopped

            def wait(self, timeout):
                states.append(worker.get())
                if len(states) == 3:
                    self.stopped = True

        from unittest.mock import Mock
        stop = ControlledStop()
        worker = UsageWorker(stop)
        fake = Mock()
        fake.read_limits.side_effect = [fixture(31), SourceError("network unavailable"), fixture(57)]
        with patch("bridge.__main__.CodexClient", return_value=fake), self.assertLogs(level="INFO"):
            worker.run()
        self.assertEqual([s[0].windows[0].used for s in states], [31, 31, 57])
        self.assertIsNone(states[0][1])
        self.assertEqual(states[1][1], "network unavailable")
        self.assertIsNone(states[2][1])
        self.assertEqual(fake.close.call_count, 2)

    def test_early_exit_is_reported(self):
        c = CodexClient(timeout=1)
        process = subprocess.Popen([sys.executable, "-c", "pass"], stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE, text=True, encoding="utf-8")
        with patch("bridge.codex.find_codex", return_value=sys.executable), patch("bridge.codex.subprocess.Popen", return_value=process):
            with self.assertRaises(SourceError):
                with c:
                    pass
        self.assertIsNotNone(process.poll())


if __name__ == "__main__":
    unittest.main()
