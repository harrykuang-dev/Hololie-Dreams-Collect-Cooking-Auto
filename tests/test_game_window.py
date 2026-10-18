"""Foreground requests use only window APIs; all native calls are mocked."""
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'outputs/kitchen-bot'))
from game_window import GAME_TITLE, request_game_foreground


class GameWindow(unittest.TestCase):
    def api(self, **values):
        api = Mock(spec=['FindWindowW','IsWindow','IsIconic','GetForegroundWindow',
                         'ShowWindowAsync','SetForegroundWindow'])
        defaults = dict(FindWindowW=0x123456789,IsWindow=True,IsIconic=False,
                        GetForegroundWindow=0x987654321,ShowWindowAsync=True,
                        SetForegroundWindow=True)
        defaults.update(values)
        for name,value in defaults.items():getattr(api,name).return_value=value
        return api

    def test_normal_window_is_activated_without_changing_its_size(self):
        api=self.api()
        self.assertTrue(request_game_foreground(user32=api))
        api.FindWindowW.assert_called_once_with(None,GAME_TITLE)
        api.SetForegroundWindow.assert_called_once_with(0x123456789)
        api.ShowWindowAsync.assert_not_called()

    def test_minimized_window_is_restored_before_activation(self):
        api=self.api(IsIconic=True)
        self.assertTrue(request_game_foreground(user32=api))
        calls=[call[0] for call in api.mock_calls]
        self.assertLess(calls.index('ShowWindowAsync'),calls.index('SetForegroundWindow'))
        api.ShowWindowAsync.assert_called_once_with(0x123456789,9)

    def test_foreground_game_is_left_alone(self):
        api=self.api(GetForegroundWindow=0x123456789)
        self.assertTrue(request_game_foreground(user32=api))
        api.SetForegroundWindow.assert_not_called()
        api.ShowWindowAsync.assert_not_called()

    def test_missing_or_destroyed_window_is_not_activated(self):
        for values in ({'FindWindowW':0},{'IsWindow':False}):
            with self.subTest(values=values):
                api=self.api(**values)
                self.assertFalse(request_game_foreground(user32=api))
                api.SetForegroundWindow.assert_not_called()
                api.ShowWindowAsync.assert_not_called()

    def test_denied_activation_is_not_retried(self):
        api=self.api(SetForegroundWindow=False)
        self.assertFalse(request_game_foreground(user32=api))
        api.SetForegroundWindow.assert_called_once()

    def test_failed_restore_does_not_activate(self):
        api=self.api(IsIconic=True,ShowWindowAsync=False)
        self.assertFalse(request_game_foreground(user32=api))
        api.SetForegroundWindow.assert_not_called()

    def test_native_api_error_falls_back_to_waiting(self):
        with patch('game_window._user32',side_effect=OSError('Unavailable')):
            self.assertFalse(request_game_foreground())


if __name__=='__main__':unittest.main()
