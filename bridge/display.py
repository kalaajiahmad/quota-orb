"""Live Windows mirror of the exact USB-acknowledged 128x64 framebuffer.

This view reads only the local atomic status file: no provider calls or USB port.
It never redraws quota values independently of the acknowledged device frame.
"""
import argparse
import base64
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import tkinter as tk
import zlib

from .providers import ROOT
from .render import png_bytes, render
from .model import normalize
from .ui import MotionButton, StatusPulse, motion_enabled, windows_app_identity, window_icon

BG, PANEL, TEXT, MUTED, ACCENT = '#0d1d23','#172e35','#e0eeee','#a9c4ca','#d7a17d'


def confirmed_pixels(status):
    """Reject incomplete, malformed, or CRC-mismatched local frame records."""
    try:
        record = status['display_frame']
        pixels = bytes.fromhex(record['pixels'])
        ack = record['ack']
        stamp = record['acknowledged_at']
        if (len(pixels) != 1024 or ack.get('type') != 'ack' or
                type(ack.get('seq')) is not int or not 1 <= ack['seq'] <= 0xffffffff or
                type(ack.get('crc')) is not int or ack['crc'] != zlib.crc32(pixels) or
                type(stamp) not in (int,float) or not 0 < stamp <= time.time()+5):
            return None
        return pixels
    except (KeyError, TypeError, ValueError, AttributeError):
        return None


def mirror_state(status, now=None):
    now = time.time() if now is None else now
    if not status.get('running'):
        return 'MONITOR STOPPED', False
    if now-status.get('updated_at',0) > 6:
        return 'MONITOR NOT RESPONDING · last confirmed frame', False
    if status.get('paused'):
        return 'PAUSED · last confirmed frame', False
    if not status.get('usb_connected'):
        return 'USB DISCONNECTED · last confirmed frame', False
    record = status.get('display_frame') or {}
    if now-record.get('acknowledged_at',0) > 3:
        return 'WAITING FOR USB ACK · last confirmed frame', False
    return 'LIVE USB MIRROR · '+status.get('source','NO DATA'), True


class LiveDisplay:
    def __init__(self, root, runtime, demo=False):
        self.root, self.runtime, self.demo = root, Path(runtime), demo
        self.frame = None
        self.image = None
        self.setup = None
        self.studio = None
        root.title('Quota Orb | Display studio' if not demo else 'Quota Orb | Simulated display')
        root.configure(bg=BG)
        window_icon(root)
        root.resizable(False,False)
        self.zoom = tk.IntVar(value=4)
        self.state = tk.StringVar(value='WAITING FOR FIRST CONFIRMED FRAME')
        self.detail = tk.StringVar(value='Connect the board and start monitoring from setup.')
        self.host = tk.Frame(root,bg=BG)
        self.host.pack(fill='both',expand=True)
        self.live = content = tk.Frame(self.host,bg=BG,padx=24,pady=20)
        content.pack()
        self.active = content
        self.navigation_timer = None
        self.refresh_timer = None
        header = tk.Frame(content,bg=BG)
        header.pack(fill='x')
        tk.Label(header,text='Quota Orb.',bg=BG,fg=TEXT,font=('Segoe UI',21,'bold')).pack(side='left')
        tk.Label(header,text='128 × 64  /  LIVE MIRROR',bg=BG,fg=ACCENT,
                 font=('Segoe UI',9,'bold')).pack(side='right')
        status_row = tk.Frame(content,bg=BG)
        status_row.pack(fill='x',pady=(10,12))
        self.pulse = StatusPulse(status_row)
        self.pulse.pack(side='left',padx=(0,6))
        self.state_label = tk.Label(status_row,textvariable=self.state,bg=BG,fg=MUTED,
                                    font=('Segoe UI',10,'bold'))
        self.state_label.pack(side='left')
        bezel = tk.Frame(content,bg='#071519',highlightbackground=ACCENT,highlightthickness=1,padx=12,pady=12)
        bezel.pack()
        self.screen = tk.Label(bezel,bg='#070f13',borderwidth=0,highlightthickness=0)
        self.screen.pack()
        controls = tk.Frame(content,bg=BG)
        controls.pack(fill='x',pady=(14,0))
        tk.Label(controls,text='PIXEL SCALE',bg=BG,fg=MUTED,font=('Segoe UI',8,'bold')).pack(side='left',padx=(0,8))
        self.scale_buttons = {}
        for scale in (1,2,4,6):
            button = MotionButton(controls,f'{scale}×',lambda value=scale:self.set_zoom(value),width=38,
                                  accent=scale==4,height=32)
            button.pack(side='left',padx=2)
            self.scale_buttons[scale] = button
        MotionButton(controls,'Edit layout',self.edit_layout,accent=True,height=32).pack(side='right',padx=(8,0))
        MotionButton(controls,'Setup',self.open_setup,height=32).pack(side='right')
        tk.Label(content,textvariable=self.detail,bg=BG,fg=MUTED,font=('Segoe UI',9),
                 wraplength=520,justify='left').pack(anchor='w',pady=(12,4))
        tk.Label(content,text='Close this window to keep monitoring in the notification area.',
                 bg=BG,fg=MUTED,font=('Segoe UI',8)).pack(anchor='w')
        self.redraw()
        root.update_idletasks()
        root.geometry(f'{content.winfo_reqwidth()}x{content.winfo_reqheight()}')
        root.bind('<Destroy>',self.destroyed,add='+')
        self.refresh_timer = root.after(0,self.refresh)

    def open_setup(self):
        if self.setup is None or self.setup.poll() is not None:
            self.setup = subprocess.Popen([str(Path(sys.executable).with_name('pythonw.exe')),
                '-m','bridge.onboarding'],cwd=ROOT,creationflags=subprocess.CREATE_NO_WINDOW)

    def edit_layout(self):
        if self.studio is None:
            from .studio import Studio
            self.studio = Studio(self.host,self.runtime,self.show_live)
        self.navigate(self.studio.root)

    def show_live(self):
        self.navigate(self.live)

    def navigate(self,target):
        if target is self.active:
            return
        if self.navigation_timer:
            self.root.after_cancel(self.navigation_timer)
            self.navigation_timer = None
        previous,self.active = self.active,target
        previous.pack_forget()
        previous.place_forget()
        target.pack()
        self.root.update_idletasks()
        width,height = target.winfo_reqwidth(),target.winfo_reqheight()
        start_w,start_h = self.root.winfo_width(),self.root.winfo_height()
        target.pack_forget()
        target.place(x=24,y=0,width=width,height=height)
        target.lift()
        started = time.monotonic()
        enabled = motion_enabled() and self.root.state()!='withdrawn'
        def animate():
            fraction = min(1,(time.monotonic()-started)/0.24) if enabled else 1
            eased = 1-(1-fraction)**3
            self.root.geometry(f'{round(start_w+(width-start_w)*eased)}x{round(start_h+(height-start_h)*eased)}')
            target.place_configure(x=round(24*(1-eased)))
            if fraction<1:
                self.navigation_timer = self.root.after(16,animate)
            else:
                self.navigation_timer = None
                target.place_forget()
                target.pack()
        animate()

    def destroyed(self,event):
        if event.widget is self.root:
            for timer in (self.navigation_timer,self.refresh_timer):
                if timer:
                    self.root.after_cancel(timer)
            self.navigation_timer = self.refresh_timer = None

    def redraw(self):
        pixels = self.frame if self.frame is not None else bytes(1024)
        self.image = tk.PhotoImage(data=base64.b64encode(png_bytes(pixels,self.zoom.get())))
        self.screen.configure(image=self.image)

    def set_zoom(self,scale):
        self.zoom.set(scale)
        for value,button in self.scale_buttons.items():
            button.configure(accent=value==scale)
        self.redraw()
        if self.active is self.live:
            self.root.update_idletasks()
            self.root.geometry(f'{self.live.winfo_reqwidth()}x{self.live.winfo_reqheight()}')

    def refresh(self):
        try:
            show = self.runtime/'show-display'
            if show.exists():
                show.unlink(missing_ok=True)
                self.root.deiconify()
                self.root.lift()
                self.root.focus_force()
                self.show_live()
            if self.demo:
                now = time.time()
                snapshot = normalize({'rateLimits':{'limitId':'codex','primary':{
                    'usedPercent':28,'windowDurationMins':10080,'resetsAt':int(now)+311040}}},now=now)
                frame = render(snapshot,now)
                data = {'running':True,'updated_at':now,'source':'LIVE','usb_connected':True,
                    'display_frame':{'pixels':frame.hex(),'ack':{'type':'ack','seq':1,
                        'crc':zlib.crc32(frame)},'acknowledged_at':now}}
            else:
                data = json.loads((self.runtime/'status.json').read_text(encoding='utf-8'))
                if not isinstance(data,dict):
                    raise ValueError('Invalid monitor state')
            label, live = mirror_state(data)
            if not data.get('running'):
                self.root.destroy()
                return
            pixels = confirmed_pixels(data)
            if pixels is not None and pixels != self.frame:
                self.frame = pixels
                self.redraw()
            if self.demo:
                label = 'DEMO · SIMULATED DATA · NO ACCOUNT OR USB CONNECTION'
            elif pixels is None:
                label, live = 'WAITING FOR FIRST CONFIRMED USB FRAME', False
            self.state.set(label)
            self.state_label.configure(fg='#74dba1' if live else '#f1bd68')
            self.pulse.live = live
            ack = (data.get('display_frame') or {}).get('ack') or {}
            seq = ack.get('seq')
            self.detail.set(('Same 1,024 bytes acknowledged by the board. Frame '+str(seq)+'. '
                if pixels is not None else 'No acknowledged framebuffer is available yet. ')+
                '1× is native resolution; larger scales preserve each pixel. '
                'Panel brightness and hardware rotation are controlled on the board.'+
                (' Layout warning: '+str(data['layout_error']) if data.get('layout_error') else ''))
        except (OSError,ValueError,TypeError,KeyError):
            self.state.set('WAITING FOR MONITOR · last confirmed frame')
            self.state_label.configure(fg='#f1bd68')
            self.pulse.live = False
        self.refresh_timer = self.root.after(200,self.refresh)


def main():
    parser = argparse.ArgumentParser(description='Quota Orb live acknowledged OLED mirror')
    parser.add_argument('--runtime',type=Path,default=ROOT/'.runtime')
    parser.add_argument('--demo',action='store_true',help='Clearly labelled synthetic preview; no account or USB')
    args = parser.parse_args()
    mutex = None
    if os.name=='nt' and not args.demo:
        import ctypes
        kernel = ctypes.WinDLL('kernel32',use_last_error=True)
        kernel.CreateMutexW.argtypes = [ctypes.c_void_p,ctypes.c_bool,ctypes.c_wchar_p]
        kernel.CreateMutexW.restype = ctypes.c_void_p
        kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        mutex = kernel.CreateMutexW(None,False,'Local\\QuotaOrbDesktop')
        if not mutex:
            raise OSError('Could not create the display window mutex')
        if ctypes.get_last_error()==183:
            args.runtime.mkdir(parents=True,exist_ok=True)
            (args.runtime/'show-display').touch()
            kernel.CloseHandle(mutex)
            return 0
    windows_app_identity()
    try:
        root = tk.Tk()
        LiveDisplay(root,args.runtime,args.demo)
        root.mainloop()
    finally:
        if mutex:
            kernel.CloseHandle(mutex)


if __name__ == '__main__':
    main()
