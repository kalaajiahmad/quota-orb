import ctypes
import json
import logging
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import unittest
import uuid
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
POWERSHELL = shutil.which('powershell.exe')


@unittest.skipUnless(os.name == 'nt' and POWERSHELL, 'Windows PowerShell launchers')
class WindowsLauncherTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='.launcher-test-', dir=ROOT)
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root/'scripts').mkdir()
        (self.root/'.venv/Scripts').mkdir(parents=True)
        (self.root/'.venv/Scripts/pythonw.exe').touch()
        self.runtime = self.root/'.runtime'
        self.mutex_name = 'Local\\QuotaOrbLauncherTest-'+uuid.uuid4().hex
        source = (ROOT/'scripts/Start.ps1').read_text(encoding='utf-8')
        # Isolate the production mutex from any real monitor running on this PC.
        self.assertIn('Local\\QuotaOrbBridge', source)
        (self.root/'scripts/Start.ps1').write_text(
            source.replace('Local\\QuotaOrbBridge', self.mutex_name), encoding='utf-8')
        self.harness = self.root/'invoke.ps1'
        self.harness.write_text(r'''
$ErrorActionPreference = 'Stop'
function Start-Process {
    param($FilePath, $ArgumentList, $WorkingDirectory, $WindowStyle,
          $RedirectStandardOutput, $RedirectStandardError, [switch]$PassThru)
    $record = @{file=$FilePath; arguments=@($ArgumentList); working=$WorkingDirectory;
                style=$WindowStyle; stdout=$RedirectStandardOutput; stderr=$RedirectStandardError}
    $record | ConvertTo-Json -Compress | Add-Content -LiteralPath (Join-Path $PSScriptRoot 'launches.jsonl')
    if ($env:QUOTA_ORB_TEST_NEW_STATUS -eq '1') {
        @{running=$true; tray_registered=$true; pid=[int]$env:QUOTA_ORB_TEST_PID;
          updated_at=[DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()/1000.0} |
            ConvertTo-Json | Set-Content -LiteralPath (Join-Path $PSScriptRoot '.runtime/status.json')
    }
    [pscustomobject]@{Id=[int]$env:QUOTA_ORB_TEST_PID; HasExited=$false}
}
if ($env:QUOTA_ORB_TEST_EXPIRE -eq '1') {
    $global:QuotaOrbTestClockBase = [DateTime]::UtcNow
    $global:QuotaOrbTestClockCalls = 0
    function Get-Date {
        $global:QuotaOrbTestClockCalls++
        if ($global:QuotaOrbTestClockCalls -le 2) { $global:QuotaOrbTestClockBase }
        else { $global:QuotaOrbTestClockBase.AddMinutes(2) }
    }
    function Start-Sleep { param($Milliseconds, $Seconds) }
}
try { & (Join-Path $PSScriptRoot 'scripts/Start.ps1') @args; exit 0 }
catch { [Console]::Error.WriteLine($_.Exception.Message); exit 1 }
''', encoding='utf-8')

    def hold_mutex(self):
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
        kernel.CreateMutexW.restype = ctypes.c_void_p
        kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        handle = kernel.CreateMutexW(None, False, self.mutex_name)
        self.assertTrue(handle)
        self.assertNotEqual(ctypes.get_last_error(), 183)
        self.addCleanup(kernel.CloseHandle, handle)

    def status(self, **changes):
        self.runtime.mkdir(exist_ok=True)
        record = dict(running=True, tray_registered=True, pid=os.getpid(), updated_at=time.time())
        record.update(changes)
        (self.runtime/'status.json').write_text(json.dumps(record), encoding='utf-8')

    def start(self, *arguments, expire=False, new_status=False):
        environment = dict(os.environ, QUOTA_ORB_TEST_PID=str(os.getpid()),
                           QUOTA_ORB_TEST_EXPIRE=str(int(expire)),
                           QUOTA_ORB_TEST_NEW_STATUS=str(int(new_status)))
        return subprocess.run([POWERSHELL, '-NoProfile', '-ExecutionPolicy', 'Bypass',
                               '-File', str(self.harness), *arguments],
                              cwd=self.root, env=environment, capture_output=True,
                              text=True, timeout=15, creationflags=subprocess.CREATE_NO_WINDOW)

    def launches(self):
        path = self.root/'launches.jsonl'
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []

    def test_existing_healthy_monitor_receives_display_request_without_second_process(self):
        self.hold_mutex()
        self.status()
        result = self.start('-ShowWindow')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.runtime/'open-display').exists())
        self.assertEqual(self.launches(), [])
        self.assertFalse((self.runtime/'stop').exists())

    def test_direct_start_keeps_existing_monitor_in_tray(self):
        self.hold_mutex()
        self.status()
        result = self.start()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.runtime/'open-display').exists())
        self.assertEqual(self.launches(), [])

    def test_unhealthy_existing_monitor_cannot_report_success_or_request_a_window(self):
        self.hold_mutex()
        for changes in ({'updated_at':time.time()-60}, {'updated_at':time.time()+60},
                        {'tray_registered':False}, {'running':False}, {'pid':2147483647}):
            with self.subTest(changes=changes):
                self.status(**changes)
                result = self.start('-ShowWindow', expire=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('existing monitor is not responding', result.stderr)
                self.assertFalse((self.runtime/'open-display').exists())
                self.assertFalse((self.runtime/'stop').exists(), 'Do not stop an existing monitor on timeout')
                self.assertEqual(self.launches(), [])

    def test_new_monitor_starts_hidden_with_selected_provider_then_requests_window(self):
        result = self.start('-ShowWindow', '-Provider', 'claude', '-Port', 'COM99', new_status=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        launch, = self.launches()
        self.assertEqual(Path(launch['file']), self.root/'.venv/Scripts/pythonw.exe')
        self.assertEqual(launch['arguments'], ['-m','bridge','--quiet','--provider','claude','--port','COM99'])
        self.assertEqual(launch['style'], 'Hidden')
        self.assertEqual(Path(launch['working']), self.root)
        self.assertTrue((self.runtime/'open-display').exists())

    def test_new_monitor_without_healthy_status_requests_shutdown(self):
        result = self.start('-ShowWindow', expire=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Shutdown requested', result.stderr)
        self.assertEqual(len(self.launches()), 1)
        self.assertFalse((self.runtime/'open-display').exists())
        self.assertTrue((self.runtime/'stop').exists(), result.stderr)

    def test_invalid_port_is_rejected_before_runtime_mutation_even_when_running(self):
        self.hold_mutex()
        result = self.start('-ShowWindow', '-Port', 'COM1&unexpected')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Port must look like COM4', result.stderr)
        self.assertFalse(self.runtime.exists())
        self.assertEqual(self.launches(), [])

    def test_cmd_entry_points_forward_to_the_intended_script_and_flags(self):
        capture = self.root/'capture.ps1'
        capture.write_text("ConvertTo-Json -InputObject @($args) | Set-Content -LiteralPath "
                           "(Join-Path $PSScriptRoot 'arguments.json')", encoding='utf-8')
        (self.root/'capture.cmd').write_text(
            '@echo off\n'+f'"{POWERSHELL}" -NoProfile -ExecutionPolicy Bypass '
            '-File "%~dp0capture.ps1" %*\n', encoding='utf-8')
        for name, script, flags in (
                ('Start Quota Orb.cmd', 'Start.ps1', ['-ShowWindow']),
                ('Start Codex Peek.cmd', 'Start.ps1', ['-Provider','codex','-ShowWindow']),
                ('Stop Codex Peek.cmd', 'Stop.ps1', [])):
            with self.subTest(name=name):
                source = (ROOT/name).read_text(encoding='utf-8')
                # Replace only the external executable; exercise cmd's real quoting and forwarding.
                self.assertIn('powershell.exe', source)
                (self.root/name).write_text(source.replace('powershell.exe', 'call "%~dp0capture.cmd"'),
                                            encoding='utf-8')
                result = subprocess.run(['cmd.exe','/d','/c',str(self.root/name)], cwd=self.root,
                    capture_output=True, text=True, timeout=15, creationflags=subprocess.CREATE_NO_WINDOW)
                self.assertEqual(result.returncode, 0, result.stderr)
                arguments = json.loads((self.root/'arguments.json').read_text(encoding='utf-8-sig'))
                self.assertEqual(arguments[:4], ['-NoProfile','-ExecutionPolicy','Bypass','-File'])
                self.assertEqual(Path(arguments[4]), self.root/'scripts'/script)
                self.assertEqual(arguments[5:], flags)


@unittest.skipUnless(os.name == 'nt', 'Windows monitor and desktop singleton')
class DisplayRequestTests(unittest.TestCase):
    def test_busy_request_retries_next_frame_without_interrupting_monitoring(self):
        from bridge.__main__ import main
        import zlib
        with tempfile.TemporaryDirectory() as tmp:
            runtime = Path(tmp)
            request = runtime/'open-display'
            original_unlink = Path.unlink
            attempts, records = [], []
            def locked_once(path, *args, **kwargs):
                if path == request and request.exists():
                    attempts.append(path)
                    if len(attempts) == 1:
                        raise PermissionError('Launcher is still writing its request')
                return original_unlink(path, *args, **kwargs)
            with patch('sys.argv', ['bridge','--quiet','--runtime',str(runtime),
                                   '--output',str(runtime/'preview.png')]), \
                 patch('bridge.tray.Tray') as tray, \
                 patch('bridge.__main__.UsageSession') as session, \
                 patch('bridge.__main__.MUTEX_NAME', 'Local\\QuotaOrbTest-'+uuid.uuid4().hex), \
                 patch('bridge.usb.Display') as display, \
                 patch('bridge.__main__.subprocess.Popen') as launch, \
                 patch('bridge.__main__.RotatingFileHandler', return_value=logging.NullHandler()), \
                 patch('bridge.__main__.logging.basicConfig'), \
                 patch.object(Path, 'unlink', locked_once):
                session.return_value.get.return_value = None, None
                session.return_value.paused = session.return_value.transitioning = False
                device = display.return_value
                device.port, device.serial, device.button_presses, device.last_ack = 'COM99', None, 0, None
                device.connect.side_effect = lambda: setattr(device, 'serial', True)
                device.close.side_effect = lambda: setattr(device, 'serial', None)
                def acknowledge(frame):
                    device.last_ack = {'type':'ack','seq':len(records)+1,'crc':zlib.crc32(frame)}
                device.send.side_effect = acknowledge
                tray.return_value.failed.is_set.return_value = False
                tray.return_value.registered = True
                tray.return_value.start.side_effect = request.touch
                launch.return_value.poll.return_value = None
                def update(status):
                    if status.get('stopping'):
                        return
                    records.append(dict(status))
                    if len(records) == 1:
                        self.assertTrue(request.exists(), 'A busy request must remain available for retry')
                        launch.assert_not_called()
                    else:
                        self.assertFalse(request.exists())
                        launch.assert_called_once()
                        tray.call_args.args[0].put('quit')
                tray.return_value.update.side_effect = update
                self.assertEqual(main(), 0)
                self.assertEqual(len(attempts), 2)
                self.assertEqual([status['frames_acknowledged'] for status in records], [1,2])
                self.assertEqual([status['last_ack']['seq'] for status in records], [1,2])
                self.assertTrue(all(status['running'] and status['usb_connected'] for status in records))
                device.connect.assert_called_once()
                self.assertEqual(device.send.call_count, 2)
                launch.assert_called_once()
                session.return_value.close.assert_called_once()

    def test_monitor_consumes_requests_and_reuses_its_existing_display_process(self):
        from bridge.__main__ import main
        with tempfile.TemporaryDirectory() as tmp:
            runtime = Path(tmp)
            with patch('sys.argv', ['bridge','--quiet','--preview-only','--runtime',str(runtime),
                                   '--output',str(runtime/'preview.png')]), \
                 patch('bridge.tray.Tray') as tray, \
                 patch('bridge.__main__.UsageSession') as session, \
                 patch('bridge.__main__.MUTEX_NAME', 'Local\\QuotaOrbTest-'+uuid.uuid4().hex), \
                 patch('bridge.usb.Display') as display, \
                 patch('bridge.__main__.subprocess.Popen') as launch, \
                 patch('bridge.__main__.RotatingFileHandler', return_value=logging.NullHandler()), \
                 patch('bridge.__main__.logging.basicConfig'):
                session.return_value.get.return_value = None, None
                session.return_value.paused = session.return_value.transitioning = False
                device = display.return_value
                device.port, device.serial, device.button_presses, device.last_ack = 'COM99', None, 0, None
                tray.return_value.failed.is_set.return_value = False
                tray.return_value.registered = True
                tray.return_value.start.side_effect = lambda: (runtime/'open-display').touch()
                launch.return_value.poll.return_value = None
                updates = []
                def update(status):
                    if status.get('stopping'):
                        return
                    updates.append(status)
                    self.assertFalse((runtime/'open-display').exists())
                    self.assertEqual(launch.call_count, 1)
                    if len(updates) == 1:
                        (runtime/'open-display').touch()
                    else:
                        self.assertTrue((runtime/'show-display').exists())
                        tray.call_args.args[0].put('quit')
                tray.return_value.update.side_effect = update
                self.assertEqual(main(), 0)
                self.assertEqual(len(updates), 2)
                arguments = launch.call_args.args[0]
                self.assertEqual(arguments[1:], ['-m','bridge.display','--runtime',str(runtime.resolve())])
                device.connect.assert_not_called()
                session.return_value.close.assert_called_once()
                self.assertFalse((runtime/'open-display').exists())
                self.assertFalse((runtime/'process.json').exists())


if __name__ == '__main__':
    unittest.main()
