import os
import sys
import winreg

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "Keypointer"


def _command(app_path=None):
    if getattr(sys, "frozen", False):
        return '"%s"' % sys.executable
    script = app_path or os.path.abspath(sys.argv[0])
    if not script.lower().endswith((".py", ".pyw")):
        script = os.path.abspath(__file__)
    return '"%s" "%s"' % (sys.executable, script)


def set_autostart(enabled, app_path=None):
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE)
    except OSError:
        key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY)
    try:
        if enabled:
            winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, _command(app_path))
        else:
            try:
                winreg.DeleteValue(key, VALUE_NAME)
            except OSError:
                pass
    finally:
        winreg.CloseKey(key)


def is_autostart():
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_READ)
    except OSError:
        return False
    try:
        try:
            winreg.QueryValueEx(key, VALUE_NAME)
            return True
        except OSError:
            return False
    finally:
        winreg.CloseKey(key)