import math
import os
import threading

from .commons import cursor_position
from .model import SnapTarget

CLICKABLE_NAMES = {
    "ButtonControl",
    "CheckBoxControl",
    "RadioButtonControl",
    "HyperlinkControl",
    "MenuItemControl",
    "TreeItemControl",
    "TabItemControl",
    "ComboBoxControl",
    "ListItemControl",
    "SliderControl",
    "DataItemControl",
    "EditControl",
}


class MagnetRunner:
    def __init__(self):
        self.enabled = False
        self._stop = threading.Event()
        self._thread = None
        self._last_snap = None

    def start(self):
        if self._thread:
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="magnet", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        thread = self._thread
        if thread:
            thread.join(timeout=2.0)
            self._thread = None

    def pull(self):
        snap = self._last_snap
        self._last_snap = None
        return snap

    def set_enabled(self, enabled):
        self.enabled = bool(enabled)
        if not self.enabled:
            self._last_snap = None

    def _run(self):
        try:
            from uiautomation import ControlFromPoint

            while not self._stop.is_set():
                if self.enabled:
                    snap = self._scan(ControlFromPoint)
                    if snap is not None:
                        self._last_snap = snap
                self._stop.wait(0.08)
        except Exception:
            pass

    def _scan(self, from_point):
        try:
            x, y = cursor_position()
            node = from_point(int(x), int(y))
            for _ in range(8):
                if node is None:
                    return None
                if self._clickable(node):
                    break
                node = node.GetParentControl()
            else:
                return None
            rect = node.BoundingRectangle
            if not rect:
                return None
            if rect.right <= rect.left or rect.bottom <= rect.top:
                return None
            try:
                pid = int(node.ProcessId)
            except Exception:
                pid = 0
            if pid == os.getpid():
                return None
            cx = (rect.left + rect.right) / 2.0
            cy = (rect.top + rect.bottom) / 2.0
            half = math.hypot((rect.right - rect.left) / 2.0, (rect.bottom - rect.top) / 2.0)
            dist = self._distance(x, y, rect)
            return SnapTarget(float(cx), float(cy), float(half), float(dist))
        except Exception:
            return None

    @staticmethod
    def _clickable(node):
        try:
            name = str(getattr(node, "ControlTypeName", ""))
            if name in CLICKABLE_NAMES:
                return True
            if node.GetInvokePattern():
                return True
        except Exception:
            return False
        return False

    @staticmethod
    def _distance(x, y, rect):
        dx = 0.0
        if x < rect.left:
            dx = rect.left - x
        elif x > rect.right:
            dx = x - rect.right
        dy = 0.0
        if y < rect.top:
            dy = rect.top - y
        elif y > rect.bottom:
            dy = y - rect.bottom
        return math.hypot(dx, dy)