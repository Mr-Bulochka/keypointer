import logging
import threading

import pystray

from .art import draw_tray_icon

MENU_SETTINGS = "Settings…"
MENU_QUIT = "Quit"


class Tray:
    def __init__(self, on_settings, on_toggle_magnet, on_quit):
        self._on_settings = on_settings
        self._on_toggle_magnet = on_toggle_magnet
        self._on_quit = on_quit
        self._magnet_enabled = True
        self._icon = None
        self._thread = None
        self._log = logging.getLogger("tray")

    def start(self):
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._run, name="tray", daemon=True)
        self._thread.start()

    def stop(self):
        icon = self._icon
        if icon is not None:
            try:
                icon.stop()
            except Exception:
                pass
        thread = self._thread
        if thread is not None:
            thread.join(timeout=2.0)
            self._thread = None

    def set_magnet(self, enabled):
        self._magnet_enabled = bool(enabled)
        icon = self._icon
        if icon is not None:
            try:
                icon.update_menu()
            except Exception:
                pass

    def _magnet_label(self, item=None):
        return "Magnet: " + ("on" if self._magnet_enabled else "off")

    def _run(self):
        menu = pystray.Menu(
            pystray.MenuItem(MENU_SETTINGS, self._on_menu_settings, default=True),
            pystray.MenuItem(self._magnet_label, self._on_menu_toggle_magnet),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(MENU_QUIT, self._on_menu_quit),
        )
        icon = pystray.Icon("keypointer", draw_tray_icon(64), "Keypointer", menu)
        self._icon = icon
        try:
            icon.run_detached()
            icon.visible = True
        except Exception:
            self._log.exception("error while starting the tray icon")

    def _on_menu_settings(self, icon, item):
        self._safe(self._on_settings)

    def _on_menu_toggle_magnet(self, icon, item):
        self._safe(self._on_toggle_magnet)

    def _on_menu_quit(self, icon, item):
        self._safe(self._on_quit)

    @staticmethod
    def _safe(fn):
        try:
            fn()
        except Exception:
            pass