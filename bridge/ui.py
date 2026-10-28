"""Small native Tk visual system: rounded controls and non-blocking motion."""
import time
import tkinter as tk
from tkinter import font
import os

BG, PANEL, TEXT, MUTED, ACCENT = '#0d1d23','#172e35','#e0eeee','#a9c4ca','#d7a17d'
APP_ID = 'QuotaOrb.Desktop'


def windows_app_identity():
    """Set before creating windows so Windows does not group them as Python."""
    if os.name=='nt':
        import ctypes
        shell = ctypes.WinDLL('shell32',use_last_error=True)
        function = shell.SetCurrentProcessExplicitAppUserModelID
        function.argtypes,function.restype = [ctypes.c_wchar_p],ctypes.c_long
        if function(APP_ID)!=0:
            raise OSError('Windows could not set the Quota Orb application identity')


def window_icon(root):
    if os.name != 'nt':
        # Tk's iconbitmap expects XBM on Unix, not the bundled Windows ICO.
        return
    from pathlib import Path
    path = Path(__file__).resolve().parents[1]/'assets/tray-live.ico'
    root.iconbitmap(default=str(path))
    root.iconbitmap(str(path))


def motion_enabled():
    if os.name == 'nt':
        import ctypes
        enabled = ctypes.c_int(1)
        if ctypes.windll.user32.SystemParametersInfoW(0x1042,0,ctypes.byref(enabled),0):
            return bool(enabled.value)
    return True


def mix(first, second, fraction):
    a,b = [tuple(int(color[i:i+2],16) for i in (1,3,5)) for color in (first,second)]
    return '#'+''.join(f'{round(x+(y-x)*fraction):02x}' for x,y in zip(a,b))


def rounded(canvas, x, y, w, h, radius=10, **options):
    radius = min(radius,w/2,h/2)
    return canvas.create_polygon(x+radius,y,x+w-radius,y,x+w,y,x+w,y+radius,
        x+w,y+h-radius,x+w,y+h,x+w-radius,y+h,
        x+radius,y+h,x,y+h,x,y+h-radius,x,y+radius,x,y,
        smooth=True,splinesteps=24,**options)


class MotionButton(tk.Canvas):
    def __init__(self,parent,text,command=None,accent=False,width=None,height=36,**kwargs):
        self.typeface = font.Font(family='Segoe UI',size=10,weight='bold' if accent else 'normal')
        width = width or self.typeface.measure(text)+28
        try:
            background = parent.cget('background')
        except tk.TclError:
            background = BG
        super().__init__(parent,width=width,height=height,bg=background,
            highlightthickness=0,borderwidth=0,takefocus=1,cursor='hand2',**kwargs)
        self.text,self.command,self.accent = text,command,accent
        self.disabled,self.hover,self.pressed,self.focused = False,False,False,False
        self.progress,self.target,self.timer = 0.0,0.0,None
        self.motion = motion_enabled()
        self.bind('<Enter>',lambda event:self.hover_to(True))
        self.bind('<Leave>',lambda event:self.hover_to(False))
        self.bind('<ButtonPress-1>',self.press)
        self.bind('<ButtonRelease-1>',self.release)
        self.bind('<Return>',lambda event:self.invoke())
        self.bind('<space>',lambda event:self.invoke())
        self.bind('<FocusIn>',lambda event:self.focus(True))
        self.bind('<FocusOut>',lambda event:self.focus(False))
        self.bind('<Destroy>',self.destroyed)
        self.bind('<Configure>',lambda event:self.paint())
        self.paint()

    def configure(self,cnf=None,**kwargs):
        if isinstance(cnf,dict):
            kwargs = dict(cnf,**kwargs)
        if 'state' in kwargs:
            self.disabled = kwargs.pop('state')=='disabled'
        if 'text' in kwargs:
            self.text = kwargs.pop('text')
        if 'accent' in kwargs:
            self.accent = kwargs.pop('accent')
        result = super().configure(**kwargs) if kwargs else None
        self.paint()
        return result

    config = configure

    def hover_to(self,value):
        self.hover,self.target = value,float(value)
        if not self.motion:
            self.progress = self.target
            self.paint()
            return
        if not self.timer:
            self.animate()

    def animate(self):
        self.timer = None
        self.progress += (self.target-self.progress)*0.24
        if abs(self.target-self.progress)<0.01:
            self.progress = self.target
        self.paint()
        if self.progress!=self.target:
            self.timer = self.after(16,self.animate)

    def paint(self):
        self.delete('all')
        width,height = int(self.cget('width')),int(self.cget('height'))
        base,highlight = (ACCENT,'#edc6aa') if self.accent else (PANEL,'#2c4a53')
        fill = '#14282e' if self.disabled else mix(base,highlight,self.progress)
        inset = 2 if self.pressed else 0
        rounded(self,inset,inset,width-2*inset,height-2*inset,10,fill=fill,
                outline='#edc6aa' if self.focused else fill,width=1)
        self.create_text(width/2,height/2+(1 if self.pressed else 0),text=self.text,
            fill='#617b83' if self.disabled else BG if self.accent else TEXT,font=self.typeface)

    def focus(self,value):
        self.focused = value
        self.paint()

    def press(self,event):
        if not self.disabled:
            self.focus_set()
            self.pressed = True
            self.paint()

    def release(self,event):
        pressed,self.pressed = self.pressed,False
        self.paint()
        if pressed and 0<=event.x<int(self.cget('width')) and 0<=event.y<int(self.cget('height')):
            self.invoke()

    def invoke(self):
        if not self.disabled and self.command:
            self.command()

    def destroyed(self,event):
        if self.timer:
            self.after_cancel(self.timer)
            self.timer = None


class StatusPulse(tk.Canvas):
    """Low-key pulse while frames are confirmed; a steady dot when waiting."""
    def __init__(self,parent):
        super().__init__(parent,width=16,height=16,bg=BG,highlightthickness=0)
        self.live = False
        self.motion = motion_enabled()
        self.start = time.monotonic()
        self.timer = None
        self.bind('<Destroy>',self.destroyed)
        self.animate()

    def animate(self):
        import math
        self.delete('all')
        wave = (math.sin((time.monotonic()-self.start)*2.5)+1)/2 if self.motion else 0
        color = '#74dba1' if self.live else '#f1bd68'
        self.create_oval(1,1,15,15,fill=mix(BG,color,0.12+wave*0.14 if self.live else 0.12),outline='')
        self.create_oval(5,5,11,11,fill=color,outline='')
        self.timer = self.after(33 if self.live and self.motion else 250,self.animate)

    def destroyed(self,event):
        if self.timer:
            self.after_cancel(self.timer)
