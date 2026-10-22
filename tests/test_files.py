import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from bridge.files import atomic_write


class AtomicFileTests(unittest.TestCase):
    def test_transient_lock_retries_and_replaces_complete_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'status.json'
            path.write_bytes(b'old')
            replace = os.replace
            calls = []
            def locked_once(source,target):
                calls.append(source)
                if len(calls)==1:
                    self.assertEqual(path.read_bytes(),b'old')
                    raise PermissionError('Reader lock')
                replace(source,target)
            with patch('bridge.files.os.replace',side_effect=locked_once):
                atomic_write(path,b'new complete content')
            self.assertEqual(path.read_bytes(),b'new complete content')
            self.assertEqual(len(calls),2)
            self.assertEqual(list(Path(tmp).iterdir()),[path])

    def test_permanent_lock_preserves_previous_file_and_cleans_temp(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'status.json'
            path.write_bytes(b'old')
            with patch('bridge.files.os.replace',side_effect=PermissionError('Locked')):
                with self.assertRaises(PermissionError):
                    atomic_write(path,b'new',replace_wait=0)
            self.assertEqual(path.read_bytes(),b'old')
            self.assertEqual(list(Path(tmp).iterdir()),[path])

    @unittest.skipUnless(os.name=='nt','Actual Windows sharing semantics')
    def test_windows_read_handle_can_release_during_atomic_write(self):
        import ctypes
        kernel = ctypes.WinDLL('kernel32',use_last_error=True)
        create = kernel.CreateFileW
        create.argtypes = [ctypes.c_wchar_p,ctypes.c_uint32,ctypes.c_uint32,
            ctypes.c_void_p,ctypes.c_uint32,ctypes.c_uint32,ctypes.c_void_p]
        create.restype = ctypes.c_void_p
        close = kernel.CloseHandle
        close.argtypes = [ctypes.c_void_p]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'status.json'
            path.write_bytes(b'old')
            # Permit read/write but intentionally omit FILE_SHARE_DELETE.
            handle = create(str(path),0x80000000,3,None,3,0x80,None)
            self.assertNotIn(handle,(None,ctypes.c_void_p(-1).value))
            release = threading.Timer(.1,lambda:close(handle))
            release.start()
            try:
                atomic_write(path,b'confirmed new frame')
            finally:
                release.join()
            self.assertEqual(path.read_bytes(),b'confirmed new frame')


if __name__=='__main__':
    unittest.main()
