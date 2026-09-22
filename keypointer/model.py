import json
import math
import os
from dataclasses import dataclass

from .commons import appdata_dir, cursor_position, virtual_screen

ACTIONS = ("left_click", "right_click", "double_click", "middle_click", "scroll_up", "scroll_down")

ACTION_NAMES = {
    "left_click": "Left button",
    "right_click": "Right button",
    "double_click": "Double click",
    "middle_click": "Middle button",
    "scroll_up": "Scroll up",
    "scroll_down": "Scroll down",
}

DEFAULT_BINDINGS = {
    "left_click": 0x2D,
    "right_click": 0x2E,
    "double_click": 0x24,
    "middle_click": 0x23,
    "scroll_up": 0x21,
    "scroll_down": 0x22,
}

MOVE_KEYS = (0x25, 0x26, 0x27, 0x28)

KEY_NAMES = {
    0x08: "Backspace",
    0x09: "Tab",
    0x0D: "Enter",
    0x1B: "Esc",
    0x20: "Space",
    0x21: "PageUp",
    0x22: "PageDown",
    0x23: "End",
    0x24: "Home",
    0x25: "Left arrow",
    0x26: "Up arrow",
    0x27: "Right arrow",
    0x28: "Down arrow",
    0x2D: "Insert",
    0x2E: "Delete",
    0x90: "NumLock",
    0x91: "ScrollLock",
}


def _key_name(vk):
    if vk in KEY_NAMES:
        return KEY_NAMES[vk]
    if 0x30 <= vk <= 0x39:
        return chr(vk)
    if 0x41 <= vk <= 0x5A:
        return chr(vk)
    if 0x70 <= vk <= 0x87:
        return "F%d" % (vk - 0x70 + 1)
    return "Key %d" % vk


def _clamp(value, low, high):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return float(low)
    return max(float(low), min(float(high), value))


def _clamp_int(value, low, high):
    return int(_clamp(value, low, high))


class Settings:
    def __init__(self, data=None):
        data = data if isinstance(data, dict) else {}
        self.bindings = dict(DEFAULT_BINDINGS)
        raw_bindings = data.get("bindings")
        if isinstance(raw_bindings, dict):
            for action in ACTIONS:
                vk = raw_bindings.get(action)
                if isinstance(vk, int) and 1 <= vk < 256:
                    self.bindings[action] = vk
        self.sensitivity = _clamp(data.get("sensitivity", 2.0), 0.5, 4.0)
        self.smoothness = _clamp(data.get("smoothness", 6.0), 1.0, 30.0)
        self.cursor_radius = _clamp_int(data.get("cursor_radius", 32), 24, 200)
        color = data.get("color", "#ff66c4")
        self.color = color if isinstance(color, str) and color else "#ff66c4"
        self.scroll_delta = _clamp_int(data.get("scroll_delta", 40), 10, 200)
        self.scroll_interval_ms = _clamp_int(data.get("scroll_interval_ms", 120), 40, 400)
        self.magnet_enabled = bool(data.get("magnet_enabled", True))
        self.magnet_capture = _clamp_int(data.get("magnet_capture", 56), 16, 200)
        self.magnet_hold = _clamp_int(data.get("magnet_hold", 10), 0, 40)
        self.start_at_login = bool(data.get("start_at_login", False))

    def to_dict(self):
        return {
            "bindings": dict(self.bindings),
            "sensitivity": self.sensitivity,
            "smoothness": self.smoothness,
            "cursor_radius": self.cursor_radius,
            "color": self.color,
            "scroll_delta": self.scroll_delta,
            "scroll_interval_ms": self.scroll_interval_ms,
            "magnet_enabled": self.magnet_enabled,
            "magnet_capture": self.magnet_capture,
            "magnet_hold": self.magnet_hold,
            "start_at_login": self.start_at_login,
        }

    def clone(self):
        return Settings(self.to_dict())


class SettingsStore:
    def __init__(self, path=None):
        self.path = path or os.path.join(appdata_dir(), "settings.json")

    def load(self):
        try:
            with open(self.path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if not isinstance(data, dict):
                data = {}
        except (OSError, ValueError):
            data = {}
        return Settings(data)

    def save(self, settings):
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(settings.to_dict(), fh, ensure_ascii=False, indent=2)
        os.replace(tmp, self.path)


@dataclass
class SnapTarget:
    cx: float
    cy: float
    half_diag: float
    dist: float


SPEED = 600.0


class CursorModel:
    def __init__(self):
        x, y = cursor_position()
        self.x = float(x)
        self.y = float(y)
        self.tx = self.x
        self.ty = self.y
        self.vx = 0.0
        self.vy = 0.0
        self.pulse = 0.0
        self.locked = False
        self.lock_cx = 0.0
        self.lock_cy = 0.0
        self.lock_radius = 0.0

    def cursor_pos(self):
        return self.x, self.y

    def update(self, dt, axis_x, axis_y, snap, settings):
        k = 1.0 - math.exp(-dt * settings.smoothness)
        left, top, width, height = virtual_screen()
        target_vx = axis_x * settings.sensitivity * SPEED
        target_vy = axis_y * settings.sensitivity * SPEED
        self.vx += (target_vx - self.vx) * k
        self.vy += (target_vy - self.vy) * k
        self.tx += self.vx * dt
        self.ty += self.vy * dt
        self.tx = max(float(left), min(float(left + width), self.tx))
        self.ty = max(float(top), min(float(top + height), self.ty))
        if snap is not None and not self.locked and snap.dist <= settings.magnet_capture:
            self.locked = True
            self.lock_cx = snap.cx
            self.lock_cy = snap.cy
            self.lock_radius = min(max(snap.half_diag, 0.0), 120.0) + settings.magnet_hold
        if self.locked:
            fx = self.tx + self.vx * 0.2
            fy = self.ty + self.vy * 0.2
            if math.hypot(fx - self.lock_cx, fy - self.lock_cy) > self.lock_radius:
                self.locked = False
        dest_x = self.lock_cx if self.locked else self.tx
        dest_y = self.lock_cy if self.locked else self.ty
        self.x += (dest_x - self.x) * k
        self.y += (dest_y - self.y) * k
        self.pulse = max(0.0, self.pulse - dt * 4.0)