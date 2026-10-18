"""Verify custom counts, cooperative stops and capture without MP4 encoding."""
from pathlib import Path
import os
import sys
import tempfile
import unittest
from unittest.mock import patch
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT), str(ROOT/'outputs/kitchen-bot')]
from gui import parse_games, CookingApp
from standalone import Desktop, Recording
from app_settings import StartHotkey, hotkeys_conflict, captured_hotkey, parse_stop_hotkey


class Controls(unittest.TestCase):
    def test_num_and_caps_lock_bits_do_not_become_alt(self):
        for lock in (0,0x8,0x2,0x20,0x2A,0x40008):
            for sym,vk,key in (('F8',0x77,'F8'),('q',0x51,'Q'),('KP_1',0x61,'Num1')):
                self.assertEqual(captured_hotkey(sym,lock,vk),key)
                self.assertEqual(captured_hotkey(sym,lock|4,vk),'Ctrl+'+key)
                self.assertEqual(captured_hotkey(sym,lock|0x20000,vk),'Alt+'+key)
                self.assertEqual(captured_hotkey(sym,lock|0x20005,vk),'Ctrl+Alt+Shift+'+key)

    def test_count(self):
        for text in ('1', '5', '6', '1000'):
            self.assertEqual(parse_games(text), int(text))
        for text in ('', '0', '-1', '1.5', 'abc', '１２', '1000000000'):
            with self.assertRaises(ValueError): parse_games(text)

    def test_stop_file_and_escape(self):
        desktop=object.__new__(Desktop)
        class Keys:
            value=0
            def GetAsyncKeyState(self, key): return self.value
        desktop.u=Keys()
        with tempfile.TemporaryDirectory() as folder:
            signal=Path(folder)/'stop'
            with patch.dict(os.environ, {'COOKING_STOP_FILE':str(signal)}):
                self.assertFalse(desktop.should_stop())
                signal.touch(); self.assertTrue(desktop.should_stop())
                self.assertFalse(desktop.click(1, 1))
                signal.unlink(); desktop.u.value=0x8000
                self.assertTrue(desktop.should_stop())

    def test_video_off_still_publishes_frames(self):
        class Capture:
            w=h=32
            def capture(self): return np.zeros((32,32,3), dtype=np.uint8)
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {'COOKING_RECORD_VIDEO':'0'}), patch('standalone.cv2.VideoWriter') as encoder:
            recording=Recording(Capture(), Path(folder), 20)
            try:
                packet=recording.frame_after(0)
                self.assertIsNotNone(packet)
                self.assertEqual(packet[1].shape, (32,32,3))
                encoder.assert_not_called()
            finally: recording.close()

    def test_custom_modifier_shortcut_requires_release_and_exact_modifiers(self):
        held=set()
        state=lambda key: 0x8000 if key in held else 0
        shortcut=StartHotkey()
        self.assertFalse(shortcut.poll('Ctrl+F6',state))
        held.update((0x11,0x75))
        self.assertTrue(shortcut.poll('Ctrl+F6',state))
        self.assertFalse(shortcut.poll('Ctrl+F6',state))
        held.clear(); shortcut.poll('Ctrl+F6',state)
        held.update((0x11,0x10,0x75))
        self.assertFalse(shortcut.poll('Ctrl+F6',state))
        self.assertTrue(hotkeys_conflict('F6','Ctrl+F6'))
        self.assertFalse(hotkeys_conflict('Ctrl+F6','Alt+F6'))
        self.assertEqual(captured_hotkey('F6',0x04,0x75),'Ctrl+F6')
        self.assertEqual(parse_stop_hotkey('Alt+F9'),((0x12,),0x78))

    def test_stop_shortcut_respects_modifier(self):
        desktop=object.__new__(Desktop)
        held=set()
        class Keys:
            def GetAsyncKeyState(self,key): return 0x8000 if key in held else 0
        desktop.u=Keys()
        with patch.dict(os.environ,{'COOKING_STOP_FILE':'','COOKING_STOP_KEY':'Ctrl+F9'}):
            held.add(0x78); self.assertFalse(desktop.should_stop())
            held.add(0x11); self.assertTrue(desktop.should_stop())

    def test_pause_event_survives_key_release_and_duplicate_polls(self):
        desktop=object.__new__(Desktop); desktop.toggle_seen=0
        with tempfile.TemporaryDirectory() as folder:
            signal=Path(folder)/'toggle';signal.write_text('0',encoding='ascii')
            with patch.dict(os.environ,{'COOKING_TOGGLE_FILE':str(signal)}):
                self.assertFalse(desktop.should_toggle())
                signal.write_text('1',encoding='ascii')
                self.assertTrue(desktop.should_toggle())
                self.assertFalse(desktop.should_toggle())
                signal.write_text('3',encoding='ascii')
                self.assertFalse(desktop.should_toggle())
                signal.write_text('4',encoding='ascii')
                self.assertTrue(desktop.should_toggle())

    def test_launcher_retries_a_busy_pause_signal(self):
        launcher=object.__new__(CookingApp)
        launcher.child=object(); launcher.toggle_count=0
        class Root:
            callbacks=[]
            def after(self, delay, callback): self.callbacks.append(callback)
        launcher.root=Root()
        with tempfile.TemporaryDirectory() as folder:
            launcher.stop_path=Path(folder)/'stop'
            launcher.toggle_path=Path(folder)/'toggle'
            launcher.toggle_path.write_text('0',encoding='ascii')
            with patch.object(Path,'replace',side_effect=PermissionError('Reader busy')):
                launcher.toggle()
            self.assertEqual(launcher.toggle_path.read_text(), '0')
            launcher.root.callbacks.pop()()
            self.assertEqual(launcher.toggle_path.read_text(), '1')
            launcher.publish_toggle()  # Duplicate retry is harmless.

    def test_shortcut_help_preserves_escape_inside_start_binding(self):
        class Value:
            def __init__(self,text):self.text=text
            def get(self):return self.text
        launcher=object.__new__(CookingApp)
        launcher.start_key=Value('Ctrl+Esc');launcher.stop_key=Value('F9')
        self.assertEqual(launcher.with_keys('F8 start; Esc stop'),'Ctrl+Esc start; F9 stop')


if __name__=='__main__': unittest.main()
