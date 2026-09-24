import ctypes
import ctypes.wintypes as wintypes
import logging
import threading

from .commons import (
    AC_SRC_ALPHA,
    AC_SRC_OVER,
    BI_RGB,
    BITMAPINFO,
    BITMAPINFOHEADER,
    BLENDFUNCTION,
    DIB_RGB_COLORS,
    ULW_ALPHA,
    WM_APP_HIDE,
    WM_APP_QUIT,
    WM_APP_RENDER,
    WM_APP_SHOW,
    WM_DESTROY,
    SWP_NOACTIVATE,
    SWP_SHOWWINDOW,
    WS_EX_LAYERED,
    WS_EX_NOACTIVATE,
    WS_EX_TOOLWINDOW,
    WS_EX_TOPMOST,
    WS_EX_TRANSPARENT,
    WS_POPUP,
    gdi32,
    kernel32,
    user32,
)

WM_NCHITTEST = 0x0084
HTTRANSPARENT = -1
SW_HIDE = 0
SW_SHOWNOACTIVATE = 4
HWND_TOPMOST = -1
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001

_log = logging.getLogger("overlay")


def _api_error():
    code = kernel32.GetLastError()
    if not code:
        return f"error {code}"
    try:
        return f"{ctypes.WinError(code)}"
    except OSError:
        return f"error {code}"


class SIZE(ctypes.Structure):
    _fields_ = [("cx", ctypes.c_long), ("cy", ctypes.c_long)]


WNDPROC = ctypes.WINFUNCTYPE(
    ctypes.c_ssize_t, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM
)


class WNDCLASS(ctypes.Structure):
    _fields_ = [
        ("style", wintypes.UINT),
        ("lpfnWndProc", WNDPROC),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", wintypes.HINSTANCE),
        ("hIcon", wintypes.HICON),
        ("hCursor", ctypes.c_void_p),
        ("hbrBackground", wintypes.HBRUSH),
        ("lpszMenuName", wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR),
    ]


user32.RegisterClassW.restype = wintypes.ATOM
user32.RegisterClassW.argtypes = [ctypes.POINTER(WNDCLASS)]
user32.UnregisterClassW.restype = wintypes.BOOL
user32.UnregisterClassW.argtypes = [wintypes.LPCWSTR, wintypes.HINSTANCE]
user32.CreateWindowExW.restype = wintypes.HWND
user32.CreateWindowExW.argtypes = [
    wintypes.DWORD,
    wintypes.LPCWSTR,
    wintypes.LPCWSTR,
    wintypes.DWORD,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    wintypes.HWND,
    wintypes.HMENU,
    wintypes.HINSTANCE,
    ctypes.c_void_p,
]
user32.PostMessageW.restype = wintypes.BOOL
user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.PostQuitMessage.restype = None
user32.PostQuitMessage.argtypes = [ctypes.c_int]
user32.GetMessageW.restype = ctypes.c_int
user32.GetMessageW.argtypes = [
    ctypes.POINTER(wintypes.MSG),
    wintypes.HWND,
    wintypes.UINT,
    wintypes.UINT,
]
user32.TranslateMessage.restype = wintypes.BOOL
user32.TranslateMessage.argtypes = [ctypes.POINTER(wintypes.MSG)]
user32.DispatchMessageW.restype = ctypes.c_ssize_t
user32.DispatchMessageW.argtypes = [ctypes.POINTER(wintypes.MSG)]
user32.UpdateLayeredWindow.restype = wintypes.BOOL
user32.UpdateLayeredWindow.argtypes = [
    wintypes.HWND,
    wintypes.HDC,
    ctypes.POINTER(wintypes.POINT),
    ctypes.POINTER(SIZE),
    wintypes.HDC,
    ctypes.POINTER(wintypes.POINT),
    wintypes.COLORREF,
    ctypes.POINTER(BLENDFUNCTION),
    wintypes.DWORD,
]
user32.SetWindowPos.restype = wintypes.BOOL
user32.SetWindowPos.argtypes = [
    wintypes.HWND,
    wintypes.HWND,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    wintypes.UINT,
]
gdi32.CreateCompatibleDC.restype = wintypes.HDC
gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
gdi32.DeleteDC.restype = wintypes.BOOL
gdi32.DeleteDC.argtypes = [wintypes.HDC]
gdi32.SelectObject.restype = ctypes.c_void_p
gdi32.SelectObject.argtypes = [wintypes.HDC, ctypes.c_void_p]
gdi32.DeleteObject.restype = wintypes.BOOL
gdi32.DeleteObject.argtypes = [ctypes.c_void_p]
gdi32.CreateDIBSection.restype = ctypes.c_void_p
gdi32.CreateDIBSection.argtypes = [
    wintypes.HDC,
    ctypes.POINTER(BITMAPINFO),
    wintypes.UINT,
    ctypes.POINTER(ctypes.c_void_p),
    ctypes.c_void_p,
    wintypes.DWORD,
]


class CursorOverlay:
    def __init__(self):
        self._lock = threading.Lock()
        self._img = bytearray()
        self._thread = None
        self._ready = None
        self._hwnd = None
        self._hdc = None
        self._dib = None
        self._old_obj = None
        self._bits = None
        self._size = (0, 0)
        self._hidden = False

    def start(self):
        if self._thread:
            return self._hwnd is not None
        self._ready = threading.Event()
        self._thread = threading.Thread(target=self._run, name="cursor-overlay", daemon=True)
        self._thread.start()
        self._ready.wait(timeout=5.0)
        return self._hwnd is not None

    def render(self, data, left, top, size):
        if size <= 0 or not data:
            return
        count = size * size * 4
        buf = bytearray(count)
        n = min(len(data), count)
        buf[:n] = data[:n]
        with self._lock:
            self._img = buf
            hwnd = self._hwnd
        if hwnd:
            user32.PostMessageW(
                hwnd,
                WM_APP_RENDER,
                (size << 16) | size,
                ((left & 0xFFFF) << 16) | (top & 0xFFFF),
            )

    def hide(self):
        with self._lock:
            hwnd = self._hwnd
        if hwnd:
            user32.PostMessageW(hwnd, WM_APP_HIDE, 0, 0)

    def alive(self):
        with self._lock:
            return self._hwnd is not None

    def set_visible(self, visible):
        with self._lock:
            hwnd = self._hwnd
        if not hwnd:
            return
        if visible:
            user32.PostMessageW(hwnd, WM_APP_SHOW, 0, 0)
        else:
            user32.PostMessageW(hwnd, WM_APP_HIDE, 0, 0)

    def stop(self):
        with self._lock:
            hwnd = self._hwnd
        if hwnd:
            user32.PostMessageW(hwnd, WM_APP_QUIT, 0, 0)
        thread = self._thread
        if thread:
            thread.join(timeout=2.0)
            self._thread = None

    def _run(self):
        hinst = kernel32.GetModuleHandleW(None)
        wndclass = WNDCLASS()
        wndclass.lpfnWndProc = WNDPROC(self._wnd_proc)
        wndclass.hInstance = hinst
        wndclass.lpszClassName = "KeypointerCursorOverlay"
        atom = user32.RegisterClassW(ctypes.byref(wndclass))
        if not atom:
            _log.error("overlay: RegisterClassW failed, err=%s", _api_error())
            self._ready.set()
            return
        hwnd = user32.CreateWindowExW(
            WS_EX_TOPMOST | WS_EX_TOOLWINDOW | WS_EX_LAYERED
            | WS_EX_TRANSPARENT | WS_EX_NOACTIVATE,
            "KeypointerCursorOverlay",
            "",
            WS_POPUP,
            -32000, -32000, 1, 1,
            None, None, hinst, None,
        )
        with self._lock:
            self._hwnd = hwnd
        self._ready.set()
        if not hwnd:
            _log.error("overlay: CreateWindowExW failed, err=%s", _api_error())
            user32.UnregisterClassW("KeypointerCursorOverlay", hinst)
            return
        try:
            msg = wintypes.MSG()
            while True:
                res = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
                if res <= 0:
                    break
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
        finally:
            with self._lock:
                self._hwnd = None
            self._release_dib()
            user32.UnregisterClassW("KeypointerCursorOverlay", hinst)

    def _wnd_proc(self, hwnd, msg, wparam, lparam):
        if msg == WM_APP_RENDER:
            try:
                w = (wparam >> 16) & 0xFFFF
                h = wparam & 0xFFFF
                left = ctypes.c_short((lparam >> 16) & 0xFFFF).value
                top = ctypes.c_short(lparam & 0xFFFF).value
                with self._lock:
                    img = self._img
                self._ensure_dib(w, h)
                if self._bits:
                    ctypes.memmove(self._bits, img, min(len(img), w * h * 4))
                    blend = BLENDFUNCTION(AC_SRC_OVER, 0, 255, AC_SRC_ALPHA)
                    src = wintypes.POINT(0, 0)
                    dst = wintypes.POINT(left, top)
                    size = SIZE(w, h)
                    ok = user32.UpdateLayeredWindow(
                        hwnd,
                        None,
                        ctypes.byref(dst),
                        ctypes.byref(size),
                        self._hdc,
                        ctypes.byref(src),
                        0,
                        ctypes.byref(blend),
                        ULW_ALPHA,
                    )
                    if not ok:
                        _log.warning(
                            "overlay: UpdateLayeredWindow failed, err=%s", _api_error()
                        )
                    elif not self._hidden:
                        if not user32.SetWindowPos(
                            hwnd,
                            HWND_TOPMOST,
                            0, 0, 0, 0,
                            SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_SHOWWINDOW,
                        ):
                            _log.warning(
                                "overlay: SetWindowPos failed, err=%s", _api_error()
                            )
            except Exception:
                _log.exception("overlay: error in WM_APP_RENDER handler")
                return 0
            return 0
        if msg == WM_APP_SHOW:
            self._hidden = False
            user32.ShowWindow(hwnd, SW_SHOWNOACTIVATE)
            return 0
        if msg == WM_APP_HIDE:
            self._hidden = True
            user32.ShowWindow(hwnd, SW_HIDE)
            return 0
        if msg == WM_APP_QUIT:
            user32.DestroyWindow(hwnd)
            return 0
        if msg == WM_NCHITTEST:
            return HTTRANSPARENT
        if msg == WM_DESTROY:
            user32.PostQuitMessage(0)
            return 0
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def _ensure_dib(self, w, h):
        if self._dib and self._size == (w, h):
            return
        self._release_dib()
        header = BITMAPINFOHEADER()
        header.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        header.biWidth = int(w)
        header.biHeight = -int(h)
        header.biPlanes = 1
        header.biBitCount = 32
        header.biCompression = BI_RGB
        bmi = BITMAPINFO()
        bmi.bmiHeader = header
        bits = ctypes.c_void_p()
        dib = gdi32.CreateDIBSection(
            None, ctypes.byref(bmi), DIB_RGB_COLORS, ctypes.byref(bits), None, 0
        )
        if not dib:
            _log.error("overlay: CreateDIBSection failed, err=%s", _api_error())
            return
        hdc = gdi32.CreateCompatibleDC(None)
        if not hdc:
            _log.error("overlay: CreateCompatibleDC failed, err=%s", _api_error())
            gdi32.DeleteObject(dib)
            return
        old = gdi32.SelectObject(hdc, dib)
        self._dib = dib
        self._hdc = hdc
        self._old_obj = old
        self._bits = bits
        self._size = (w, h)

    def _release_dib(self):
        if self._hdc:
            if self._old_obj:
                gdi32.SelectObject(self._hdc, self._old_obj)
            gdi32.DeleteDC(self._hdc)
        if self._dib:
            gdi32.DeleteObject(self._dib)
        self._hdc = None
        self._dib = None
        self._old_obj = None
        self._bits = None
        self._size = (0, 0)