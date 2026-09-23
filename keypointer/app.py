import collections
import logging
import time
import tkinter as tk
from tkinter import messagebox

from . import art, model, mouse, native_cursor, settings_view
from .autostart import set_autostart
from .commons import cursor_position, user32
from .hook import KeyboardHook
from .magnet import MagnetRunner
from .overlay import CursorOverlay
from .tray import Tray

TICK_MS = 16
TRAIL_CAP = 10
TRAIL_DECAY = 300.0
IDLE_SPEED = 12.0
MODS = (0x11, 0x12, 0x10, 0x5B, 0x5C)
MOVE_AXES = {
    0x25: (-1.0, 0.0),
    0x26: (0.0, -1.0),
    0x27: (1.0, 0.0),
    0x28: (0.0, 1.0),
}


class App:
    def __init__(self, root, store):
        self._root = root
        self._store = store
        self._log = logging.getLogger("app")
        self._settings = store.load()
        self._rev = {vk: action for action, vk in self._settings.bindings.items()}
        self._cursor = model.CursorModel()
        self._overlay = CursorOverlay()
        self._hook = KeyboardHook(self._on_key)
        self._hook.set_binding_keys(self._binding_keys())
        self._hook.set_mover_keys(set(model.MOVE_KEYS))
        self._hook.set_emergency(self._on_emergency)
        self._tray = Tray(
            lambda: self._root.after(0, self._open_settings),
            lambda: self._root.after(0, self._toggle_magnet),
            lambda: self._root.after(0, self._quit),
        )
        self._magnet = MagnetRunner()
        self._magnet.set_enabled(self._settings.magnet_enabled)
        self._clicks = collections.deque()
        self._ops = collections.deque()
        self._scroll_vk = None
        self._scroll_dir = 0
        self._next_scroll = 0.0
        self._trail = []
        self._running = False
        self._dialog_open = False
        self._ball_on = True
        self._tick_failures = 0

    def _binding_keys(self):
        return set(self._rev)

    def start(self):
        if not self._hook.start():
            messagebox.showwarning(
                "Keypointer",
                "Failed to install the global keyboard hook. "
                "Another instance may already be running.",
            )
            if self._root.winfo_exists():
                self._root.after(0, self._root.destroy)
            return
        if not self._overlay.start():
            messagebox.showwarning(
                "Keypointer",
                "Failed to create the cursor overlay.",
            )
            if self._root.winfo_exists():
                self._root.after(0, self._root.destroy)
            return
        try:
            native_cursor.hide()
        except Exception:
            self._log.exception("error while hiding the system cursor")
        self._tray.start()
        self._magnet.start()
        self._resync()
        self._running = True
        self._root.after(TICK_MS, self._tick)

    def stop(self):
        self._running = False
        if native_cursor.hidden():
            try:
                native_cursor.restore()
            except Exception:
                self._log.exception("error while restoring the system cursor")
        for closer in (self._tray.stop, self._magnet.stop, self._overlay.stop, self._hook.stop):
            try:
                closer()
            except Exception:
                self._log.exception("error while stopping")

    def _tick(self):
        if not self._running:
            return
        try:
            self._root.after(TICK_MS, self._tick)
        except tk.TclError:
            return
        while True:
            try:
                self._ops.popleft()()
            except IndexError:
                break
            except Exception:
                self._log.exception("error while processing an operation")
        if self._dialog_open:
            return
        if not self._overlay.alive():
            self._restore_native()
            self._ball_on = False
            return
        if not self._ball_on:
            self._tick_failures = 0
            return
        try:
            self._move()
            self._draw()
            self._tick_failures = 0
        except Exception:
            self._log.exception("error in the cursor loop")
            self._tick_failures += 1
            self._restore_native()
            self._ball_on = False
            try:
                self._overlay.set_visible(False)
            except Exception:
                self._log.exception("error while hiding the cursor overlay")
            if self._tick_failures >= 5:
                self._quit()

    def _move(self):
        now = time.monotonic()
        ax, ay = 0.0, 0.0
        for vk, (dx, dy) in MOVE_AXES.items():
            if user32.GetAsyncKeyState(vk) & 0x8000:
                ax += dx
                ay += dy
        snap = None
        if self._settings.magnet_enabled and self._magnet.enabled:
            snap = self._magnet.pull()
        was_locked = self._cursor.locked
        drive = self._cursor.update(TICK_MS / 1000.0, ax, ay, snap, self._settings)
        if not was_locked and self._cursor.locked:
            self._cursor.pulse = 0.8
        elif was_locked and not self._cursor.locked:
            self._cursor.pulse = 0.4
        if drive:
            mouse.move_to(self._cursor.x, self._cursor.y)
        elif not self._cursor.locked:
            self._resync()
        self._fire_clicks(now)

    def _draw(self):
        if not self._ball_on:
            return
        decay = TRAIL_DECAY * TICK_MS / 1000.0
        trail = []
        for px, py, pa in self._trail:
            pa -= decay
            if pa > 0:
                trail.append((px, py, pa))
        self._trail = trail
        cx, cy = self._cursor.x, self._cursor.y
        if not trail or abs(cx - trail[-1][0]) >= 1.0 or abs(cy - trail[-1][1]) >= 1.0:
            trail.append((int(round(cx)), int(round(cy)), 255))
        del trail[:-TRAIL_CAP]
        self._trail = trail
        bgra, left, top, side = art.draw_cursor(
            cx,
            cy,
            self._settings.cursor_radius,
            self._settings.color,
            trail,
            self._cursor.pulse,
            self._dialog_open,
        )
        self._overlay.render(bgra, left, top, side)

    def _fire_clicks(self, now):
        if self._scroll_vk is not None and now >= self._next_scroll:
            down = bool(user32.GetAsyncKeyState(self._scroll_vk) & 0x8000)
            mods = any(user32.GetAsyncKeyState(m) & 0x8000 for m in MODS)
            if not down or mods:
                self._scroll_vk = None
                self._scroll_dir = 0
            else:
                delta = self._scroll_dir * 120 * max(
                    1, int(round(self._settings.scroll_delta / 120.0))
                )
                mouse.scroll(delta)
                self._next_scroll = now + max(
                    0.0, self._settings.scroll_interval_ms / 1000.0
                )
        while True:
            try:
                action = self._clicks.popleft()
            except IndexError:
                break
            if action == "left_click":
                mouse.left_click()
            elif action == "right_click":
                mouse.right_click()
            elif action == "double_click":
                mouse.double_click_left()
            elif action == "middle_click":
                mouse.middle_click()

    def _on_key(self, vk, is_up=False, repeat=False):
        if is_up or repeat or self._dialog_open:
            return
        if vk in MODS or vk in model.MOVE_KEYS:
            return
        action = self._rev.get(vk)
        if action is None:
            return
        if action in ("scroll_up", "scroll_down"):
            self._scroll_vk = vk
            self._scroll_dir = 1 if action == "scroll_up" else -1
            self._next_scroll = 0.0
        else:
            self._clicks.append(action)

    def _resync(self):
        x, y = cursor_position()
        self._cursor.x = float(x)
        self._cursor.y = float(y)
        self._cursor.tx = float(x)
        self._cursor.ty = float(y)
        self._cursor.vx = 0.0
        self._cursor.vy = 0.0
        self._cursor.locked = False

    def _restore_native(self):
        if native_cursor.hidden():
            try:
                native_cursor.restore()
            except Exception:
                self._log.exception("error while restoring the system cursor")

    def _toggle_ball_cursor(self):
        if self._dialog_open:
            return
        if self._ball_on:
            self._ball_on = False
            try:
                self._overlay.set_visible(False)
            except Exception:
                self._log.exception("error while hiding the cursor overlay")
            self._restore_native()
        else:
            self._ball_on = True
            self._resync()
            try:
                self._overlay.set_visible(True)
            except Exception:
                self._log.exception("error while showing the cursor overlay")
            try:
                native_cursor.hide()
            except Exception:
                self._log.exception("error while hiding the system cursor")

    def _on_emergency(self, name):
        if name == "toggle_cursor":
            self._ops.append(self._toggle_ball_cursor)
        elif name == "quit":
            self._ops.append(self._quit)

    def _open_settings(self):
        if self._dialog_open:
            return
        self._dialog_open = True
        self._scroll_vk = None
        self._scroll_dir = 0
        self._clicks.clear()
        try:
            self._hook.set_binding_keys([])
        except Exception:
            self._log.exception("error while disabling key tracking")
        self._overlay.hide()
        if native_cursor.hidden():
            try:
                native_cursor.restore()
            except Exception:
                self._log.exception("error while restoring the system cursor")
        settings_view.show_settings(
            self._root,
            self._store,
            self._settings,
            self._apply_settings,
            self._on_settings_closed,
        )

    def _on_settings_closed(self):
        self._dialog_open = False
        self._scroll_vk = None
        self._scroll_dir = 0
        self._clicks.clear()
        try:
            self._hook.set_binding_keys(self._binding_keys())
        except Exception:
            self._log.exception("error while re-enabling key tracking")
        self._resync()
        if self._ball_on:
            try:
                native_cursor.hide()
            except Exception:
                self._log.exception("error while hiding the system cursor")
            try:
                self._overlay.set_visible(True)
            except Exception:
                self._log.exception("error while showing the cursor overlay")

    def _apply_settings(self, new):
        self._settings = new
        self._rev = {vk: action for action, vk in new.bindings.items()}
        try:
            self._magnet.set_enabled(new.magnet_enabled)
        except Exception:
            self._log.exception("error while toggling the magnet")
        self._tray.set_magnet(new.magnet_enabled)
        try:
            set_autostart(new.start_at_login)
        except OSError:
            self._log.exception("failed to update autostart")
        self._resync()

    def _toggle_magnet(self):
        self._settings.magnet_enabled = not self._settings.magnet_enabled
        self._apply_settings(self._settings)
        try:
            self._store.save(self._settings)
        except OSError:
            self._log.exception("failed to save settings")

    def _quit(self):
        self._running = False
        try:
            if self._root.winfo_exists():
                self._root.after(0, self._root.destroy)
        except tk.TclError:
            pass