"""Request game activation from the launcher's explicit Start action."""
import ctypes
from ctypes import wintypes

GAME_TITLE = 'hololive-Dreams'


def _user32():
    user32 = ctypes.WinDLL('user32', use_last_error=True)
    signatures = {
        'FindWindowW': ([wintypes.LPCWSTR, wintypes.LPCWSTR], wintypes.HWND),
        'IsWindow': ([wintypes.HWND], wintypes.BOOL),
        'IsIconic': ([wintypes.HWND], wintypes.BOOL),
        'GetForegroundWindow': ([], wintypes.HWND),
        'ShowWindowAsync': ([wintypes.HWND, ctypes.c_int], wintypes.BOOL),
        'SetForegroundWindow': ([wintypes.HWND], wintypes.BOOL),
    }
    for name, (arguments, result) in signatures.items():
        function = getattr(user32, name)
        function.argtypes, function.restype = arguments, result
    return user32


def request_game_foreground(title=GAME_TITLE, *, user32=None):
    """Make one best-effort request; the worker still verifies actual focus.

    Call on the GUI thread receiving Start, while it has foreground permission.
    No synthetic keys, input-queue attachment, or repeated focus stealing.
    """
    try:
        user32 = _user32() if user32 is None else user32
        window = user32.FindWindowW(None, title)
        if not window or not user32.IsWindow(window):
            return False
        if user32.IsIconic(window):
            if not user32.ShowWindowAsync(window, 9):  # SW_RESTORE
                return False
        elif user32.GetForegroundWindow() == window:
            return True
        return bool(user32.SetForegroundWindow(window))
    except (AttributeError, OSError):
        return False
