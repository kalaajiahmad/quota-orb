"""Provider capabilities and non-secret local preferences."""
import json
import os
from pathlib import Path
import shutil
import subprocess

from .codex import find_codex
from .model import SourceError
from .files import atomic_write

ROOT = Path(__file__).resolve().parents[1]
PROVIDERS = {
    'codex': {'name':'Codex', 'status':'Available - subscription quota polling',
              'install':'https://learn.chatgpt.com/docs/cli', 'auth':['login']},
    'claude': {'name':'Claude Code', 'status':'Experimental - local status-line events',
               'install':'https://code.claude.com/docs/en/quickstart', 'auth':['auth','login']},
    'gemini': {'name':'Gemini', 'status':'Unavailable - account-quota adapter not verified',
               'install':'https://geminicli.com/docs/get-started/', 'auth':None},
}

def executable(provider, explicit=None):
    if provider == 'codex':
        return find_codex(explicit)
    if provider != 'claude':
        raise SourceError('This provider has no supported quota adapter yet')
    candidates = [Path(explicit)] if explicit else [
        Path(shutil.which('claude') or ''), Path.home()/'.local/bin/claude.exe']
    for path in candidates:
        if path.is_file() and path.suffix.lower() == '.exe':
            return str(path.resolve())
    raise SourceError('Install the official native Claude Code CLI first')

def login_command(provider, program):
    args = PROVIDERS.get(provider,{}).get('auth')
    if not args:
        raise SourceError('No sign-in flow is enabled for this provider')
    # Fixed arguments, no shell, no pasted token/API-key path.
    return [str(program), *args]

def launch_login(provider, program):
    # Visible vendor-owned console so browser-login fallbacks stay with the CLI.
    # Never redirect, parse, persist, or log its authentication output.
    flags = subprocess.CREATE_NEW_CONSOLE if os.name == 'nt' else 0
    return subprocess.Popen(login_command(provider,program), cwd=ROOT,
                            creationflags=flags)

def preferences(path=None):
    path = Path(path or ROOT/'.runtime/preferences.json')
    try:
        raw = json.loads(path.read_text(encoding='utf-8'))
    except (OSError,ValueError):
        return {'provider':'codex','port':None}
    if not isinstance(raw,dict) or raw.get('provider') not in ('codex','claude'):
        return {'provider':'codex','port':None}
    port = raw.get('port')
    if port is not None and (not isinstance(port,str) or not port.startswith('COM') or not port[3:].isdigit()):
        port = None
    return {'provider':raw['provider'],'port':port}

def save_preferences(provider, port=None, path=None):
    if provider not in ('codex','claude'):
        raise SourceError('This provider has no quota adapter')
    path = Path(path or ROOT/'.runtime/preferences.json')
    data = {'provider':provider,'port':port}
    atomic_write(path,(json.dumps(data,indent=2)+'\n').encode('utf-8'))

def start_monitor(provider, port=None):
    # A fixed local script owns background startup and the duplicate-process guard.
    command = ['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass',
               '-File',str(ROOT/'scripts/Start.ps1'),'-Provider',provider]
    if port:
        if not port.startswith('COM') or not port[3:].isdigit():
            raise SourceError('Choose an available serial port')
        command += ['-Port',port]
    subprocess.run(command,cwd=ROOT,check=True,creationflags=subprocess.CREATE_NO_WINDOW)
