import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from bridge import lifecycle


class LifecycleTests(unittest.TestCase):
    def test_heartbeat_requires_live_process_and_recent_status(self):
        with tempfile.TemporaryDirectory() as folder:
            runtime = Path(folder)
            status = {'running': True, 'pid': 123, 'updated_at': time.time()}
            (runtime / 'status.json').write_text(json.dumps(status), encoding='utf-8')
            with patch('bridge.lifecycle._process_alive', return_value=True) as alive:
                self.assertEqual(lifecycle._healthy_status(runtime), status)
                alive.assert_called_once_with(123)
                status['updated_at'] -= 30
                (runtime / 'status.json').write_text(json.dumps(status), encoding='utf-8')
                self.assertIsNone(lifecycle._healthy_status(runtime))

    def test_existing_monitor_receives_display_request(self):
        with tempfile.TemporaryDirectory() as folder:
            runtime = Path(folder)
            with patch.object(lifecycle, 'RUNTIME', runtime), \
                 patch.object(lifecycle.os, 'name', 'posix'), \
                 patch.object(lifecycle, '_healthy_status', return_value={'desktop_request_version': 1}), \
                 patch.object(lifecycle.subprocess, 'Popen') as popen:
                lifecycle.start_monitor()
                self.assertTrue((runtime / 'open-display').exists())
                popen.assert_not_called()

    @unittest.skipUnless(os.name == 'nt', 'Windows launcher')
    def test_windows_desktop_only_requests_preview_mode(self):
        with patch.object(lifecycle.os, 'name', 'nt'), \
             patch.object(lifecycle.subprocess, 'CREATE_NO_WINDOW', 0, create=True), \
             patch.object(lifecycle.subprocess, 'run') as run:
            lifecycle.start_monitor('codex')
            command = run.call_args.args[0]
            self.assertIn('-PreviewOnly', command)
            self.assertIn('-ShowWindow', command)


if __name__ == '__main__':
    unittest.main()
