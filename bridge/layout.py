"""Versioned, bounded, data-only dashboard layouts and shared OLED rendering."""
from copy import deepcopy
import json
from pathlib import Path
import re

from .render import Canvas, GLYPHS
from .widgets import WIDGETS, WidgetCanvas

MAX_BYTES = 16384
CLASSIC = {'version':1,'mode':'classic','widgets':[]}


def starter():
    positions = [('provider',0,0),('status',80,0),('line',0,10),('window',0,14),
        ('remaining',0,25),('robot',100,24),('progress',0,49),('reset',0,57),('age',104,57)]
    return {'version':1,'mode':'custom','widgets':[
        {'id':kind,'kind':kind,'x':x,'y':y,'width':WIDGETS[kind].width,
         'height':WIDGETS[kind].height,'options':{}} for kind,x,y in positions]}


def validate(value):
    if (not isinstance(value,dict) or set(value)!={'version','mode','widgets'} or
            type(value['version']) is not int or value['version']!=1 or
            value['mode'] not in ('classic','custom') or not isinstance(value['widgets'],list)):
        raise ValueError('Expected a version 1 Quota Orb layout')
    if len(value['widgets'])>24 or value['mode']=='classic' and value['widgets']:
        raise ValueError('A layout supports at most 24 widgets; classic has none')
    ids, rectangles = set(), []
    status_count = 0
    for item in value['widgets']:
        if not isinstance(item,dict) or set(item)!={'id','kind','x','y','width','height','options'}:
            raise ValueError('Unknown or missing widget fields')
        identifier,kind = item['id'],item['kind']
        if (not isinstance(identifier,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,48}',identifier)
                or identifier in ids or not isinstance(kind,str) or kind not in WIDGETS):
            raise ValueError('Unknown widget type or invalid/duplicate widget ID')
        ids.add(identifier)
        definition = WIDGETS[kind]
        x,y,w,h = [item[key] for key in ('x','y','width','height')]
        if (any(type(n) is not int for n in (x,y,w,h)) or x<0 or y<0 or
                w<definition.min_width or h<definition.min_height or x+w>128 or y+h>64):
            raise ValueError('Widget size or position exceeds the 128x64 canvas')
        options = item['options']
        if not isinstance(options,dict) or set(options)-({'text'} if definition.text_option else set()):
            raise ValueError('Unsupported widget options')
        if 'text' in options and (not isinstance(options['text'],str) or len(options['text'])>40 or
                any(char not in GLYPHS for char in options['text'].upper())):
            raise ValueError('Text supports up to 40 characters from the OLED alphabet')
        for px,py,pw,ph in rectangles:
            if x<px+pw and px<x+w and y<py+ph and py<y+h:
                raise ValueError('Widgets overlap; move or resize them before applying')
        rectangles.append((x,y,w,h))
        status_count += kind=='status'
    if value['mode']=='custom' and status_count!=1:
        raise ValueError('Keep exactly one Source status widget so stale data remains visible')
    return deepcopy(value)


def load(path):
    path = Path(path)
    with path.open('rb') as stream:
        raw = stream.read(MAX_BYTES+1)
    if len(raw)>MAX_BYTES:
        raise ValueError('Layout file exceeds 16 KiB')
    try:
        return validate(json.loads(raw))
    except (UnicodeError,RecursionError) as exc:
        raise ValueError('Invalid layout JSON') from exc


def save(path, value):
    data = json.dumps(validate(value),indent=2)+'\n'
    if len(data.encode('utf-8'))>MAX_BYTES:
        raise ValueError('Layout file exceeds 16 KiB')
    path = Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(data,encoding='utf-8')
    temporary.replace(path)


def render_layout(value, context):
    value = validate(value)
    canvas = Canvas()
    for item in value['widgets']:
        bounds = tuple(item[key] for key in ('x','y','width','height'))
        WIDGETS[item['kind']].draw(WidgetCanvas(canvas,bounds),context,item['options'])
    return bytes(canvas.data)


class LayoutStore:
    def __init__(self,path):
        self.path = Path(path)
        self.value = deepcopy(CLASSIC)
        self.error = None

    def read(self):
        try:
            # The bounded 16 KiB file is read at 1 Hz. Timestamp-only caches miss
            # rapid saves on filesystems/clocks with coarse timestamp resolution.
            self.value = load(self.path)
            self.error = None
        except FileNotFoundError:
            self.value, self.error = deepcopy(CLASSIC),None
        except (OSError,ValueError,TypeError):
            self.error = 'Invalid layout; retaining the last valid layout (classic on first launch)'
        return self.value
