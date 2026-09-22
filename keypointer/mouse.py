import ctypes
import time

from .commons import (
    INPUT,
    INPUT_MOUSE,
    MOUSEEVENTF_ABSOLUTE,
    MOUSEEVENTF_LEFTDOWN,
    MOUSEEVENTF_LEFTUP,
    MOUSEEVENTF_MIDDLEDOWN,
    MOUSEEVENTF_MIDDLEUP,
    MOUSEEVENTF_MOVE,
    MOUSEEVENTF_RIGHTDOWN,
    MOUSEEVENTF_RIGHTUP,
    MOUSEEVENTF_VIRTUALDESK,
    MOUSEEVENTF_WHEEL,
    MOUSEINPUT,
    user32,
    virtual_screen,
)


def _send_mouse(flags, dx=0, dy=0, data=0):
    mouse_input = MOUSEINPUT(dx, dy, data, flags, 0, 0)
    inp = INPUT(type=INPUT_MOUSE, mi=mouse_input)
    user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))


def move_to(x, y):
    left, top, width, height = virtual_screen()
    if width <= 0 or height <= 0:
        return
    nx = int(round((x - left) * 65535.0 / width))
    ny = int(round((y - top) * 65535.0 / height))
    nx = max(0, min(65535, nx))
    ny = max(0, min(65535, ny))
    _send_mouse(MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK, nx, ny)


def _click_pair(down_flag, up_flag):
    _send_mouse(down_flag)
    time.sleep(0.01)
    _send_mouse(up_flag)


def left_click():
    _click_pair(MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP)


def right_click():
    _click_pair(MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP)


def middle_click():
    _click_pair(MOUSEEVENTF_MIDDLEDOWN, MOUSEEVENTF_MIDDLEUP)


def double_click_left():
    _click_pair(MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP)
    time.sleep(0.03)
    _click_pair(MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP)


def scroll(delta):
    _send_mouse(MOUSEEVENTF_WHEEL, data=int(delta))