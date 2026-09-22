import argparse
import importlib.metadata as metadata
import logging
import os
import sys
import tempfile
import tkinter as tk

from keypointer import app, commons, model

CHECK_LOG = os.path.join(tempfile.gettempdir(), "keypointer_check.log")

MODULES = (
    "keypointer",
    "keypointer.art",
    "keypointer.autostart",
    "keypointer.commons",
    "keypointer.hook",
    "keypointer.magnet",
    "keypointer.model",
    "keypointer.mouse",
    "keypointer.overlay",
    "keypointer.settings_view",
    "keypointer.tray",
    "keypointer.app",
)


def run_checks():
    lines = ["Keypointer checks"]
    for name in MODULES:
        try:
            __import__(name)
            lines.append("%s: OK" % name)
        except Exception as exc:
            lines.append("%s: FAIL: %s" % (name, exc))
    try:
        import pystray
        import PIL

        lines.append("pystray: %s" % metadata.version("pystray"))
        lines.append("Pillow: %s" % metadata.version("Pillow"))
    except Exception as exc:
        lines.append("deps: FAIL: %s" % exc)
    with open(CHECK_LOG, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    print("\n".join(lines))
    bad = [line for line in lines if "FAIL" in line]
    return 1 if bad else 0


def main():
    parser = argparse.ArgumentParser(description="Keypointer")
    parser.add_argument("--check", action="store_true", help="run checks and exit")
    args = parser.parse_args()
    if args.check:
        return run_checks()
    guard = commons.SingleInstance("KeypointerLocal")
    if not guard.owned:
        print("Keypointer is already running")
        return 1
    commons.set_dpi_awareness()
    commons.configure_logging()
    logger = logging.getLogger("main")
    logger.info("Keypointer starting")
    root = tk.Tk()
    root.withdraw()
    instance = None
    try:
        instance = app.App(root, model.SettingsStore())
        instance.start()
        root.mainloop()
    finally:
        if instance is not None:
            instance.stop()
        guard.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())