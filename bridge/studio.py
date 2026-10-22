"""Local drag/drop layout editor. Drafts use labelled simulated data."""
import base64
from copy import deepcopy
from pathlib import Path
import time
import tkinter as tk
from tkinter import filedialog, messagebox
import uuid

from .layout import CLASSIC, load, save, starter, validate
from .model import normalize
from .render import Canvas, png_bytes
from .widgets import Context, WIDGETS, WidgetCanvas
from .ui import MotionButton

BG, PANEL, TEXT, MUTED, ACCENT = '#0d1d23','#172e35','#e0eeee','#a9c4ca','#d7a17d'
SCALE = 6


class Studio:
    def __init__(self,parent,runtime,on_live=None):
        self.runtime = Path(runtime)
        self.root = tk.Frame(parent,bg=BG)
        self.window = parent.winfo_toplevel()
        try:
            current = load(self.runtime/'layout.json')
        except (OSError,ValueError,TypeError):
            current = CLASSIC
        self.layout = deepcopy(current) if current['mode']=='custom' else starter()
        self.selected, self.drag, self.palette_kind = None,None,None
        self.history = []
        self.image = None
        self.message = tk.StringVar(value='Drag widgets onto the canvas. Select a widget to move or resize it.')
        self.fields = {key:tk.StringVar() for key in ('x','y','width','height','text')}
        outer = tk.Frame(self.root,bg=BG,padx=22,pady=18)
        outer.pack()
        heading = tk.Frame(outer,bg=BG)
        heading.pack(fill='x')
        tk.Label(heading,text='Make it yours.',bg=BG,fg=TEXT,font=('Segoe UI',22,'bold')).pack(side='left')
        if on_live:
            MotionButton(heading,'← Live display',on_live).pack(side='right')
        tk.Label(outer,text='128 × 64 pixels  /  DRAFT WITH SIMULATED DATA  /  2 px position snapping',
                 bg=BG,fg=ACCENT,font=('Segoe UI',9,'bold')).pack(anchor='w',pady=(2,14))
        body = tk.Frame(outer,bg=BG)
        body.pack()
        palette = tk.Frame(body,bg=PANEL,padx=12,pady=12)
        palette.pack(side='left',fill='y',padx=(0,16))
        tk.Label(palette,text='WIDGETS',bg=PANEL,fg=ACCENT,font=('Segoe UI',10,'bold')).pack(anchor='w')
        tk.Label(palette,text='Drag to canvas.\nDouble-click to place.',bg=PANEL,fg=MUTED,
                 justify='left',font=('Segoe UI',8)).pack(anchor='w',pady=(2,8))
        for kind,definition in WIDGETS.items():
            item = MotionButton(palette,'+  '+definition.title,width=174,height=32)
            item.configure(cursor='fleur')
            item.pack(fill='x',pady=2)
            item.bind('<ButtonPress-1>',lambda event,key=kind:self.palette_start(key),add='+')
            item.bind('<ButtonRelease-1>',self.palette_drop,add='+')
            item.bind('<Double-Button-1>',lambda event,key=kind:self.add(key))
        right = tk.Frame(body,bg=BG)
        right.pack(side='left',anchor='n')
        self.canvas = tk.Canvas(right,width=128*SCALE,height=64*SCALE,bg='#070f13',
            highlightthickness=1,highlightbackground=ACCENT)
        self.canvas.pack()
        self.canvas.bind('<ButtonPress-1>',self.press)
        self.canvas.bind('<B1-Motion>',self.motion)
        self.canvas.bind('<ButtonRelease-1>',self.release)
        inspector = tk.Frame(right,bg=BG)
        inspector.pack(fill='x',pady=12)
        for key in ('x','y','width','height'):
            tk.Label(inspector,text=key.upper(),bg=BG,fg=MUTED,font=('Segoe UI',8)).pack(side='left',padx=(0,4))
            tk.Entry(inspector,textvariable=self.fields[key],width=4,bg=PANEL,fg=TEXT,
                     insertbackground=TEXT,relief='flat').pack(side='left',padx=(0,12),ipady=5)
        self.button(inspector,'Update size / position',self.update_fields)
        self.button(inspector,'Remove',self.remove)
        text_row = tk.Frame(right,bg=BG)
        text_row.pack(fill='x')
        tk.Label(text_row,text='TEXT WIDGET',bg=BG,fg=MUTED,font=('Segoe UI',8)).pack(side='left',padx=(0,10))
        tk.Entry(text_row,textvariable=self.fields['text'],width=32,bg=PANEL,fg=TEXT,
                 insertbackground=TEXT,relief='flat').pack(side='left',ipady=5)
        self.button(text_row,'Update text',self.update_fields)
        actions = tk.Frame(outer,bg=BG)
        actions.pack(fill='x',pady=(18,10))
        self.apply_button = self.button(actions,'Apply to OLED',self.apply,accent=True)
        self.button(actions,'Undo',self.undo)
        self.button(actions,'Starter layout',self.reset)
        self.button(actions,'Import JSON',self.import_layout)
        self.button(actions,'Export JSON',self.export_layout)
        self.button(actions,'Use classic display',self.classic)
        self.message_label = tk.Label(outer,textvariable=self.message,bg=BG,fg=MUTED,
            font=('Segoe UI',9),justify='left',wraplength=980)
        self.message_label.pack(anchor='w')
        tk.Label(outer,text='Draft changes stay here until Apply. Export contains layout geometry/text only. '
            'The live mirror shows only frames acknowledged by the board.',bg=BG,fg=MUTED,
            font=('Segoe UI',8),wraplength=980,justify='left').pack(anchor='w',pady=(8,0))
        self.window.bind('<Delete>',lambda event:self.remove()
            if self.root.winfo_ismapped() and not isinstance(event.widget,tk.Entry) else None,add='+')
        self.window.bind('<Control-z>',lambda event:self.undo() if self.root.winfo_ismapped() else None,add='+')
        self.refresh()

    def button(self,parent,text,command,accent=False):
        button = MotionButton(parent,text,command,accent=accent)
        button.pack(side='left',padx=(0,7))
        return button

    def remember(self):
        self.history.append(deepcopy(self.layout))
        self.history = self.history[-50:]

    def item(self):
        return next((item for item in self.layout['widgets'] if item['id']==self.selected),None)

    def select(self,identifier):
        self.selected = identifier
        item = self.item()
        for key,var in self.fields.items():
            var.set(str(item.get(key,'')) if item and key!='text' else
                    item['options'].get('text','QUOTA ORB') if item and item['kind']=='text' else '')

    def palette_start(self,kind):
        self.palette_kind = kind

    def palette_drop(self,event):
        if not self.palette_kind:
            return
        x,y = (event.x_root-self.canvas.winfo_rootx())//SCALE,(event.y_root-self.canvas.winfo_rooty())//SCALE
        kind,self.palette_kind = self.palette_kind,None
        if 0<=x<128 and 0<=y<64:
            self.add(kind,x,y)

    def add(self,kind,x=None,y=None):
        definition = WIDGETS[kind]
        if len(self.layout['widgets'])>=24:
            self.message.set('Maximum 24 widgets. Remove an existing widget first.')
            return
        if kind=='status' and any(i['kind']=='status' for i in self.layout['widgets']):
            self.message.set('A Source status widget already exists. Keep exactly one.')
            return
        if x is None:
            positions = [(px,py) for py in range(0,65-definition.height,2)
                         for px in range(0,129-definition.width,2)]
            x,y = next(((px,py) for px,py in positions if all(
                px+definition.width<=i['x'] or i['x']+i['width']<=px or
                py+definition.height<=i['y'] or i['y']+i['height']<=py for i in self.layout['widgets'])),(0,0))
        self.remember()
        item = {'id':uuid.uuid4().hex[:12],'kind':kind,'x':max(0,min(128-definition.width,x//2*2)),
            'y':max(0,min(64-definition.height,y//2*2)),'width':definition.width,
            'height':definition.height,'options':{}}
        self.layout['widgets'].append(item)
        self.select(item['id'])
        self.refresh()

    def press(self,event):
        x,y = event.x//SCALE,event.y//SCALE
        found = next((item for item in reversed(self.layout['widgets']) if
            item['x']<=x<item['x']+item['width'] and item['y']<=y<item['y']+item['height']),None)
        self.select(found['id'] if found else None)
        self.drag = (x-found['x'],y-found['y']) if found else None
        if found:
            self.remember()
        self.refresh()

    def motion(self,event):
        item = self.item()
        if item and self.drag:
            item['x'] = max(0,min(128-item['width'],event.x//SCALE-self.drag[0]))
            item['y'] = max(0,min(64-item['height'],event.y//SCALE-self.drag[1]))
            self.select(item['id'])
            self.refresh()

    def release(self,event):
        item = self.item()
        if item and self.drag:
            item['x'] = item['x']//2*2
            item['y'] = item['y']//2*2
            self.select(item['id'])
            self.refresh()
        self.drag = None

    def update_fields(self):
        item = self.item()
        if not item:
            self.message.set('Select a widget first.')
            return
        candidate = deepcopy(item)
        try:
            for key in ('x','y','width','height'):
                candidate[key] = int(self.fields[key].get())
            definition = WIDGETS[item['kind']]
            if (candidate['x']<0 or candidate['y']<0 or candidate['width']<definition.min_width or
                candidate['height']<definition.min_height or candidate['x']+candidate['width']>128 or
                    candidate['y']+candidate['height']>64):
                raise ValueError('Dimensions must fit the canvas and widget minimum')
            if definition.text_option:
                candidate['options'] = {'text':self.fields['text'].get().upper()}
            self.remember()
            item.update(candidate)
            self.refresh()
        except ValueError:
            self.message.set('Use integer coordinates/sizes within 128×64 and the widget minimum. Text must use the OLED alphabet.')

    def remove(self):
        item = self.item()
        if item:
            self.remember()
            self.layout['widgets'].remove(item)
            self.select(None)
            self.refresh()

    def undo(self):
        if self.history:
            self.layout = self.history.pop()
            self.select(None)
            self.refresh()

    def reset(self):
        self.remember()
        self.layout = starter()
        self.select(None)
        self.refresh()

    def refresh(self):
        try:
            validate(self.layout)
            self.apply_button.configure(state='normal')
            self.message.set('Valid draft. Apply to OLED when ready; the live mirror will confirm the actual received frame.')
            self.message_label.configure(fg=MUTED)
        except (ValueError,TypeError) as exc:
            self.apply_button.configure(state='disabled')
            self.message.set(str(exc))
            self.message_label.configure(fg='#f1bd68')
        now = time.time()
        sample = normalize({'rateLimits':{'limitId':'codex','primary':{
            'usedPercent':28,'windowDurationMins':10080,'resetsAt':int(now)+311040}}},now=now)
        context = Context(sample,now)
        target = Canvas()
        for item in self.layout['widgets']:
            bounds = tuple(item[key] for key in ('x','y','width','height'))
            WIDGETS[item['kind']].draw(WidgetCanvas(target,bounds),context,item['options'])
        self.image = tk.PhotoImage(data=base64.b64encode(png_bytes(bytes(target.data),SCALE)))
        self.canvas.delete('all')
        self.canvas.create_image(0,0,anchor='nw',image=self.image)
        for item in self.layout['widgets']:
            x,y,w,h = (item[key]*SCALE for key in ('x','y','width','height'))
            self.canvas.create_rectangle(x,y,x+w,y+h,outline=ACCENT if item['id']==self.selected else '#29464e',
                                         width=2 if item['id']==self.selected else 1,dash=() if item['id']==self.selected else (3,3))

    def apply(self):
        try:
            save(self.runtime/'layout.json',self.layout)
            self.message.set('Applied locally. A running monitor sends the layout on its next frame; resume if paused. Check the live mirror for confirmation.')
        except (OSError,ValueError,TypeError) as exc:
            messagebox.showerror('Layout was not applied',str(exc),parent=self.root)

    def classic(self):
        try:
            save(self.runtime/'layout.json',CLASSIC)
            self.message.set('Classic display selected. Your draft remains open; Apply to switch back to it.')
        except OSError:
            messagebox.showerror('Could not save display mode','Check write access to the project runtime folder.',parent=self.root)

    def import_layout(self):
        path = filedialog.askopenfilename(parent=self.root,title='Import a data-only Quota Orb layout',
            initialdir=Path(__file__).resolve().parents[1]/'layouts',filetypes=[('Layout JSON','*.json')])
        if path:
            try:
                candidate = load(path)
                self.remember()
                self.layout = starter() if candidate['mode']=='classic' else candidate
                self.select(None)
                self.refresh()
            except (OSError,ValueError,TypeError):
                messagebox.showerror('Import refused','The layout is invalid, unsupported, overlapping, or exceeds 16 KiB. No code was loaded and the active layout was preserved.',parent=self.root)

    def export_layout(self):
        try:
            validate(self.layout)
        except (ValueError,TypeError):
            self.message.set('Fix the draft before exporting it.')
            return
        path = filedialog.asksaveasfilename(parent=self.root,title='Export layout geometry and text',
            defaultextension='.json',initialfile='quota-orb-layout.json',filetypes=[('Layout JSON','*.json')])
        if path:
            try:
                save(path,self.layout)
                self.message.set('Exported geometry and custom text only. Review text you entered before sharing this file.')
            except OSError:
                messagebox.showerror('Export failed','Could not write the selected file.',parent=self.root)
