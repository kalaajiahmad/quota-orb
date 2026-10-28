import tempfile
from pathlib import Path
import unittest

from bridge.desktop_widget import (load_preferences, position_from_geometry, rendered_pixels,
                                   save_preferences, widget_status)


class WidgetDataTests(unittest.TestCase):
    def test_preferences_round_trip_and_invalid_file(self):
        with tempfile.TemporaryDirectory() as folder:
            runtime = Path(folder)
            save_preferences(runtime, True, 40, 60)
            self.assertEqual(load_preferences(runtime), {'enabled': True, 'x': 40, 'y': 60})
            (runtime / 'desktop-widget.json').write_text('not json', encoding='utf-8')
            self.assertEqual(load_preferences(runtime), {})

    def test_signed_window_position_is_preserved_without_geometry_size(self):
        with tempfile.TemporaryDirectory() as folder:
            runtime = Path(folder)
            save_preferences(runtime, True, -216, -91, '270x170-2510-1280')
            self.assertEqual(load_preferences(runtime)['position'], '-2510-1280')
            self.assertEqual(position_from_geometry('270x170+10-50'), '+10-50')
            self.assertIsNone(position_from_geometry('270x170-10+20;bad'))

    def test_frame_and_monitor_freshness(self):
        self.assertIsNone(rendered_pixels({'rendered_frame': '00'}))
        self.assertIsNone(rendered_pixels({'rendered_frame': 'invalid'}))
        self.assertEqual(rendered_pixels({'rendered_frame': '00' * 1024}), bytes(1024))
        self.assertEqual(widget_status({'running': True, 'updated_at': 10, 'source': 'LIVE'}, 20),
                         'MONITOR NOT RESPONDING')
        self.assertEqual(widget_status({'running': True, 'updated_at': 19, 'source': 'LIVE'}, 20),
                         'LIVE')
        self.assertEqual(widget_status({'running': True, 'updated_at': 19, 'paused': True}, 20),
                         'PAUSED')


if __name__ == '__main__':
    unittest.main()
