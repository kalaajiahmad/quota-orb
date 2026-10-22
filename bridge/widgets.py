"""Reviewed widget registry. Layout JSON selects these IDs; it never loads code."""
from dataclasses import dataclass
from .model import countdown, freshness
from .render import Canvas


@dataclass(frozen=True)
class Context:
    snapshot: object
    now: float
    page: int = 0
    error: bool = False
    stale_seconds: float = 150
    provider: str = 'codex'

    @property
    def window(self):
        return self.snapshot.windows[self.page % len(self.snapshot.windows)] if self.snapshot else None

    @property
    def source(self):
        state = freshness(self.snapshot,self.now,self.error,self.stale_seconds)
        if self.window and state == 'LIVE':
            if self.window.blocked:
                return 'BLOCKED'
            if self.window.resets_at is not None and self.window.resets_at <= self.now:
                return 'CHECK'
        return state


class WidgetCanvas(Canvas):
    """Local pixel coordinates clipped to the widget's validated rectangle."""
    def __init__(self, target, bounds):
        self.target = target
        self.x, self.y, self.width, self.height = bounds

    def pixel(self, x, y, on=True):
        if 0 <= x < self.width and 0 <= y < self.height:
            self.target.pixel(self.x+x,self.y+y,on)


@dataclass(frozen=True)
class Widget:
    title: str
    width: int
    height: int
    min_width: int
    min_height: int
    draw: object
    text_option: bool = False


def remaining(c, context, options):
    text = str(int(context.window.remaining))+'%' if context.window else '--%'
    scale = min(3,max(1,c.height//7),max(1,c.width//(len(text)*6)))
    c.text(0,0,text,scale)


def progress(c, context, options):
    c.rect(0,0,c.width,c.height,False)
    if context.window:
        width = int((c.width-4)*context.window.remaining/100)
        if width:
            c.rect(2,2,width,max(1,c.height-4))


def window_label(c, context, options):
    window = context.window
    label = 'WAITING FOR DATA' if not window else window.label
    if window and window.bucket not in ('codex','claude'):
        label = window.bucket+' '+label
    c.text(0,0,label)


def age(c, context, options):
    seconds = max(0,int(context.now-context.snapshot.fetched_at)) if context.snapshot else None
    c.text(0,0,'--' if seconds is None else str(seconds)+'S' if seconds<1000 else str(min(999,seconds//60))+'M')


WIDGETS = {
    'provider':Widget('Provider',60,8,18,7,lambda c,x,o:c.text(0,0,x.provider)),
    'status':Widget('Source status',48,8,42,7,lambda c,x,o:c.text(0,0,x.source)),
    'window':Widget('Quota window',100,8,36,7,window_label),
    'remaining':Widget('Remaining %',90,23,30,7,remaining),
    'progress':Widget('Allowance bar',128,5,8,3,progress),
    'reset':Widget('Reset countdown',96,7,36,7,
        lambda c,x,o:c.text(0,0,countdown(x.window.resets_at,x.now) if x.window else 'RESET UNKNOWN')),
    'age':Widget('Reading age',24,7,18,7,age),
    'robot':Widget('Animated companion',28,24,28,21,
        lambda c,x,o:c.robot(0,0,int(x.now),x.source not in ('LIVE','CHECK'))),
    'text':Widget('Custom text',72,8,6,7,lambda c,x,o:c.text(0,0,o.get('text','QUOTA ORB')),True),
    'line':Widget('Separator',128,1,2,1,lambda c,x,o:c.rect(0,0,c.width,c.height)),
}
