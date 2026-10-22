"""Consume only documented Claude Code status-line rate limits, never credentials.

The status-line JSON includes sensitive session/path fields. We hold it only in
memory, whitelist numeric quota fields, and immediately discard everything else.
"""
import json
import base64
import os
from pathlib import Path
import sys
import time
import uuid

from .model import SourceError, normalize, number

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT/'.runtime/claude-usage.json'

def sanitized_event(payload, now=None):
    limits = payload.get('rate_limits') if isinstance(payload,dict) else None
    bucket = {'limitId':'claude'}
    for name,field,minutes in [('five_hour','primary',300),('seven_day','secondary',10080)]:
        window = limits.get(name) if isinstance(limits,dict) else None
        if not isinstance(window,dict):
            continue
        used,reset = window.get('used_percentage'),window.get('resets_at')
        if not number(used) or not 0 <= used <= 100:
            continue
        bucket[field] = {'usedPercent':float(used),'windowDurationMins':minutes,
                         'resetsAt':reset if type(reset) is int and reset>0 else None}
    # An absent field is explicitly unavailable, not 0% used.
    return {'received_at':time.time() if now is None else now,
            'rateLimits':bucket if len(bucket)>1 else None}

def save_event(payload, path=CACHE, now=None):
    record = sanitized_event(payload,now)
    path = Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp = path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
    try:
        with tmp.open('x',encoding='utf-8') as stream:
            if os.name != 'nt':
                os.chmod(tmp,0o600)
            json.dump(record,stream)
        tmp.replace(path)
    finally:
        tmp.unlink(missing_ok=True)
    return record

class ClaudeFileClient:
    def __init__(self,path=CACHE):
        self.path = Path(path)
        self.observed_at = None

    def start(self):
        return self

    def read_limits(self):
        try:
            if self.path.stat().st_size>8192:
                raise SourceError('Invalid Claude quota cache')
            record = json.loads(self.path.read_text(encoding='utf-8'))
            stamp = record.get('received_at')
            if not number(stamp) or stamp>time.time()+5 or stamp<=0:
                raise SourceError('Invalid Claude quota event time')
            normalize(record,now=stamp)
        except (OSError,ValueError,AttributeError,SourceError) as exc:
            raise SourceError('Waiting for Claude Code quota events. Use an eligible signed-in session.') from exc
        self.observed_at = stamp
        return record

    def close(self):
        pass

def statusline_command():
    # Claude's Windows statusLine supports PowerShell. Literal quoting keeps
    # installation paths from becoming shell expressions; no input enters code.
    script = ROOT/'scripts/Claude-Statusline.ps1'
    literal = "'"+str(script).replace("'","''")+"'"
    encoded = base64.b64encode(('& '+literal).encode('utf-16le')).decode('ascii')
    return 'powershell.exe -NoProfile -ExecutionPolicy Bypass -EncodedCommand '+encoded

def configure_statusline(settings_path=None, remove=False):
    base = Path(os.environ.get('CLAUDE_CONFIG_DIR') or Path.home()/'.claude')
    path = Path(settings_path or base/'settings.json')
    original = path.read_bytes() if path.exists() else None
    try:
        data = json.loads(original.decode('utf-8-sig')) if original else {}
    except (ValueError,UnicodeDecodeError) as exc:
        raise SourceError('Claude settings are not valid JSON; no changes made') from exc
    if not isinstance(data,dict):
        raise SourceError('Claude settings must be an object; no changes made')
    own = {'type':'command','command':statusline_command()}
    existing = data.get('statusLine')
    if remove:
        if existing != own:
            raise SourceError('The status line changed; refusing to remove another configuration')
        del data['statusLine']
    else:
        if existing and existing != own:
            raise SourceError('An existing status line is configured. It was preserved. See the manual integration guide.')
        data['statusLine'] = own
    path.parent.mkdir(parents=True,exist_ok=True)
    # Check again before a single atomic replacement. Do not back up other
    # settings into this repository; they may contain private environment values.
    if (path.read_bytes() if path.exists() else None) != original:
        raise SourceError('Settings changed during setup; no changes made')
    tmp = path.with_name(path.name+'.quota-orb-'+uuid.uuid4().hex+'.tmp')
    try:
        with tmp.open('x',encoding='utf-8') as stream:
            if os.name != 'nt':
                os.chmod(tmp,0o600)
            json.dump(data,stream,indent=2)
            stream.write('\n')
        if (path.read_bytes() if path.exists() else None) != original:
            raise SourceError('Settings changed during setup; no changes made')
        tmp.replace(path)
    finally:
        tmp.unlink(missing_ok=True)

def main():
    try:
        raw = sys.stdin.buffer.read(1_048_577)
        if len(raw)>1_048_576:
            return 0
        record = save_event(json.loads(raw))
        if record['rateLimits']:
            snapshot = normalize(record,now=record['received_at'])
            print('Quota Orb | '+' | '.join(f'{w.label}: {int(w.remaining)}% left' for w in snapshot.windows))
        else:
            print('Quota Orb | quota unavailable')
    except (ValueError,OSError,SourceError):
        # Never echo the input, paths, tokens, session IDs, or exception payload.
        print('Quota Orb | waiting for quota')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
