import os
import ctypes as C
from ctypes import wintypes as W
from pathlib import Path
import queue
import tempfile
import unittest
import uuid
from unittest.mock import patch, Mock, call

from bridge.__main__ import UsageSession, main
from bridge.tray import (presentation, status_text, Tray, track_tray_menu,
                         shell_window_rect, MonitorInfo, PopupParameters)


class Worker:
    def __init__(self, stop):
        self.stop = stop
        self.alive = False
        self.joined = False

    def start(self):
        self.alive = True

    def is_alive(self):
        return self.alive

    def get(self):
        return None, None

    def join(self, timeout):
        self.joined = True
        self.alive = False


class SessionTests(unittest.TestCase):
    def test_pause_and_quick_resume_never_overlap_clients(self):
        workers = []
        def create(stop):
            worker = Worker(stop)
            workers.append(worker)
            return worker
        session = UsageSession(create)
        session.tick()
        session.toggle()
        self.assertTrue(workers[0].stop.is_set())
        self.assertTrue(session.transitioning)
        session.tick()
        self.assertEqual(len(workers), 1)
        session.toggle()
        session.tick()
        self.assertEqual(len(workers), 1, 'Resume must wait for previous client cleanup')
        workers[0].alive = False
        session.tick()
        self.assertEqual(len(workers), 2)
        self.assertFalse(workers[1].stop.is_set())
        session.close()
        self.assertTrue(workers[1].stop.is_set())
        self.assertTrue(workers[1].joined)

    def test_close_before_start_is_safe(self):
        create = Mock()
        session = UsageSession(create)
        session.close()
        create.assert_not_called()


class TrayTests(unittest.TestCase):
    def test_shell_panel_is_excluded_on_negative_coordinate_monitor(self):
        user = Mock()
        user.WindowFromPoint.return_value = 11
        user.GetAncestor.return_value = 12
        user.GetShellWindow.return_value = 13
        user.MonitorFromPoint.return_value = 14
        def pid(hwnd, out):
            C.cast(out, C.POINTER(W.DWORD)).contents.value = 42
        def rectangle(hwnd, out):
            rect = C.cast(out, C.POINTER(W.RECT)).contents
            rect.left, rect.top, rect.right, rect.bottom = -400, 800, -100, 1000
            return True
        def monitor(handle, out):
            info = C.cast(out, C.POINTER(MonitorInfo)).contents
            info.rcMonitor = W.RECT(-1920, 0, 0, 1080)
            return True
        user.GetWindowThreadProcessId.side_effect = pid
        user.GetWindowRect.side_effect = rectangle
        user.GetMonitorInfoW.side_effect = monitor
        rect = shell_window_rect(user, W.POINT(-250, 900))
        self.assertEqual((rect.left, rect.top, rect.right, rect.bottom), (-400, 800, -100, 1000))
        self.assertIsNone(shell_window_rect(user, W.POINT(-50, 900)))
        def wrong_process(hwnd, out):
            C.cast(out, C.POINTER(W.DWORD)).contents.value = hwnd
        user.GetWindowThreadProcessId.side_effect = wrong_process
        self.assertIsNone(shell_window_rect(user, W.POINT(-250, 900)))

    def test_menu_passes_the_excluded_panel_to_windows_and_cleans_up(self):
        user = Mock()
        captured = []
        def track(menu, flags, x, y, owner, params):
            p = C.cast(params, C.POINTER(PopupParameters)).contents
            captured.append((flags, x, y, p.cbSize, p.rcExclude.left, p.rcExclude.top,
                             p.rcExclude.right, p.rcExclude.bottom))
            return 4
        user.TrackPopupMenuEx.side_effect = track
        point = W.POINT(-250, 900)
        self.assertEqual(track_tray_menu(user, 123, 456, point, W.RECT(-400, 800, -100, 1000)), 4)
        self.assertEqual(captured, [(0x142, -250, 900, C.sizeof(PopupParameters), -400, 800, -100, 1000)])
        self.assertEqual(user.mock_calls[0], call.SetWindowPos(123, -1, 0, 0, 0, 0, 0x53))
        self.assertEqual(user.mock_calls[-2:], [call.PostMessageW(123, 0, 0, 0),
                         call.SetWindowPos(123, -2, 0, 0, 0, 0, 0x93)])

    def test_menu_always_hides_the_owner_when_tracking_fails(self):
        user = Mock()
        user.TrackPopupMenuEx.side_effect = RuntimeError('menu failed')
        with self.assertRaises(RuntimeError):
            track_tray_menu(user, 123, 456, W.POINT(0, 0))
        self.assertEqual(user.mock_calls[-1], call.SetWindowPos(123, -2, 0, 0, 0, 0, 0x93))

    def test_icons_distinguish_live_stale_missing_and_paused(self):
        status = {'provider': 'codex', 'source': 'LIVE', 'usb_connected': True}
        self.assertEqual(presentation(status)[0], 'live')
        self.assertEqual(presentation(dict(status, source='STALE'))[0], 'warning')
        self.assertEqual(presentation(dict(status, source='NO DATA'))[0], 'error')
        self.assertEqual(presentation(dict(status, source='BLOCKED'))[0], 'error')
        self.assertEqual(presentation(dict(status, usb_connected=False))[0], 'warning')
        self.assertIn('Paused', presentation(dict(status, paused=True))[1])
        self.assertIn('Pausing', presentation(dict(status, paused=True, transitioning=True))[1])
        self.assertEqual(presentation(dict(status, stopping=True))[0], 'idle')

    def test_status_does_not_expose_snapshot_or_errors(self):
        text = status_text({'provider':'claude', 'source':'LIVE', 'usb_connected':True,
            'snapshot':'PRIVATE_MARKER', 'source_error':'PRIVATE_MARKER',
            'port':'PRIVATE_MARKER', 'frames_acknowledged':12})
        self.assertNotIn('PRIVATE_MARKER', text)
        self.assertIn('Claude Code', text)
        self.assertIn('12', text)

    @unittest.skipUnless(os.name == 'nt', 'Windows notification-area implementation')
    def test_menu_commands_are_queued(self):
        commands = queue.Queue()
        tray = Tray(commands)
        for item, expected in [(1,'setup'), (3,'toggle'), (4,'quit'), (5,'display')]:
            tray.action(item)
            self.assertEqual(commands.get_nowait(), expected)

    @unittest.skipUnless(os.name == 'nt', 'Windows notification-area implementation')
    def test_unexpected_icon_thread_exit_requests_shutdown(self):
        commands = queue.Queue()
        tray = Tray(commands)
        with patch.object(tray, '_run'):
            with self.assertRaises(OSError):
                tray.start()
        self.assertTrue(tray.failed.is_set())
        self.assertEqual(commands.get_nowait(), 'quit')

    @unittest.skipUnless(os.name == 'nt', 'Windows notification-area implementation')
    def test_icon_failure_prevents_provider_and_usb_access(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime = Path(tmp)
            with patch('sys.argv', ['bridge','--quiet','--runtime',str(runtime)]), \
                 patch('bridge.tray.Tray') as tray, \
                 patch('bridge.__main__.UsageWorker') as worker, \
                 patch('bridge.__main__.MUTEX_NAME','Local\\QuotaOrbTest-'+uuid.uuid4().hex), \
                 patch('bridge.usb.Display') as display, \
                 patch('bridge.__main__.RotatingFileHandler', return_value=__import__('logging').NullHandler()), \
                 patch('bridge.__main__.logging.basicConfig'):
                tray.return_value.start.side_effect = OSError('Icon unavailable')
                with self.assertRaises(OSError):
                    main()
                worker.assert_not_called()
                display.return_value.connect.assert_not_called()
                tray.return_value.close.assert_called_once()
                self.assertFalse((runtime/'process.json').exists())

    @unittest.skipUnless(os.name == 'nt', 'Windows notification-area implementation')
    def test_bridge_pause_resume_and_quit_cleanup(self):
        records = []
        workers = []
        def create(event, *args):
            worker = Worker(event)
            # Model a completed client shutdown as soon as its cancellation is observed.
            worker.is_alive = lambda: not event.is_set()
            workers.append(worker)
            return worker
        with tempfile.TemporaryDirectory() as tmp:
            runtime = Path(tmp)
            with patch('sys.argv', ['bridge','--quiet','--runtime',str(runtime),
                                   '--output',str(runtime/'preview.png')]), \
                 patch('bridge.tray.Tray') as tray, \
                 patch('bridge.__main__.UsageWorker', side_effect=create), \
                 patch('bridge.__main__.MUTEX_NAME','Local\\QuotaOrbTest-'+uuid.uuid4().hex), \
                 patch('bridge.usb.Display') as display, \
                 patch('bridge.__main__.RotatingFileHandler', return_value=__import__('logging').NullHandler()), \
                 patch('bridge.__main__.logging.basicConfig'):
                device = display.return_value
                device.port, device.serial = 'COM99', None
                device.button_presses, device.last_ack = 0, None
                device.connect.side_effect = lambda: setattr(device,'serial',True)
                device.close.side_effect = lambda: setattr(device,'serial',None)
                def acknowledge(frame):
                    import zlib
                    device.last_ack = {'type':'ack','seq':len(records)+1,'crc':zlib.crc32(frame)}
                device.send.side_effect = acknowledge
                tray.return_value.failed.is_set.return_value = False
                tray.return_value.registered = True
                def update(status):
                    if status.get('stopping'):
                        return
                    records.append(dict(status))
                    tray.call_args.args[0].put('toggle' if len(records)<3 else 'quit')
                tray.return_value.update.side_effect = update
                self.assertEqual(main(), 0)
                self.assertEqual([r['paused'] for r in records], [False,True,False])
                self.assertEqual([r['frames_acknowledged'] for r in records], [1,1,2])
                from bridge.display import confirmed_pixels
                self.assertTrue(all(confirmed_pixels(r) is not None for r in records))
                self.assertEqual(len(workers), 2)
                self.assertTrue(all(w.stop.is_set() for w in workers))
                self.assertTrue(workers[-1].joined)
                tray.return_value.close.assert_called_once()
                self.assertFalse((runtime/'process.json').exists())


if __name__ == '__main__':
    unittest.main()
