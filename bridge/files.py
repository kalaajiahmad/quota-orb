"""Atomic local output with bounded Windows reader-lock recovery."""
import os
from pathlib import Path
import tempfile
import time


def atomic_write(path, data, replace_wait=1.0):
    path = Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix='.'+path.name+'.',suffix='.tmp',dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor,'wb') as stream:
            stream.write(data)
        deadline = time.monotonic()+replace_wait
        while True:
            try:
                os.replace(temporary,path)
                return
            except PermissionError:
                # Windows readers/antivirus can briefly deny replacement. Keep
                # the old complete file visible until the new one can replace it.
                if time.monotonic()>=deadline:
                    raise
                time.sleep(min(.025,max(0,deadline-time.monotonic())))
    finally:
        temporary.unlink(missing_ok=True)
