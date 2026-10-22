import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from bridge.claude import sanitized_event, save_event, ClaudeFileClient, configure_statusline, statusline_command
from bridge.model import normalize, freshness, SourceError
from bridge.providers import login_command, preferences, save_preferences, launch_login

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

class ProviderFlowTests(unittest.TestCase):
    def test_login_uses_only_fixed_vendor_arguments(self):
        self.assertEqual(login_command('codex','provider.exe'),['provider.exe','login'])
        self.assertEqual(login_command('claude','provider.exe'),['provider.exe','auth','login'])
        with self.assertRaises(SourceError):
            login_command('gemini','provider.exe')

    def test_auth_output_is_not_captured_or_redirected(self):
        with patch('bridge.providers.subprocess.Popen') as run:
            launch_login('codex','provider.exe')
            args,kwargs = run.call_args
            self.assertNotIn('shell',kwargs)
            self.assertNotIn('stdout',kwargs)
            self.assertNotIn('stderr',kwargs)
            self.assertEqual(args[0],['provider.exe','login'])

    def test_preferences_store_only_nonsecret_selection(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'prefs.json'
            save_preferences('claude','COM99',path)
            self.assertEqual(preferences(path),{'provider':'claude','port':'COM99'})
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

if __name__ == '__main__':
    unittest.main()
