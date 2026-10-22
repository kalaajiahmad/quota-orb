"""Windows notification-area presence for the running bridge. Standard library only.

The icon belongs to the bridge process, not a separate hidden supervisor. UI
commands are queued to the bridge; icon registration failure stops monitoring.
"""
import ctypes as C
from ctypes import wintypes as W
import os
from pathlib import Path
import threading
import uuid

ROOT = Path(__file__).resolve().parents[1]
ICON_GUID = uuid.UUID('11e6796a-a5ff-489e-a2df-b613bb71e8c7')

def presentation(status):
    provider = {'codex':'Codex','claude':'Claude Code'}.get(status.get('provider'),'Provider')
    if status.get('stopping'):
        return 'idle','Quota Orb - stopping monitor'
    if status.get('paused'):
        return 'idle',f'Quota Orb - {provider} | '+('Pausing' if status.get('transitioning') else 'Paused')
    if status.get('transitioning'):
        return 'idle',f'Quota Orb - {provider} | Resuming'
    if not status.get('usb_connected'):
        return 'warning',f'Quota Orb - {provider} | USB disconnected'
    source = status.get('source','NO DATA')
    if source in ('BLOCKED','NO DATA'):
        return 'error',f'Quota Orb - {provider} | {source} | USB connected'
    if source != 'LIVE':
        return 'warning',f'Quota Orb - {provider} | {source} | USB connected'
    return 'live',f'Quota Orb - {provider} | LIVE | USB connected'

def status_text(status):
    _,tip = presentation(status)
    return (tip+'\n\nAcknowledged frames: '+str(status.get('frames_acknowledged',0))+
            '\n\nClick the icon for the live OLED mirror.\nRight-click for setup, status, Pause, Resume, and Quit.\n'
            'Quit stops monitoring and removes the icon.\n'
            'Windows may place the icon under the taskbar overflow arrow.')

class Tray:
    def __init__(self,commands,provider='codex'):
        if os.name != 'nt':
            raise OSError('The notification-area app supports Windows only')
        self.commands = commands
        self.status = {'provider':provider,'paused':False}
        self.lock = threading.Lock()
        self.ready = threading.Event()
        self.failed = threading.Event()
        self.error = None
        self.closing = threading.Event()
        self.hwnd = None
        self.registered = False
        self.thread = threading.Thread(target=self.run,name='Quota Orb notification icon',daemon=True)

    def start(self):
        self.thread.start()
        if not self.ready.wait(10) or self.failed.is_set():
            self.close()
            raise OSError('Could not display the Quota Orb notification icon; monitoring was not started')

    def update(self,status):
        with self.lock:
            self.status = dict(status)

    def snapshot(self):
        with self.lock:
            return dict(self.status)

    def close(self):
        self.closing.set()
        if self.hwnd:
            self.user.PostMessageW(self.hwnd,0x0010,0,0)
        self.thread.join(timeout=5)

    def action(self,identifier):
        if identifier == 1:
            self.commands.put('setup')
        elif identifier == 2:
            self.user.MessageBoxW(self.hwnd,status_text(self.snapshot()),'Quota Orb | Status',0x40)
        elif identifier == 3:
            self.commands.put('toggle')
        elif identifier == 4:
            self.commands.put('quit')
        elif identifier == 5:
            self.commands.put('display')

    def run(self):
        icons = []
        try:
            self._run(icons)
        except BaseException as exc:
            self.error = str(exc)
            self.failed.set()
            self.commands.put('quit')
        finally:
            if not self.closing.is_set():
                self.failed.set()
                self.commands.put('quit')
            if self.registered:
                self.shell.Shell_NotifyIconW(2,C.byref(self.nid))
                self.registered = False
            for handle in icons:
                self.user.DestroyIcon(handle)
            self.ready.set()

    def _run(self,icons):
        self.user = user = C.WinDLL('user32',use_last_error=True)
        self.shell = shell = C.WinDLL('shell32',use_last_error=True)
        kernel = C.WinDLL('kernel32',use_last_error=True)
        LRESULT = C.c_ssize_t
        CALLBACK = C.WINFUNCTYPE(LRESULT,W.HWND,W.UINT,W.WPARAM,W.LPARAM)
        class GUID(C.Structure):
            _fields_ = [('a',W.DWORD),('b',W.WORD),('c',W.WORD),('d',C.c_ubyte*8)]
        class NID(C.Structure):
            _fields_ = [('cbSize',W.DWORD),('hWnd',W.HWND),('uID',W.UINT),('uFlags',W.UINT),
                ('uCallbackMessage',W.UINT),('hIcon',W.HICON),('szTip',W.WCHAR*128),
                ('dwState',W.DWORD),('dwStateMask',W.DWORD),('szInfo',W.WCHAR*256),
                ('uVersion',W.UINT),('szInfoTitle',W.WCHAR*64),('dwInfoFlags',W.DWORD),
                ('guidItem',GUID),('hBalloonIcon',W.HICON)]
        class WC(C.Structure):
            _fields_ = [('style',W.UINT),('lpfnWndProc',CALLBACK),('cbClsExtra',C.c_int),
                ('cbWndExtra',C.c_int),('hInstance',W.HINSTANCE),('hIcon',W.HICON),
                ('hCursor',W.HANDLE),('hbrBackground',W.HBRUSH),('lpszMenuName',W.LPCWSTR),
                ('lpszClassName',W.LPCWSTR)]
        def api(dll,name,restype,*args):
            f = getattr(dll,name)
            f.restype, f.argtypes = restype,list(args)
            return f
        api(kernel,'GetModuleHandleW',W.HMODULE,W.LPCWSTR)
        api(user,'RegisterClassW',W.ATOM,C.POINTER(WC))
        api(user,'UnregisterClassW',W.BOOL,W.LPCWSTR,W.HINSTANCE)
        api(user,'CreateWindowExW',W.HWND,W.DWORD,W.LPCWSTR,W.LPCWSTR,W.DWORD,
            C.c_int,C.c_int,C.c_int,C.c_int,W.HWND,W.HMENU,W.HINSTANCE,W.LPVOID)
        api(user,'DefWindowProcW',LRESULT,W.HWND,W.UINT,W.WPARAM,W.LPARAM)
        api(user,'DestroyWindow',W.BOOL,W.HWND)
        api(user,'PostQuitMessage',None,C.c_int)
        api(user,'PostMessageW',W.BOOL,W.HWND,W.UINT,W.WPARAM,W.LPARAM)
        api(user,'GetMessageW',W.BOOL,C.POINTER(W.MSG),W.HWND,W.UINT,W.UINT)
        api(user,'TranslateMessage',W.BOOL,C.POINTER(W.MSG))
        api(user,'DispatchMessageW',LRESULT,C.POINTER(W.MSG))
        api(user,'SetTimer',C.c_size_t,W.HWND,C.c_size_t,W.UINT,W.LPVOID)
        api(user,'KillTimer',W.BOOL,W.HWND,C.c_size_t)
        api(user,'RegisterWindowMessageW',W.UINT,W.LPCWSTR)
        api(user,'LoadImageW',W.HANDLE,W.HINSTANCE,W.LPCWSTR,W.UINT,C.c_int,C.c_int,W.UINT)
        api(user,'DestroyIcon',W.BOOL,W.HICON)
        api(user,'GetSystemMetrics',C.c_int,C.c_int)
        api(user,'CreatePopupMenu',W.HMENU)
        api(user,'AppendMenuW',W.BOOL,W.HMENU,W.UINT,C.c_size_t,W.LPCWSTR)
        api(user,'TrackPopupMenu',W.UINT,W.HMENU,W.UINT,C.c_int,C.c_int,C.c_int,W.HWND,W.LPVOID)
        api(user,'DestroyMenu',W.BOOL,W.HMENU)
        api(user,'GetCursorPos',W.BOOL,C.POINTER(W.POINT))
        api(user,'SetForegroundWindow',W.BOOL,W.HWND)
        api(user,'MessageBoxW',C.c_int,W.HWND,W.LPCWSTR,W.LPCWSTR,W.UINT)
        api(shell,'Shell_NotifyIconW',W.BOOL,W.DWORD,C.POINTER(NID))
        callback_message = 0x8000+17
        taskbar_created = user.RegisterWindowMessageW('TaskbarCreated')
        instance = kernel.GetModuleHandleW(None)
        class_name = 'QuotaOrbNotificationWindow'
        loaded = {}
        size = user.GetSystemMetrics(49)
        for name in ('live','warning','error','idle'):
            handle = user.LoadImageW(None,str(ROOT/'assets'/('tray-'+name+'.ico')),1,size,size,0x10)
            if not handle:
                raise C.WinError(C.get_last_error())
            loaded[name] = handle
            icons.append(handle)
        self.nid = nid = NID()
        nid.cbSize = C.sizeof(NID)
        nid.uID = 1
        nid.guidItem = GUID.from_buffer_copy(ICON_GUID.bytes_le)
        nid.uCallbackMessage = callback_message
        self._last = None

        def icon(add=False):
            state,tip = presentation(self.snapshot())
            nid.uFlags = 1|2|4|32|128  # message, icon, tip, GUID, standard tooltip
            nid.hIcon, nid.szTip = loaded[state],tip[:127]
            if add:
                if not shell.Shell_NotifyIconW(0,C.byref(nid)):
                    raise OSError('Windows refused the notification icon')
                self.registered = True
                nid.uVersion = 4
                if not shell.Shell_NotifyIconW(4,C.byref(nid)):
                    raise OSError('Windows refused notification icon version 4')
            elif (state,tip) != self._last:
                if not shell.Shell_NotifyIconW(1,C.byref(nid)):
                    icon(True)
            self._last = (state,tip)

        def menu():
            popup = user.CreatePopupMenu()
            point = W.POINT()
            user.GetCursorPos(C.byref(point))
            try:
                user.AppendMenuW(popup,2,0,'Quota Orb')  # disabled heading
                for identifier,title in [(5,'Open live display'),(2,'Show status'),(1,'Open setup'),
                    (3,'Resume monitoring' if self.snapshot().get('paused') else 'Pause monitoring'),
                    (4,'Quit Quota Orb')]:
                    user.AppendMenuW(popup,0,identifier,title)
                user.SetForegroundWindow(self.hwnd)
                chosen = user.TrackPopupMenu(popup,0x100|0x2,point.x,point.y,0,self.hwnd,None)
                if chosen:
                    self.action(chosen)
                user.PostMessageW(self.hwnd,0,0,0)
                shell.Shell_NotifyIconW(3,C.byref(nid))
            finally:
                user.DestroyMenu(popup)

        @CALLBACK
        def procedure(hwnd,message,wparam,lparam):
            try:
                if message == callback_message:
                    event = lparam & 0xffff
                    if event in (0x007b,0x0205):  # keyboard context menu / right click
                        menu()
                    elif event in (0x0203,0x0400,0x0401):  # mouse / keyboard selection
                        self.action(5)
                    return 0
                if message == taskbar_created:
                    icon(True)
                    return 0
                if message == 0x0113:
                    if self.closing.is_set():
                        user.DestroyWindow(hwnd)
                        return 0
                    icon()
                    return 0
                if message == 0x0010:
                    user.DestroyWindow(hwnd)
                    return 0
                if message == 0x0002:
                    user.PostQuitMessage(0)
                    return 0
            except BaseException:
                self.failed.set()
                self.commands.put('quit')
            return user.DefWindowProcW(hwnd,message,wparam,lparam)

        wc = WC(lpfnWndProc=procedure,hInstance=instance,lpszClassName=class_name)
        if not user.RegisterClassW(C.byref(wc)):
            raise C.WinError(C.get_last_error())
        try:
            self.hwnd = user.CreateWindowExW(0,class_name,'Quota Orb notification icon',0,0,0,0,0,None,None,instance,None)
            if not self.hwnd:
                raise C.WinError(C.get_last_error())
            nid.hWnd = self.hwnd
            icon(True)
            if not user.SetTimer(self.hwnd,1,1000,None):
                raise OSError('Could not start the notification icon status timer')
            self.ready.set()
            if self.closing.is_set():
                user.PostMessageW(self.hwnd,0x0010,0,0)
            message = W.MSG()
            while True:
                result = user.GetMessageW(C.byref(message),None,0,0)
                if result == -1:
                    raise C.WinError(C.get_last_error())
                if result == 0:
                    break
                user.TranslateMessage(C.byref(message))
                user.DispatchMessageW(C.byref(message))
            user.KillTimer(self.hwnd,1)
        finally:
            if self.registered:
                shell.Shell_NotifyIconW(2,C.byref(nid))
                self.registered = False
            if self.hwnd:
                user.DestroyWindow(self.hwnd)
                self.hwnd = None
            user.UnregisterClassW(class_name,instance)
