import ctypes
import ctypes.wintypes as wintypes
import threading

from .commons import (
    KBDLLHOOKSTRUCT,
    LLKHF_UP,
    VK_CONTROL,
    VK_ESCAPE,
    VK_MENU,
    VK_SHIFT,
    WH_KEYBOARD_LL,
    WM_QUIT,
    kernel32,
    user32,
)

LOW_LEVEL_KEYBOARD_PROC = ctypes.WINFUNCTYPE(
    ctypes.c_ssize_t, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM
)

user32.SetWindowsHookExW.restype = ctypes.c_void_p
user32.SetWindowsHookExW.argtypes = [
    ctypes.c_int,
    LOW_LEVEL_KEYBOARD_PROC,
    ctypes.c_void_p,
    wintypes.DWORD,
]
user32.CallNextHookEx.restype = ctypes.c_ssize_t
user32.CallNextHookEx.argtypes = [
    ctypes.c_void_p,
    ctypes.c_int,
    wintypes.WPARAM,
    wintypes.LPARAM,
]
user32.UnhookWindowsHookEx.restype = wintypes.BOOL
user32.UnhookWindowsHookEx.argtypes = [ctypes.c_void_p]
user32.PostThreadMessageW.restype = wintypes.BOOL
user32.PostThreadMessageW.argtypes = [
    wintypes.DWORD,
    wintypes.UINT,
    wintypes.WPARAM,
    wintypes.LPARAM,
]
user32.GetMessageW.restype = ctypes.c_int
user32.GetMessageW.argtypes = [
    ctypes.POINTER(wintypes.MSG),
    wintypes.HWND,
    wintypes.UINT,
    wintypes.UINT,
]

MODIFIERS = (VK_CONTROL, VK_MENU, VK_SHIFT)
EMERGENCY_KEYS = {0x4B: "toggle_cursor", 0x51: "quit"}


class KeyboardHook:
    def __init__(self, on_key):
        self._on_key = on_key
        self._proc = None
        self._handle = None
        self._thread = None
        self._thread_id = 0
        self._watch = set()
        self._held = set()
        self._mods = set()
        self._capturing = False
        self._movers = set()
        self._emergency = None
        self._lock = threading.Lock()

    def set_binding_keys(self, keys):
        with self._lock:
            self._watch = set(keys)

    def set_capture(self, capturing):
        with self._lock:
            self._capturing = bool(capturing)

    def set_mover_keys(self, keys):
        with self._lock:
            self._movers = set(keys)

    def set_emergency(self, handler):
        with self._lock:
            self._emergency = handler

    def start(self):
        if self._thread:
            return self._handle is not None
        self._ready = threading.Event()
        self._thread = threading.Thread(target=self._run, name="keyboard-hook", daemon=True)
        self._thread.start()
        self._ready.wait(timeout=5.0)
        return self._handle is not None

    def stop(self):
        handle = self._handle
        self._handle = None
        if handle:
            user32.UnhookWindowsHookEx(handle)
        if self._thread_id:
            user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)
        thread = self._thread
        if thread:
            thread.join(timeout=2.0)
            self._thread = None

    def _run(self):
        self._thread_id = kernel32.GetCurrentThreadId()
        proc = self._proc = LOW_LEVEL_KEYBOARD_PROC(self._callback)
        hmod = kernel32.GetModuleHandleW(None)
        self._handle = user32.SetWindowsHookExW(WH_KEYBOARD_LL, proc, hmod, 0)
        self._ready.set()
        if not self._handle:
            return
        try:
            msg = wintypes.MSG()
            while True:
                res = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
                if res <= 0:
                    break
        finally:
            handle = self._handle
            self._handle = None
            if handle:
                user32.UnhookWindowsHookEx(handle)

    def _callback(self, n_code, w_param, l_param):
        try:
            if n_code == 0:
                info = ctypes.cast(l_param, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
                vk = int(info.vkCode)
                is_up = bool(info.flags & LLKHF_UP)
                repeat = int(vk in self._held)
                if not is_up:
                    self._held.add(vk)
                else:
                    self._held.discard(vk)
                if vk in MODIFIERS:
                    if is_up:
                        self._mods.discard(vk)
                    else:
                        self._mods.add(vk)
                    return user32.CallNextHookEx(self._handle, n_code, w_param, l_param)
                if vk in (0x5B, 0x5C):
                    return user32.CallNextHookEx(self._handle, n_code, w_param, l_param)
                with self._lock:
                    capturing = self._capturing
                    watch = self._watch
                    movers = self._movers
                    emergency = self._emergency
                passthrough = bool(self._mods)
                callback = self._on_key
                if vk in EMERGENCY_KEYS and VK_CONTROL in self._mods and VK_MENU in self._mods:
                    if emergency is None:
                        return user32.CallNextHookEx(self._handle, n_code, w_param, l_param)
                    if not is_up and repeat == 0:
                        emergency(EMERGENCY_KEYS[vk])
                    return 1
                if capturing:
                    if passthrough:
                        return user32.CallNextHookEx(self._handle, n_code, w_param, l_param)
                    if vk == VK_ESCAPE:
                        if not is_up:
                            callback(None)
                        return 1
                    if not is_up:
                        callback(vk, False, False)
                    return 1
                if vk in movers:
                    if (
                        user32.GetAsyncKeyState(0x5B) & 0x8000
                        or user32.GetAsyncKeyState(0x5C) & 0x8000
                    ):
                        return user32.CallNextHookEx(self._handle, n_code, w_param, l_param)
                    return 1
                if vk in watch:
                    if passthrough:
                        return user32.CallNextHookEx(self._handle, n_code, w_param, l_param)
                    if repeat == 0:
                        callback(vk, is_up, False)
                    return 1
        except Exception:
            pass
        return user32.CallNextHookEx(self._handle, n_code, w_param, l_param)