import ctypes
import ctypes.wintypes as wintypes

from .commons import gdi32, user32

CURSOR_IDS = (
    32512,
    32513,
    32514,
    32515,
    32516,
    32640,
    32641,
    32642,
    32643,
    32644,
    32645,
    32646,
    32648,
    32649,
    32650,
    32651,
)

SPI_SETCURSORS = 0x0057
SPIF_SENDCHANGE = 0x0002

SIZE = 32


class ICONINFO(ctypes.Structure):
    _fields_ = [
        ("fIcon", wintypes.BOOL),
        ("xHotspot", wintypes.DWORD),
        ("yHotspot", wintypes.DWORD),
        ("hbmMask", wintypes.HBITMAP),
        ("hbmColor", wintypes.HBITMAP),
    ]


gdi32.CreateBitmap.restype = wintypes.HBITMAP
gdi32.CreateBitmap.argtypes = [
    ctypes.c_int,
    ctypes.c_int,
    wintypes.UINT,
    wintypes.UINT,
    ctypes.c_void_p,
]
gdi32.DeleteObject.restype = wintypes.BOOL
gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]

user32.CreateIconIndirect.restype = wintypes.HICON
user32.CreateIconIndirect.argtypes = [ctypes.POINTER(ICONINFO)]
user32.SetSystemCursor.restype = wintypes.BOOL
user32.SetSystemCursor.argtypes = [wintypes.HICON, wintypes.DWORD]
user32.SystemParametersInfoW.restype = wintypes.BOOL
user32.SystemParametersInfoW.argtypes = [
    wintypes.UINT,
    wintypes.UINT,
    ctypes.c_void_p,
    wintypes.UINT,
]
user32.DestroyIcon.restype = wintypes.BOOL
user32.DestroyIcon.argtypes = [wintypes.HICON]

_hidden = False


def hidden():
    return _hidden


def _blank_cursor():
    pixels = SIZE * SIZE // 8
    transparent = (ctypes.c_ubyte * pixels)()
    hbm_mask = gdi32.CreateBitmap(SIZE, SIZE, 1, 1, transparent)
    hbm_color = gdi32.CreateBitmap(SIZE, SIZE, 1, 1, transparent)
    if not hbm_mask or not hbm_color:
        if hbm_mask:
            gdi32.DeleteObject(hbm_mask)
        if hbm_color:
            gdi32.DeleteObject(hbm_color)
        raise OSError("failed to create cursor bitmaps")

    info = ICONINFO()
    info.fIcon = False
    info.xHotspot = 0
    info.yHotspot = 0
    info.hbmMask = hbm_mask
    info.hbmColor = hbm_color
    try:
        icon = user32.CreateIconIndirect(ctypes.byref(info))
    finally:
        gdi32.DeleteObject(hbm_mask)
        gdi32.DeleteObject(hbm_color)
    if not icon:
        raise OSError("failed to create blank cursor")
    return icon


def hide():
    global _hidden
    pending = []
    try:
        for cid in CURSOR_IDS:
            icon = _blank_cursor()
            pending.append(icon)
            if not user32.SetSystemCursor(icon, cid):
                raise OSError("failed to replace cursor %d" % cid)
            pending.pop()
    except Exception:
        for icon in pending:
            user32.DestroyIcon(icon)
        try:
            restore()
        except Exception:
            pass
        raise
    _hidden = True


def restore():
    global _hidden
    user32.SystemParametersInfoW(SPI_SETCURSORS, 0, None, SPIF_SENDCHANGE)
    _hidden = False