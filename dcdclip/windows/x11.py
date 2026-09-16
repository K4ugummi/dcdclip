"""X11 window backend based on EWMH hints (python-xlib)."""

from __future__ import annotations

from Xlib import X, Xatom, display, error
from Xlib.protocol import event

from dcdclip.windows.base import Rect, WindowInfo


class X11Windows:
    name = "x11-ewmh"

    def __init__(self, disp: display.Display | None = None) -> None:
        self.display = disp or display.Display()
        self.root = self.display.screen().root
        a = self.display.intern_atom
        self._client_list = a("_NET_CLIENT_LIST")
        self._active = a("_NET_ACTIVE_WINDOW")
        self._wm_name = a("_NET_WM_NAME")
        self._utf8 = a("UTF8_STRING")
        self._pid = a("_NET_WM_PID")
        self._frame_extents = a("_NET_FRAME_EXTENTS")

    def _prop(self, win, atom, ptype):
        try:
            p = win.get_full_property(atom, ptype)
        except error.XError:
            return None
        return p.value if p is not None else None

    def _title(self, win) -> str:
        value = self._prop(win, self._wm_name, self._utf8)
        if value:
            return value.decode("utf-8", "replace") if isinstance(value, bytes) else str(value)
        try:
            name = win.get_wm_name()
        except error.XError:
            name = None
        if isinstance(name, bytes):
            return name.decode("latin-1", "replace")
        return name or ""

    def _class(self, win) -> str:
        try:
            cls = win.get_wm_class()
        except error.XError:
            cls = None
        if not cls:
            return ""
        return cls[1] if len(cls) > 1 else cls[0]

    def list_windows(self) -> list[WindowInfo]:
        ids = self._prop(self.root, self._client_list, Xatom.WINDOW) or []
        result: list[WindowInfo] = []
        for wid in ids:
            win = self.display.create_resource_object("window", wid)
            pid = self._prop(win, self._pid, Xatom.CARDINAL)
            result.append(
                WindowInfo(
                    id=int(wid),
                    title=self._title(win),
                    app_class=self._class(win),
                    pid=int(pid[0]) if pid else None,
                )
            )
        return result

    def active_window_id(self) -> int | None:
        value = self._prop(self.root, self._active, Xatom.WINDOW)
        if not value or value[0] == 0:
            return None
        return int(value[0])

    def activate(self, window_id: int) -> None:
        win = self.display.create_resource_object("window", window_id)
        msg = event.ClientMessage(
            window=win,
            client_type=self._active,
            data=(32, [2, X.CurrentTime, 0, 0, 0]),  # 2 = request from a pager/tool
        )
        self.root.send_event(msg, event_mask=X.SubstructureRedirectMask | X.SubstructureNotifyMask)
        try:
            win.configure(stack_mode=X.Above)
        except error.XError:
            pass
        self.display.flush()

    def geometry(self, window_id: int) -> Rect | None:
        win = self.display.create_resource_object("window", window_id)
        try:
            geo = win.get_geometry()
            origin = self.root.translate_coords(win, 0, 0)
        except error.XError:
            return None
        return Rect(origin.x, origin.y, geo.width, geo.height)

    def close(self) -> None:
        self.display.close()
