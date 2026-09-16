"""Windows window backend (ctypes: user32, dwmapi, kernel32)."""

from __future__ import annotations

import ctypes
import os
import time
from ctypes import wintypes

from dcdclip.windows.base import Rect, WindowInfo

GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x00000080
GW_OWNER = 4
SW_RESTORE = 9
DWMWA_CLOAKED = 14
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = -4

_EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)


class Win32Windows:
    name = "win32"

    def __init__(self) -> None:
        self.user32 = ctypes.WinDLL("user32", use_last_error=True)
        self.kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        try:
            self.dwmapi: ctypes.WinDLL | None = ctypes.WinDLL("dwmapi")
        except OSError:
            self.dwmapi = None
        u = self.user32
        u.GetWindowTextLengthW.argtypes = (wintypes.HWND,)
        u.GetWindowTextW.argtypes = (wintypes.HWND, wintypes.LPWSTR, ctypes.c_int)
        u.IsWindowVisible.argtypes = (wintypes.HWND,)
        u.GetWindowLongW.argtypes = (wintypes.HWND, ctypes.c_int)
        u.GetWindowLongW.restype = ctypes.c_long
        u.GetWindow.argtypes = (wintypes.HWND, wintypes.UINT)
        u.GetWindow.restype = wintypes.HWND
        u.GetWindowThreadProcessId.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.DWORD))
        u.GetForegroundWindow.restype = wintypes.HWND
        u.SetForegroundWindow.argtypes = (wintypes.HWND,)
        u.ShowWindow.argtypes = (wintypes.HWND, ctypes.c_int)
        u.IsIconic.argtypes = (wintypes.HWND,)
        u.GetClientRect.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.RECT))
        u.ClientToScreen.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.POINT))
        u.IsWindow.argtypes = (wintypes.HWND,)
        u.keybd_event.argtypes = (wintypes.BYTE, wintypes.BYTE, wintypes.DWORD, ctypes.c_size_t)
        try:  # physical pixel coordinates, consistent with mss captures
            u.SetProcessDpiAwarenessContext(
                ctypes.c_void_p(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2)
            )
        except (AttributeError, OSError):
            pass

    # -- helpers -------------------------------------------------------------------------
    def _title(self, hwnd: int) -> str:
        n = self.user32.GetWindowTextLengthW(hwnd)
        if n <= 0:
            return ""
        buf = ctypes.create_unicode_buffer(n + 1)
        self.user32.GetWindowTextW(hwnd, buf, n + 1)
        return buf.value

    def _pid(self, hwnd: int) -> int:
        pid = wintypes.DWORD(0)
        self.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        return int(pid.value)

    def _exe_name(self, pid: int) -> str:
        h = self.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not h:
            return ""
        try:
            size = wintypes.DWORD(1024)
            buf = ctypes.create_unicode_buffer(size.value)
            if not self.kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
                return ""
            base = os.path.basename(buf.value)
            return base[:-4] if base.lower().endswith(".exe") else base
        finally:
            self.kernel32.CloseHandle(h)

    def _cloaked(self, hwnd: int) -> bool:
        if self.dwmapi is None:
            return False
        value = wintypes.DWORD(0)
        res = self.dwmapi.DwmGetWindowAttribute(
            wintypes.HWND(hwnd), DWMWA_CLOAKED, ctypes.byref(value), ctypes.sizeof(value)
        )
        return res == 0 and value.value != 0

    def _is_candidate(self, hwnd: int) -> bool:
        u = self.user32
        if not u.IsWindowVisible(hwnd) or u.GetWindow(hwnd, GW_OWNER):
            return False
        if u.GetWindowLongW(hwnd, GWL_EXSTYLE) & WS_EX_TOOLWINDOW:
            return False
        return not self._cloaked(hwnd)

    # -- backend API ---------------------------------------------------------------------
    def list_windows(self) -> list[WindowInfo]:
        result: list[WindowInfo] = []

        def cb(hwnd, _lparam):
            if self._is_candidate(hwnd):
                title = self._title(hwnd)
                if title:
                    pid = self._pid(hwnd)
                    result.append(WindowInfo(int(hwnd), title, self._exe_name(pid), pid))
            return True

        self.user32.EnumWindows(_EnumWindowsProc(cb), 0)
        return result

    def active_window_id(self) -> int | None:
        hwnd = self.user32.GetForegroundWindow()
        return int(hwnd) if hwnd else None

    def activate(self, window_id: int) -> None:
        u = self.user32
        if u.IsIconic(window_id):
            u.ShowWindow(window_id, SW_RESTORE)
        # Windows only lets the process that received the last input change the
        # foreground window; a synthetic Alt tap is the documented workaround.
        u.keybd_event(0x12, 0, 0, 0)
        u.keybd_event(0x12, 0, 2, 0)
        u.SetForegroundWindow(window_id)
        for _ in range(10):
            if u.GetForegroundWindow() == window_id:
                return
            time.sleep(0.05)

    def geometry(self, window_id: int) -> Rect | None:
        if not self.user32.IsWindow(window_id):
            return None
        rc = wintypes.RECT()
        if not self.user32.GetClientRect(window_id, ctypes.byref(rc)):
            return None
        origin = wintypes.POINT(0, 0)
        self.user32.ClientToScreen(window_id, ctypes.byref(origin))
        return Rect(origin.x, origin.y, rc.right - rc.left, rc.bottom - rc.top)

    def close(self) -> None:
        pass
