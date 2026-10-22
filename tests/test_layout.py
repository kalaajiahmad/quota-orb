from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
import zlib

from bridge.display import confirmed_pixels, mirror_state
from bridge.layout import CLASSIC, LayoutStore, load, render_layout, save, starter, validate
from bridge.model import normalize
from bridge.render import Canvas
from bridge.widgets import Context, WIDGETS, WidgetCanvas


def context(used=28,error=False):
    snapshot = normalize({'rateLimits':{'limitId':'codex','primary':{
        'usedPercent':used,'windowDurationMins':10080,'resetsAt':2_000_000_000}}},now=1000)
    return Context(snapshot,1001,error=error)


class LayoutTests(unittest.TestCase):
    def test_starter_is_valid_bounded_and_deterministic(self):
        value = starter()
        self.assertEqual(validate(value),value)
        frame = render_layout(value,context())
        self.assertEqual(len(frame),1024)
        self.assertEqual(frame,render_layout(value,context()))
        self.assertNotEqual(frame,render_layout(value,context(used=90)))
        self.assertNotEqual(frame,render_layout(value,context(error=True)))

    def test_unknown_code_paths_fields_and_options_are_rejected(self):
        variants = []
        for key,value in [('kind','external.module'),('options',{'script':'EXECUTION_MARKER'}),
                          ('options',{'url':'https://invalid.example'})]:
            item = starter()
            item['widgets'][0][key] = value
            variants.append(item)
        item = starter()
        item['import'] = 'EXECUTION_MARKER'
        variants.append(item)
        for value in variants:
            with self.assertRaises(ValueError):
                validate(value)

    def test_bounds_overlap_duplicates_status_and_version(self):
        mutations = [lambda v:v.update(version=True),lambda v:v.update(version=2),
            lambda v:v['widgets'][0].update(x=-1),lambda v:v['widgets'][0].update(width=129),
            lambda v:v['widgets'][0].update(y=0.0),lambda v:v['widgets'][0].update(x=True),
            lambda v:v['widgets'][1].update(x=1),lambda v:v['widgets'].pop(1),
            lambda v:v['widgets'][1].update(id=v['widgets'][0]['id'])]
        for mutate in mutations:
            value = starter()
            mutate(value)
            with self.assertRaises(ValueError):
                validate(value)

    def test_atomic_save_preserves_last_valid_on_bad_apply_and_import(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'layout.json'
            save(path,starter())
            store = LayoutStore(path)
            self.assertEqual(store.read(),starter())
            invalid = starter()
            invalid['widgets'][0]['x'] = -1
            with self.assertRaises(ValueError):
                save(path,invalid)
            self.assertEqual(load(path),starter())
            path.write_text('{"script":"EXECUTION_MARKER"}')
            self.assertEqual(store.read(),starter())
            self.assertIsNotNone(store.error)
            save(path,CLASSIC)
            self.assertEqual(store.read(),CLASSIC)
            self.assertIsNone(store.error)
            path.write_bytes(b' '*16385)
            with self.assertRaises(ValueError):
                load(path)

    def test_widget_pixels_are_clipped_to_own_rectangle(self):
        target = Canvas()
        clipped = WidgetCanvas(target,(10,10,2,2))
        clipped.rect(-3,-3,9,9)
        expected = Canvas()
        expected.rect(10,10,2,2)
        self.assertEqual(target.data,expected.data)

    def test_equal_timestamp_and_size_cannot_hide_layout_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'layout.json'
            first = starter()
            save(path,first)
            stamp = path.stat().st_mtime_ns
            size = path.stat().st_size
            store = LayoutStore(path)
            self.assertEqual(store.read(),first)
            changed = starter()
            changed['widgets'][0]['x'] = 2
            save(path,changed)
            self.assertEqual(path.stat().st_size,size)
            os.utime(path,ns=(stamp,stamp))
            self.assertEqual(store.read(),changed)
            path.write_text(path.read_text().replace('"version": 1','"version": 2'))
            os.utime(path,ns=(stamp,stamp))
            self.assertEqual(store.read(),changed)
            self.assertIsNotNone(store.error)

    def test_all_registered_widgets_render_missing_and_live_data(self):
        for key,widget in WIDGETS.items():
            for source in (Context(None,1001),context(0),context(100),context(error=True)):
                with self.subTest(widget=key,source=source.source):
                    target = Canvas()
                    widget.draw(WidgetCanvas(target,(0,0,widget.width,widget.height)),source,{})
                    self.assertEqual(len(target.data),1024)

    def test_export_contains_only_layout_fields(self):
        value = starter()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'export.json'
            save(path,value)
            self.assertEqual(set(json.loads(path.read_text())),{'version','mode','widgets'})
            self.assertNotIn('snapshot',path.read_text())
            self.assertNotIn('fetched_at',path.read_text())


class MirrorTests(unittest.TestCase):
    def record(self):
        pixels = bytes(range(256))*4
        now = time.time()
        return {'running':True,'source':'LIVE','usb_connected':True,'updated_at':now,
            'display_frame':{'pixels':pixels.hex(),'acknowledged_at':now,
                'ack':{'type':'ack','seq':4,'crc':zlib.crc32(pixels)}}}

    def test_preview_uses_acknowledged_bytes_and_requires_matching_crc(self):
        value = self.record()
        self.assertEqual(confirmed_pixels(value),bytes(range(256))*4)
        for mutate in (lambda r:r.update(pixels='bad'),lambda r:r['ack'].update(crc=0),
                       lambda r:r['ack'].update(type='nack'),lambda r:r['ack'].update(seq=True),
                       lambda r:r.update(acknowledged_at=time.time()+100)):
            bad = deepcopy(value)
            mutate(bad['display_frame'])
            self.assertIsNone(confirmed_pixels(bad))

    def test_offline_paused_stale_or_unacknowledged_frames_are_not_live(self):
        value = self.record()
        self.assertTrue(mirror_state(value)[1])
        for fields in ({'paused':True},{'usb_connected':False},{'updated_at':time.time()-8},
                       {'running':False},{'display_frame':None}):
            self.assertFalse(mirror_state(dict(value,**fields))[1])


if __name__=='__main__':
    unittest.main()
