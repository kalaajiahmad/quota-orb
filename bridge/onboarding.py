"""Local desktop onboarding. No web server, credential fields, or remote backend."""
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox
import webbrowser

from .codex import CodexClient
from .claude import ClaudeFileClient, configure_statusline
from .model import normalize, SourceError, freshness
from .providers import (ROOT,PROVIDERS,executable,launch_login,preferences,
                        save_preferences,start_monitor)
from .usb import Display

BG, PANEL, TEXT, MUTED, ACCENT = '#0d1d23','#172e35','#e0eeee','#a9c4ca','#d7a17d'

class Wizard:
    def __init__(self,root):
        self.root = root
        self.root.title('Quota Orb | Connect your desk companion')
        self.root.geometry('880x860')
        self.root.minsize(820,720)
        self.root.configure(bg=BG)
        self.events = queue.Queue()
        self.busy = False
        self.verified = None
        self.checked_port = None
        self.login = None
        self.flash = None
        saved = preferences()
        self.provider = tk.StringVar(value=saved['provider'])
        self.port = tk.StringVar(value=saved['port'] or '')
        self.note = tk.StringVar(value='Choose a provider, then check the connection. No sign-in is needed for the demo.')
        self.account_note = tk.StringVar(value='Not checked')
        self.usb_note = tk.StringVar(value='Not checked')
        self.run_note = tk.StringVar(value='Monitor is stopped')
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('TFrame',background=BG)
        style.configure('TLabel',background=BG,foreground=TEXT,font=('Segoe UI',10))
        style.configure('Muted.TLabel',foreground=MUTED)
        style.configure('Title.TLabel',font=('Segoe UI',28,'bold'),foreground=TEXT)
        style.configure('Section.TLabel',font=('Segoe UI',12,'bold'),foreground=ACCENT)
        style.configure('TButton',font=('Segoe UI',10),padding=(12,8),background=PANEL,foreground=TEXT)
        style.map('TButton',background=[('active','#29464e')])
        style.configure('TRadiobutton',background=BG,foreground=TEXT,font=('Segoe UI',10))
        canvas = tk.Canvas(root,bg=BG,highlightthickness=0)
        scroll = ttk.Scrollbar(root,orient='vertical',command=canvas.yview)
        scroll.pack(side='right',fill='y')
        canvas.pack(side='left',fill='both',expand=True)
        canvas.configure(yscrollcommand=scroll.set)
        frame = ttk.Frame(canvas,padding=28)
        pane = canvas.create_window((0,0),window=frame,anchor='nw')
        frame.bind('<Configure>',lambda _:canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>',lambda event:canvas.itemconfigure(pane,width=event.width))
        root.bind('<MouseWheel>',lambda event:canvas.yview_scroll(-int(event.delta/120),'units'))
        ttk.Label(frame,text='Quota Orb.',style='Title.TLabel').pack(anchor='w')
        ttk.Label(frame,text='Connect once. Keep your allowance in view.',style='Muted.TLabel').pack(anchor='w',pady=(0,14))
        self.section(frame,'1  /  Choose your provider')
        for key,definition in PROVIDERS.items():
            ttk.Radiobutton(frame,text=definition['name']+'   —   '+definition['status'],value=key,
                            variable=self.provider,command=self.changed_provider).pack(anchor='w',pady=3)
        row = ttk.Frame(frame)
        row.pack(fill='x',pady=(8,12))
        self.button(row,'Install provider CLI',self.install)
        self.button(row,'Preview demo',self.demo)
        self.section(frame,'2  /  Connect your account')
        ttk.Label(frame,text='Sign-in takes place in the provider’s browser flow and official CLI.',style='Muted.TLabel').pack(anchor='w')
        row = ttk.Frame(frame)
        row.pack(fill='x',pady=8)
        self.button(row,'Check connection',self.check_account)
        self.button(row,'Sign in with provider',self.sign_in)
        self.button(row,'Enable Claude events',self.claude_enable)
        self.button(row,'Remove Claude link',self.claude_remove)
        ttk.Label(frame,textvariable=self.account_note,wraplength=730).pack(anchor='w',pady=(0,12))
        self.section(frame,'3  /  Connect the Heltec by USB')
        row = ttk.Frame(frame)
        row.pack(fill='x',pady=8)
        self.ports = ttk.Combobox(row,textvariable=self.port,state='readonly',width=12)
        self.ports.pack(side='left',padx=(0,8))
        self.button(row,'Find board',self.scan_ports)
        self.button(row,'Check USB',self.check_usb)
        self.button(row,'Install V2 firmware',self.install_firmware)
        ttk.Label(frame,textvariable=self.usb_note,wraplength=730).pack(anchor='w',pady=(0,12))
        self.section(frame,'4  /  Start your monitor')
        row = ttk.Frame(frame)
        row.pack(fill='x',pady=8)
        self.button(row,'Start monitor',self.start)
        self.button(row,'Stop monitor',self.stop)
        self.button(row,'Setup guide',lambda:webbrowser.open((ROOT/'docs/SETUP.md').as_uri()))
        ttk.Label(frame,textvariable=self.run_note,wraplength=730).pack(anchor='w',pady=(0,10))
        ttk.Separator(frame).pack(fill='x',pady=10)
        ttk.Label(frame,textvariable=self.note,wraplength=730,style='Muted.TLabel').pack(anchor='w')
        ttk.Label(frame,text='No passwords, tokens, cookies, or API keys are entered here.\nClosing this window leaves a started monitor running. Startup at login is optional.',
                  wraplength=730,style='Muted.TLabel').pack(anchor='w',pady=(12,0))
        self.root.protocol('WM_DELETE_WINDOW',self.close)
        self.scan_ports()
        self.root.after(100,self.drain)
        self.root.after(1000,self.monitor_status)

    def section(self,parent,title):
        ttk.Label(parent,text=title,style='Section.TLabel').pack(anchor='w',pady=(4,5))

    def button(self,parent,text,command):
        ttk.Button(parent,text=text,command=command).pack(side='left',padx=(0,8))

    def changed_provider(self):
        self.verified = None
        self.account_note.set('Provider changed. Check the connection before starting.')
        if self.provider.get() == 'gemini':
            self.note.set('Gemini is not connectable in this release: a read-only account-quota adapter has not been verified. No login or model request will be started.')
        elif self.provider.get() == 'claude':
            self.note.set('Claude is experimental and event-driven. Enable its local status line, use Claude Code normally, then check. No model request is sent by Quota Orb.')
        else:
            self.note.set('Already signed into Codex CLI? Check connection. Otherwise use Sign in with provider. A ChatGPT browser session alone is not a CLI connection.')

    def work(self,function,success):
        if self.busy:
            self.note.set('A check is already running. Wait for it to finish.')
            return
        self.busy = True
        self.note.set('Working locally…')
        def run():
            try:
                self.events.put((success,function(),None))
            except SourceError as exc:
                self.events.put((None,None,str(exc)))
            except Exception:
                self.events.put((None,None,'The local operation failed. Check installation and connection, then retry. No authentication output was saved.'))
        threading.Thread(target=run,daemon=True).start()

    def drain(self):
        try:
            while True:
                callback,value,error = self.events.get_nowait()
                self.busy = False
                if error:
                    self.verified = None
                    self.note.set(error)
                    self.account_note.set('Not verified. See the message below.')
                else:
                    callback(value)
        except queue.Empty:
            pass
        self.root.after(100,self.drain)

    def install(self):
        webbrowser.open(PROVIDERS[self.provider.get()]['install'])

    def demo(self):
        preview = tk.Toplevel(self.root)
        preview.title('Quota Orb | Simulated output — no account connection')
        picture = tk.PhotoImage(file=str(ROOT/'artifacts/demo.png'))
        label = ttk.Label(preview,image=picture)
        label.image = picture
        label.pack(padx=20,pady=20)
        ttk.Label(preview,text='Simulated usage. Actual values depend on the linked provider.').pack(padx=20,pady=(0,20))

    def check_account(self):
        provider = self.provider.get()
        if provider == 'gemini':
            self.changed_provider()
            return
        self.verified = None
        def check():
            if provider == 'codex':
                with CodexClient() as client:
                    snapshot = normalize(client.read_limits())
            else:
                client = ClaudeFileClient()
                snapshot = normalize(client.read_limits(),now=client.observed_at)
                if freshness(snapshot,time.time()) == 'STALE':
                    raise SourceError('Claude event data is stale. Use Claude Code normally, then check again.')
            return len(snapshot.windows)
        def done(windows):
            if self.provider.get() != provider:
                return
            self.verified = provider
            self.account_note.set(PROVIDERS[provider]['name']+f': quota access verified ({windows} reported window(s)).')
            self.note.set('Quota fields are valid. Account names and identifiers were not requested or saved by this wizard.')
        self.work(check,done)

    def sign_in(self):
        provider = self.provider.get()
        if provider == 'gemini':
            self.changed_provider()
            return
        if self.login and self.login.poll() is None:
            self.note.set('Complete the provider sign-in already open in its browser/console.')
            return
        try:
            self.login = launch_login(provider,executable(provider))
            self.verified = None
            self.note.set('Complete sign-in in the official provider window, then click Check connection. Quota Orb does not capture its output or credentials.')
        except (SourceError,OSError) as exc:
            self.note.set(str(exc) if isinstance(exc,SourceError) else 'Could not start the installed provider CLI. Use the installation link and retry.')

    def claude_enable(self):
        if self.provider.get() != 'claude':
            self.note.set('Choose Claude Code to configure its local event connection.')
            return
        if messagebox.askyesno('Enable Claude events?',
            'Add Quota Orb as your Claude Code status line?\n\nThis changes only the statusLine setting. An existing different status line will be preserved and installation refused. The adapter reads quota fields from event input and discards session/path fields. No credentials are read. Managed policies may prevent it running.'):
            self.work(configure_statusline,lambda _:self.note.set('Claude link installed. Use an eligible Claude Code session normally, then click Check connection. The adapter never starts a model turn.'))

    def claude_remove(self):
        if messagebox.askyesno('Remove Claude link?', 'Remove only the status line installed by this copy of Quota Orb? This does not sign out of Claude. Other settings are preserved.'):
            self.work(lambda:configure_statusline(remove=True),lambda _:self.note.set('Claude link removed. Stop the monitor if it is still running. Local cached usage remains private under .runtime/.'))

    def scan_ports(self):
        from serial.tools import list_ports
        found = [p.device for p in list_ports.comports() if p.vid==0x10C4 and p.pid==0xEA60]
        self.ports['values'] = found
        if self.port.get() not in found:
            self.port.set(found[0] if len(found)==1 else '')
        self.checked_port = None
        self.usb_note.set('Select the Heltec and check USB.' if found else 'No CP210x board detected. Connect a data cable, install its driver if needed, then find again.')

    def check_usb(self):
        port = self.port.get()
        if not port:
            self.note.set('Find the board and choose its port first.')
            return
        self.checked_port = None
        def check():
            display = Display(port)
            try:
                return display.connect()
            finally:
                display.close()
        def done(_):
            if self.port.get() == port:
                self.checked_port = port
                self.usb_note.set('USB firmware handshake and OLED acknowledgement verified.')
                self.note.set('Ready to start after quota access is verified. USB checks require the monitor to be stopped.')
        self.work(check,done)

    def install_firmware(self):
        port = self.port.get()
        if not port:
            self.note.set('Select the physical board first.')
            return
        if self.flash and self.flash.poll() is None:
            self.note.set('Firmware installation is already running in its console.')
            return
        if not messagebox.askyesno('Replace board firmware?',
            'Confirm this is a Heltec WiFi Kit 32 V2 with an 8 MB classic ESP32.\n\nThe installer stops this monitor, installs the pinned build tools, verifies 8 MB flash, and saves a full private backup before replacing firmware. A USB disconnect can interrupt upload. Never share that backup. Continue?'):
            return
        command = ['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(ROOT/'scripts/Flash-Board.ps1'),'-Port',port]
        self.flash = subprocess.Popen(command,cwd=ROOT,creationflags=subprocess.CREATE_NEW_CONSOLE)
        self.checked_port = None
        self.note.set('Follow the firmware console. When complete, return and check USB. Nothing starts automatically afterward.')

    def start(self):
        provider,port = self.provider.get(),self.port.get()
        try:
            running = json.loads((ROOT/'.runtime/status.json').read_text(encoding='utf-8'))
            if running.get('running') and time.time()-running.get('updated_at',0)<8:
                self.note.set('A monitor is already running. Stop it before starting again or changing provider/board.')
                return
        except (OSError,ValueError,TypeError):
            pass
        if self.verified != provider or self.checked_port != port or not port:
            self.note.set('Verify quota access and USB for the selected provider and board before starting.')
            return
        def run():
            save_preferences(provider,port)
            start_monitor(provider,port)
        self.work(run,lambda _:self.note.set('Monitor launched. Wait for an acknowledged frame below. Closing this wizard leaves it running.'))

    def stop(self):
        command = ['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(ROOT/'scripts/Stop.ps1')]
        self.work(lambda:subprocess.run(command,cwd=ROOT,check=True,creationflags=subprocess.CREATE_NO_WINDOW),
                  lambda _:self.note.set('Monitor stopped. The board shows USB OFFLINE within six seconds. Provider sign-in is unchanged.'))

    def monitor_status(self):
        try:
            data = json.loads((ROOT/'.runtime/status.json').read_text(encoding='utf-8'))
            active = data.get('running') and time.time()-data.get('updated_at',0)<8
            if active:
                self.run_note.set(f"Running {data.get('provider','')} | source {data.get('source','unknown')} | USB {'connected' if data.get('usb_connected') else 'waiting'} | acknowledged frames {data.get('frames_acknowledged',0)}")
            else:
                self.run_note.set('Monitor is stopped')
        except (OSError,ValueError,TypeError):
            self.run_note.set('Monitor is stopped')
        self.root.after(1000,self.monitor_status)

    def close(self):
        if self.busy:
            self.note.set('Wait for the local check to finish before closing.')
            return
        self.root.destroy()

def main():
    if os.name != 'nt':
        raise SystemExit('The guided desktop setup currently supports Windows. See docs/SETUP.md.')
    root = tk.Tk()
    Wizard(root)
    root.mainloop()

if __name__ == '__main__':
    main()
