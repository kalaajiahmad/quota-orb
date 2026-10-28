import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
from unittest.mock import Mock

from bridge.claude import sanitized_event, save_event, ClaudeFileClient, configure_statusline, statusline_command
from bridge.model import normalize, freshness, SourceError
from bridge.providers import login_command, preferences, save_preferences, launch_login, valid_port

class ClaudeSecurityTests(unittest.TestCase):
    def event(self):
        return {'session_id':'PRIVATE_MARKER','transcript_path':'PRIVATE_MARKER',
                'workspace':{'current_dir':'PRIVATE_MARKER'},'credential':'PRIVATE_MARKER',
                'rate_limits':{'five_hour':{'used_percentage':37.5,'resets_at':2_000_000_000,
                                            'token':'PRIVATE_MARKER'},
                               'seven_day':{'used_percentage':63,'resets_at':2_000_300_000},
                               'spend_limit':{'used_usd':999}}}

    def test_event_is_strict_numeric_whitelist(self):
        event = sanitized_event(self.event(),now=1000)
        self.assertNotIn('PRIVATE_MARKER',json.dumps(event))
        self.assertNotIn('used_usd',json.dumps(event))
        self.assertEqual(set(event),{'received_at','rateLimits'})
        self.assertEqual(set(event['rateLimits']),{'limitId','primary','secondary'})
        self.assertEqual(normalize(event).windows[0].used,37.5)

    def test_absent_or_invalid_quota_never_becomes_zero(self):
        for payload in ({},{'rate_limits':None},{'rate_limits':{'five_hour':{'used_percentage':True}}},
                        {'rate_limits':{'seven_day':{'used_percentage':101}}}):
            self.assertIsNone(sanitized_event(payload)['rateLimits'])

    def test_cached_read_keeps_event_age(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'usage.json'
            stamp = time.time()-180
            save_event(self.event(),path,now=stamp)
            client = ClaudeFileClient(path)
            one = normalize(client.read_limits(),now=client.observed_at)
            two = normalize(client.read_limits(),now=client.observed_at)
            self.assertEqual(one.fetched_at,two.fetched_at)
            self.assertEqual(freshness(two,time.time()),'STALE')
            self.assertNotIn('PRIVATE_MARKER',path.read_text())

    def test_missing_bad_and_future_cache_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'usage.json'
            with self.assertRaises(SourceError):
                ClaudeFileClient(path).read_limits()
            for record in ('bad','[]',json.dumps(sanitized_event(self.event(),now=time.time()+100))):
                path.write_text(record)
                with self.assertRaises(SourceError):
                    ClaudeFileClient(path).read_limits()

    def test_install_remove_preserves_other_settings(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'settings.json'
            initial = {'env':{'UNRELATED':'PRESERVE'},'permissions':{'allow':['safe']}}
            path.write_text(json.dumps(initial))
            configure_statusline(path)
            configure_statusline(path)
            data = json.loads(path.read_text())
            self.assertEqual(data['env'],initial['env'])
            self.assertEqual(data['statusLine']['command'],statusline_command())
            configure_statusline(path,remove=True)
            self.assertEqual(json.loads(path.read_text()),initial)

    def test_existing_custom_or_invalid_settings_untouched(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'settings.json'
            for data in ('bad','[]',json.dumps({'statusLine':{'type':'command','command':'existing'}})):
                path.write_text(data)
                with self.assertRaises(SourceError):
                    configure_statusline(path)
                self.assertEqual(path.read_text(),data)

    def test_remove_refuses_changed_statusline(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'settings.json'
            configure_statusline(path)
            path.write_text('{"statusLine":{"type":"command","command":"other"}}')
            with self.assertRaises(SourceError):
                configure_statusline(path,remove=True)
            self.assertEqual(json.loads(path.read_text())['statusLine']['command'],'other')

    def test_posix_statusline_quotes_paths(self):
        import shlex
        with patch('bridge.claude.os.name', 'posix'), patch('bridge.claude.ROOT', '/tmp/orb path'), patch('bridge.claude.sys.executable', '/tmp/python path'):
            command = statusline_command()
        self.assertEqual(shlex.split(command), ['cd', '/tmp/orb path', '&&', 'exec', '/tmp/python path', '-m', 'bridge.claude'])

class ProviderFlowTests(unittest.TestCase):
    def test_login_uses_only_fixed_vendor_arguments(self):
        self.assertEqual(login_command('codex','provider.exe'),['provider.exe','login'])
        self.assertEqual(login_command('claude','provider.exe'),['provider.exe','auth','login'])
        with self.assertRaises(SourceError):
            login_command('gemini','provider.exe')

    def test_auth_output_is_not_captured_or_redirected(self):
        with patch('bridge.providers.subprocess.Popen') as run, patch('bridge.providers.sys.stdin') as stdin:
            stdin.isatty.return_value = True
            launch_login('codex','provider.exe')
            args,kwargs = run.call_args
            self.assertNotIn('shell',kwargs)
            self.assertNotIn('stdout',kwargs)
            self.assertNotIn('stderr',kwargs)
            self.assertEqual(args[0],['provider.exe','login'])

    def test_serial_port_validation_supports_native_device_paths(self):
        for port in ('COM1', 'COM42', 'com3'):
            self.assertTrue(valid_port(port, 'nt'))
        for port in ('COM0', 'COM1;evil', '/dev/ttyUSB0'):
            self.assertFalse(valid_port(port, 'nt'))
        for port in ('/dev/ttyUSB0', '/dev/cu.usbserial-1', '/dev/serial/by-id/usb-device'):
            self.assertTrue(valid_port(port, 'posix'))
        for port in ('COM1', '/dev/../tmp/file', '/dev//ttyUSB0', '/dev/tty\nUSB0'):
            self.assertFalse(valid_port(port, 'posix'))

    def test_preferences_store_only_nonsecret_selection(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'prefs.json'
            port = 'COM99' if os.name == 'nt' else '/dev/ttyUSB0'
            save_preferences('claude',port,path)
            self.assertEqual(preferences(path),{'provider':'claude','port':port})
            self.assertEqual(set(json.loads(path.read_text())),{'provider','port'})
            with self.assertRaises(SourceError):
                save_preferences('gemini',path=path)

    def test_preferences_reject_untrusted_provider_and_port(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'prefs.json'
            path.write_text('{"provider":"gemini","port":"bad"}')
            self.assertEqual(preferences(path),{'provider':'codex','port':None})
            path.write_text('{"provider":"claude","port":"bad"}')
            self.assertEqual(preferences(path),{'provider':'claude','port':None})


class MonitorStartTests(unittest.TestCase):
    def test_demo_is_rendered_without_files(self):
        from bridge.onboarding import demo_image
        self.assertTrue(demo_image().startswith(b'\x89PNG\r\n\x1a\n'))

    def test_desktop_only_starts_without_a_board(self):
        from bridge.onboarding import Wizard
        with tempfile.TemporaryDirectory() as tmp, patch('bridge.onboarding.ROOT', Path(tmp)), \
             patch('bridge.onboarding.save_preferences') as save, \
             patch('bridge.onboarding.start_monitor') as start:
            wizard = Mock()
            wizard.provider.get.return_value = 'codex'
            wizard.port.get.return_value = ''
            wizard.verified = 'codex'
            wizard.checked_port = None
            wizard.work.side_effect = lambda action, done: (action(), done(None))
            Wizard.start(wizard)
            save.assert_called_once_with('codex', None)
            start.assert_called_once_with('codex', None)

    def test_selected_board_must_be_verified(self):
        from bridge.onboarding import Wizard
        with tempfile.TemporaryDirectory() as tmp, patch('bridge.onboarding.ROOT', Path(tmp)):
            wizard = Mock()
            wizard.provider.get.return_value = 'codex'
            wizard.port.get.return_value = 'COM1'
            wizard.verified = 'codex'
            wizard.checked_port = None
            Wizard.start(wizard)
            wizard.work.assert_not_called()
            self.assertIn('Check USB', wizard.note.set.call_args.args[0])

    def test_quota_access_still_required_for_desktop_only(self):
        from bridge.onboarding import start_issue
        self.assertIn('Verify quota access', start_issue('codex', '', None, None))

if __name__ == '__main__':
    unittest.main()
