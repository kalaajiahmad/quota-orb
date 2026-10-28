import gc
import json
import os
from pathlib import Path
import tempfile
import time
import tkinter as tk
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import weakref
import zlib

from bridge.display import LiveDisplay
from bridge.desktop_widget import load_preferences, rendered_pixels, widget_status
from bridge.layout import load, save, starter
from bridge.studio import Studio, SCALE
from bridge.ui import MotionButton, windows_app_identity, APP_ID


@unittest.skipUnless(os.name=='nt','Supported Windows desktop UI')
class DesktopTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.runtime = Path(self.directory.name)
        windows_app_identity()
        self.root = tk.Tk()
        self.root.withdraw()

    def tearDown(self):
        root_reference = weakref.ref(self.root)
        try:
            self.root.destroy()
        finally:
            self.root = None
            # Tk controllers, callbacks, images and variables form Python cycles.
            # Finalize them on the thread that created Tcl, before a later
            # subprocess pipe-reader thread can trigger automatic collection.
            gc.collect()
            self.directory.cleanup()
        self.assertIsNone(root_reference(), 'Desktop test retained its Tk interpreter owner')

    def editor(self):
        editor = Studio(self.root,self.runtime)
        editor.root.pack()
        self.root.update_idletasks()
        return editor

    def test_mirror_has_exact_native_pixels_and_integer_zoom(self):
        frame = bytes([1])+bytes(1023)
        now = time.time()
        data = {'running':True,'updated_at':now,'source':'LIVE','usb_connected':True,
            'display_frame':{'pixels':frame.hex(),'acknowledged_at':now,
                'ack':{'type':'ack','seq':1,'crc':zlib.crc32(frame)}}}
        (self.runtime/'status.json').write_text(json.dumps(data))
        view = LiveDisplay(self.root,self.runtime)
        self.root.withdraw()
        view.refresh()
        view.set_zoom(1)
        self.assertEqual((view.image.width(),view.image.height()),(128,64))
        self.assertEqual(view.image.get(0,0),(220,249,240))
        self.assertEqual(view.image.get(0,1),(7,15,19))
        view.set_zoom(6)
        self.assertEqual((view.image.width(),view.image.height()),(768,384))
        self.assertEqual(view.image.get(5,5),(220,249,240))
        self.assertEqual(view.image.get(6,0),(7,15,19))

    def test_editor_drag_snaps_then_applies_only_valid_layout(self):
        editor = self.editor()
        editor.press(SimpleNamespace(x=101*SCALE,y=25*SCALE))
        editor.motion(SimpleNamespace(x=100*SCALE,y=24*SCALE))
        editor.release(None)
        self.assertEqual((editor.item()['x'],editor.item()['y']),(98,22))
        self.assertFalse(editor.apply_button.disabled)
        editor.apply()
        self.assertEqual(load(self.runtime/'layout.json'),editor.layout)
        editor.undo()
        self.assertEqual(editor.layout,starter())

    def test_overlap_cannot_replace_applied_layout(self):
        save(self.runtime/'layout.json',starter())
        editor = self.editor()
        editor.add('text',0,0)
        self.assertTrue(editor.apply_button.disabled)
        with patch('bridge.studio.messagebox.showerror'):
            editor.apply()
        self.assertEqual(load(self.runtime/'layout.json'),starter())

    def test_palette_drop_adds_widget_with_canvas_coordinates(self):
        editor = self.editor()
        editor.select('robot')
        editor.remove()
        editor.palette_start('robot')
        editor.palette_drop(SimpleNamespace(x_root=editor.canvas.winfo_rootx()+100*SCALE,
            y_root=editor.canvas.winfo_rooty()+24*SCALE))
        self.assertEqual(editor.item()['kind'],'robot')
        self.assertEqual((editor.item()['x'],editor.item()['y']),(100,24))
        self.assertFalse(editor.apply_button.disabled)

    def test_import_failure_preserves_draft_and_active_layout(self):
        save(self.runtime/'layout.json',starter())
        editor = self.editor()
        bad = self.runtime/'untrusted.json'
        bad.write_text('{"module":"EXECUTION_MARKER"}')
        with patch('bridge.studio.filedialog.askopenfilename',return_value=str(bad)), \
             patch('bridge.studio.messagebox.showerror') as error:
            editor.import_layout()
            error.assert_called_once()
        self.assertEqual(editor.layout,starter())
        self.assertEqual(load(self.runtime/'layout.json'),starter())

    def test_animated_button_invocation_and_disabled_state(self):
        calls = []
        button = MotionButton(self.root,'Apply',lambda:calls.append('apply'))
        button.invoke()
        button.configure(state='disabled')
        button.invoke()
        self.assertEqual(calls,['apply'])
        button.hover_to(True)
        self.assertGreater(button.progress,0)
        self.assertLessEqual(button.progress,1)

    def test_live_and_design_share_one_window_and_preserve_draft(self):
        view = LiveDisplay(self.root,self.runtime,demo=True)
        self.root.withdraw()
        view.edit_layout()
        editor = view.studio
        self.assertIs(editor.root.winfo_toplevel(),self.root)
        self.assertIs(view.active,editor.root)
        editor.select('robot')
        editor.remove()
        draft = json.dumps(editor.layout)
        view.show_live()
        view.edit_layout()
        self.assertIs(view.studio,editor)
        self.assertEqual(json.dumps(editor.layout),draft)
        self.assertFalse(any(isinstance(child,tk.Toplevel) for child in self.root.winfo_children()))

    def test_widget_remains_visible_after_main_window_closes_and_can_be_removed(self):
        view = LiveDisplay(self.root,self.runtime)
        self.root.withdraw()
        view.add_widget()
        self.assertTrue(load_preferences(self.runtime)['enabled'])
        frame = bytes([1])+bytes(1023)
        view.widget.update({'running':True,'updated_at':time.time(),'source':'LIVE'},frame)
        self.assertEqual(view.widget.image.get(0,0),(220,249,240))
        view.close_window()
        self.assertEqual(self.root.state(),'withdrawn')
        self.assertTrue(view.widget.window.winfo_exists())
        # Keep the root alive for the fixture's teardown while checking removal.
        self.root.deiconify()
        view.widget.close()
        self.assertIsNone(view.widget)
        self.assertFalse(load_preferences(self.runtime)['enabled'])

    def test_widget_restores_enabled_preference(self):
        (self.runtime/'desktop-widget.json').write_text('{"enabled": true, "x": 100, "y": 120}')
        view = LiveDisplay(self.root,self.runtime)
        self.assertIsNotNone(view.widget)
        self.assertEqual(view.widget.window.winfo_x(),100)
        self.assertEqual(view.widget.window.winfo_y(),120)

    def test_widget_restores_tk_signed_position(self):
        view = LiveDisplay(self.root,self.runtime)
        view.add_widget()
        window = view.widget.window
        window.update_idletasks()
        # Tk's negative position offsets count from the far screen edge.
        window.geometry(f'-{window.winfo_screenwidth()}-{window.winfo_screenheight()}')
        window.update_idletasks()
        view.widget.persist(True)
        position = load_preferences(self.runtime)['position']
        window.destroy()
        view.widget = None
        view.add_widget()
        view.widget.window.update_idletasks()
        self.assertEqual(load_preferences(self.runtime)['position'], position)
        from bridge.desktop_widget import position_from_geometry
        self.assertEqual(position_from_geometry(view.widget.window.geometry()), position)

    def test_widget_reports_monitor_staleness_and_rejects_bad_frames(self):
        self.assertEqual(widget_status({'running':True,'updated_at':10,'source':'LIVE'},20),
                         'MONITOR NOT RESPONDING')
        self.assertIsNone(rendered_pixels({'rendered_frame':'00'}))
        self.assertEqual(rendered_pixels({'rendered_frame':'00'*1024}),bytes(1024))

    def test_rapid_view_changes_cancel_previous_animation(self):
        view = LiveDisplay(self.root,self.runtime,demo=True)
        self.root.withdraw()
        with patch('bridge.display.motion_enabled',return_value=True), \
             patch.object(self.root,'state',return_value='normal'):
            view.edit_layout()
            view.show_live()
            view.edit_layout()
            deadline = time.monotonic()+.35
            while time.monotonic()<deadline:
                self.root.update()
                time.sleep(.01)
        self.assertIsNone(view.navigation_timer)
        self.assertIs(view.active,view.studio.root)
        self.assertEqual(view.studio.root.winfo_manager(),'pack')

    def test_windows_identity_is_quota_orb(self):
        import ctypes
        shell = ctypes.WinDLL('shell32')
        read = shell.GetCurrentProcessExplicitAppUserModelID
        read.argtypes,read.restype = [ctypes.POINTER(ctypes.c_void_p)],ctypes.c_long
        pointer = ctypes.c_void_p()
        self.assertEqual(read(ctypes.byref(pointer)),0)
        try:
            self.assertEqual(ctypes.wstring_at(pointer),APP_ID)
        finally:
            free = ctypes.WinDLL('ole32').CoTaskMemFree
            free.argtypes = [ctypes.c_void_p]
            free(pointer)


if __name__=='__main__':
    unittest.main()
