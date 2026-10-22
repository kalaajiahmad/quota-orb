# Community widgets and layouts

Quota Orb has one 128×64 framebuffer renderer for USB and the desktop mirror. Widgets compose that frame; the live view displays the bytes acknowledged by the board. A layout is versioned JSON data, not a plugin installer.

## Share a layout

Use **Edit layout → Export JSON**. Export contains geometry, widget IDs/options, and custom text only. Review text you entered before publishing it. Submit portable examples under `layouts/` with a synthetic render and a descriptive PR. Never include `.runtime/`, live screenshots, provider payloads, or machine paths. Importing a layout opens a draft; Apply remains an explicit action.

Version 1 accepts exactly `version`, `mode`, and `widgets`. Custom layouts hold at most 24 widgets and require exactly one Source status widget. Rectangles must fit within 128×64 without overlap. Widget IDs must be unique. Each widget permits only its documented options. Files are limited to 16 KiB. Unknown versions/types/fields are rejected. Invalid runtime edits preserve the last valid layout; the first-launch fallback is classic.

## Add a widget

Implement a small deterministic drawing function and register it explicitly in `bridge/widgets.py`:

```python
def example(canvas, context, options):
    window = context.window
    text = 'WAITING' if window is None else str(int(window.remaining)) + '%'
    canvas.text(0, 0, text)

# Add an entry to WIDGETS with a stable, descriptive ID:
# 'example': Widget('Example', 48, 8, 30, 7, example),
```

`Widget(title, width, height, min_width, min_height, draw, text_option=False)` defines palette dimensions and minimum size. `draw(canvas, context, options)` receives:

| Value | Contract |
|---|---|
| `canvas.width`, `.height` | Validated local widget dimensions |
| `canvas.pixel(x, y, on=True)` | One clipped monochrome pixel |
| `canvas.rect(x, y, width, height, fill=True)` | Filled or outlined rectangle |
| `canvas.text(x, y, text, scale=1)` | Original 5×7 bitmap alphabet; clipped to bounds |
| `canvas.robot(x, y, tick, sad=False)` | Original animated companion |
| `context.window` | Selected normalized quota window, or `None` |
| `context.source` | `LIVE`, `STALE`, `NO DATA`, `BLOCKED`, or `CHECK` |
| `context.snapshot`, `.now`, `.page`, `.provider` | Shared render inputs; no credentials |
| `options` | Validated options; currently only text widgets accept `text` |

Draw only within the supplied canvas. Do not read files, make network requests, start processes, access credential stores, mutate snapshots, or poll a provider from a widget. Use `context.now` for animation so a fixed input produces fixed bytes. Keep work bounded; rendering happens at 1 Hz in the monitor and during interactive editing. New option types require explicit schema validation and documentation in the same PR.

Widgets are normal reviewed Python code with the application's process privileges; there is no claim of a Python sandbox. The registry never discovers/imports modules from layout strings, downloads code, or executes scripts embedded in JSON. Install source changes only with the same trust you give the rest of the application.

## Required evidence

1. Unit tests for missing data, 0%/100%, stale/error, blocked/expired-reset states, and the widget's smallest supported dimensions. Assert deterministic 1,024-byte output and clipping.
2. Import/validation tests if the layout schema or options change. Preserve the mandatory status widget, size limits, and no-overlap rule.
3. Synthetic before/after images. Label desktop drafts separately from board-acknowledged frames. Do not use real account readings in PR assets.
4. Run `python -m unittest discover -s tests -v` and `python -m platformio run`. CI must pass, and required review/conversation rules apply. State any missing physical checks.

Follow [`CONTRIBUTING.md`](../CONTRIBUTING.md). Generation and screenshot-packaging helpers stay in ignored `tooling/`; version only required application code, portable layouts, tests, and finished documentation assets.
