"""macOS window backend: Quartz window list, AppKit activation, Accessibility raise.

Window titles of other applications are only available with the Screen Recording
permission (macOS 10.15+); without it the owner application name is used as title.
"""

from __future__ import annotations

import Quartz
from AppKit import NSApplicationActivateIgnoringOtherApps, NSRunningApplication, NSWorkspace

from dcdclip.windows.base import Rect, WindowInfo


class MacWindows:
    name = "macos-quartz"

    def _infos(self) -> list[dict]:
        opts = Quartz.kCGWindowListOptionOnScreenOnly | Quartz.kCGWindowListExcludeDesktopElements
        infos = Quartz.CGWindowListCopyWindowInfo(opts, Quartz.kCGNullWindowID) or []
        result = []
        for info in infos:
            if info.get("kCGWindowLayer", 0) != 0:
                continue
            bounds = info.get("kCGWindowBounds", {})
            if bounds.get("Height", 0) < 50 or bounds.get("Width", 0) < 50:
                continue
            result.append(dict(info))
        return result

    @staticmethod
    def _to_window(info: dict) -> WindowInfo:
        owner = str(info.get("kCGWindowOwnerName", ""))
        title = str(info.get("kCGWindowName") or owner)
        return WindowInfo(
            id=int(info["kCGWindowNumber"]),
            title=title,
            app_class=owner,
            pid=int(info.get("kCGWindowOwnerPID", 0)) or None,
        )

    def list_windows(self) -> list[WindowInfo]:
        return [self._to_window(i) for i in self._infos()]

    def active_window_id(self) -> int | None:
        app = NSWorkspace.sharedWorkspace().frontmostApplication()
        if app is None:
            return None
        pid = int(app.processIdentifier())
        for info in self._infos():  # front-to-back order
            if int(info.get("kCGWindowOwnerPID", 0)) == pid:
                return int(info["kCGWindowNumber"])
        return None

    def _info_for(self, window_id: int) -> dict | None:
        for info in self._infos():
            if int(info["kCGWindowNumber"]) == window_id:
                return info
        return None

    def activate(self, window_id: int) -> None:
        info = self._info_for(window_id)
        if info is None:
            return
        pid = int(info.get("kCGWindowOwnerPID", 0))
        app = NSRunningApplication.runningApplicationWithProcessIdentifier_(pid)
        if app is not None:
            app.activateWithOptions_(NSApplicationActivateIgnoringOtherApps)
        title = info.get("kCGWindowName")
        if title:
            self._raise_by_title(pid, str(title))

    @staticmethod
    def _raise_by_title(pid: int, title: str) -> None:
        try:
            from ApplicationServices import (
                AXUIElementCopyAttributeValue,
                AXUIElementCreateApplication,
                AXUIElementPerformAction,
                AXUIElementSetAttributeValue,
                kAXMainAttribute,
                kAXRaiseAction,
                kAXTitleAttribute,
                kAXWindowsAttribute,
            )
        except ImportError:
            return
        app = AXUIElementCreateApplication(pid)
        err, windows = AXUIElementCopyAttributeValue(app, kAXWindowsAttribute, None)
        if err or not windows:
            return
        for win in windows:
            err, t = AXUIElementCopyAttributeValue(win, kAXTitleAttribute, None)
            if not err and t == title:
                AXUIElementSetAttributeValue(win, kAXMainAttribute, True)
                AXUIElementPerformAction(win, kAXRaiseAction)
                return

    def geometry(self, window_id: int) -> Rect | None:
        info = self._info_for(window_id)
        if info is None:
            return None
        b = info["kCGWindowBounds"]
        return Rect(int(b["X"]), int(b["Y"]), int(b["Width"]), int(b["Height"]))

    def close(self) -> None:
        pass
