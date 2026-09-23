import queue
import re
import tkinter as tk
from tkinter import messagebox

from . import model
from .autostart import is_autostart, set_autostart
from .hook import KeyboardHook

COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
POLL_MS = 50

KNOBS = (
    ("sensitivity", 0.5, 12.0, 0.1, "Sensitivity", "%.1f", False),
    ("smoothness", 1, 30, 1, "Smoothness", "%d", True),
    ("cursor_radius", 24, 200, 1, "Cursor radius", "%d", True),
    ("scroll_delta", 10, 200, 10, "Scroll step", "%d", True),
    ("scroll_interval_ms", 40, 400, 10, "Scroll interval, ms", "%d", True),
    ("magnet_capture", 16, 200, 1, "Magnet radius", "%d", True),
    ("magnet_hold", 0, 40, 1, "Snap hold, ms", "%d", True),
)


class SettingsDialog:
    def __init__(self, root, store, base, on_applied, on_closed):
        self._store = store
        self._on_applied = on_applied
        self._on_closed = on_closed
        self._closed = False
        self._capturing = None
        self._events = queue.Queue()
        self.working = model.Settings(base.to_dict())

        self.window = tk.Toplevel(root)
        self.window.title("Keypointer Settings")
        self.window.resizable(False, False)
        self.window.columnconfigure(0, weight=1)
        self.window.protocol("WM_DELETE_WINDOW", self._close)

        self._bind_vars = {}
        self._bind_buttons = {}
        self._knob_vars = {}
        self._build_bindings()
        self._build_status()
        self._build_params()
        self._build_buttons()

        self._hook = KeyboardHook(self._on_key)
        self._hook_ok = self._hook.start()
        self._poll()

    def _build_bindings(self):
        frm = tk.LabelFrame(self.window, text="Activation keys")
        frm.grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 2))
        frm.columnconfigure(1, weight=1)
        for i, action in enumerate(model.ACTIONS):
            tk.Label(frm, text=model.ACTION_NAMES[action], anchor="w").grid(
                row=i, column=0, sticky="w", padx=(10, 6), pady=2
            )
            var = tk.StringVar(value=model._key_name(self.working.bindings[action]))
            tk.Label(frm, textvariable=var, anchor="w").grid(
                row=i, column=1, sticky="w", padx=4, pady=2
            )
            btn = tk.Button(frm, text="Change…", width=12, command=lambda a=action: self._start_capture(a))
            btn.grid(row=i, column=2, sticky="w", padx=(6, 10), pady=2)
            self._bind_vars[action] = var
            self._bind_buttons[action] = btn

    def _build_status(self):
        self._status_var = tk.StringVar(value="")
        tk.Label(self.window, textvariable=self._status_var, fg="#555555", anchor="w").grid(
            row=1, column=0, sticky="ew", padx=12, pady=(2, 2)
        )

    def _build_params(self):
        frm = tk.LabelFrame(self.window, text="Options")
        frm.grid(row=2, column=0, sticky="ew", padx=12, pady=(2, 4))
        frm.columnconfigure(1, weight=1)
        for i, (attr, low, high, res, text, fmt, is_int) in enumerate(KNOBS):
            tk.Label(frm, text=text, anchor="w").grid(
                row=i, column=0, sticky="w", padx=(10, 6), pady=2
            )
            var = tk.StringVar(value=fmt % getattr(self.working, attr))
            tk.Entry(frm, textvariable=var, width=10).grid(
                row=i, column=1, sticky="w", padx=4, pady=2
            )
            self._knob_vars[attr] = var
        row = len(KNOBS)
        self._color_var = tk.StringVar(value=self.working.color)
        tk.Label(frm, text="Cursor color").grid(
            row=row, column=0, sticky="w", padx=(10, 6), pady=2
        )
        tk.Entry(frm, textvariable=self._color_var, width=10).grid(
            row=row, column=1, sticky="w", padx=4, pady=2
        )
        tk.Label(frm, text="#RRGGBB", fg="#888888").grid(
            row=row, column=2, sticky="w", padx=4, pady=2
        )
        row += 1
        self._magnet_var = tk.BooleanVar(value=self.working.magnet_enabled)
        tk.Checkbutton(frm, text="Magnetic snapping to UI elements", variable=self._magnet_var, anchor="w").grid(
            row=row, column=0, columnspan=3, sticky="w", padx=10, pady=2
        )
        row += 1
        self._auto_var = tk.BooleanVar(value=self.working.start_at_login)
        tk.Checkbutton(frm, text="Start with Windows", variable=self._auto_var, anchor="w").grid(
            row=row, column=0, columnspan=3, sticky="w", padx=10, pady=2
        )

    def _build_buttons(self):
        btns = tk.Frame(self.window)
        btns.grid(row=3, column=0, sticky="e", padx=12, pady=(4, 10))
        tk.Button(btns, text="Save", width=12, command=self._save).pack(side="left", padx=4)
        tk.Button(btns, text="Cancel", width=12, command=self._close).pack(side="left", padx=4)

    def _on_key(self, vk, is_up=False, repeat=False):
        self._events.put((vk, is_up, repeat))

    def _poll(self):
        if self._closed:
            return
        try:
            while True:
                vk, is_up, _repeat = self._events.get_nowait()
                if is_up:
                    continue
                if vk is None:
                    self._cancel_capture()
                elif self._capturing is not None:
                    self._handle_capture(vk)
        except queue.Empty:
            pass
        try:
            self.window.after(POLL_MS, self._poll)
        except tk.TclError:
            pass

    def _start_capture(self, action):
        if self._capturing is not None:
            return
        if not self._hook_ok:
            self._status_var.set("Failed to start key capture.")
            return
        self._capturing = action
        for btn in self._bind_buttons.values():
            btn.configure(state="disabled")
        self._status_var.set("Press a key for \"%s\" (Esc to cancel)" % model.ACTION_NAMES[action])
        self._hook.set_capture(True)

    def _handle_capture(self, vk):
        action = self._capturing
        if vk in model.MOVE_KEYS:
            self._cancel_capture()
            messagebox.showwarning("Keypointer", "Arrow keys are reserved for cursor movement.", parent=self.window)
            return
        self.working.bindings[action] = vk
        self._bind_vars[action].set(model._key_name(vk))
        self._cancel_capture()

    def _cancel_capture(self):
        if self._capturing is None:
            return
        self._capturing = None
        try:
            self._hook.set_capture(False)
        except (OSError, tk.TclError):
            pass
        for btn in self._bind_buttons.values():
            btn.configure(state="normal")
        self._status_var.set("")

    def _save(self):
        color = (self._color_var.get() or "").strip()
        if not COLOR_RE.match(color):
            messagebox.showerror("Keypointer", "Invalid color. Format: #RRGGBB", parent=self.window)
            return
        for attr, low, high, _res, text, _fmt, is_int in KNOBS:
            raw = (self._knob_vars[attr].get() or "").strip()
            try:
                value = int(raw) if is_int else float(raw)
            except ValueError:
                messagebox.showerror("Keypointer", "Invalid value: %s" % text, parent=self.window)
                return
            if value < low or value > high:
                messagebox.showerror("Keypointer", "Value \"%s\" is out of range." % text, parent=self.window)
                return
            setattr(self.working, attr, value)
        self.working.color = color.lower()
        self.working.magnet_enabled = bool(self._magnet_var.get())
        self.working.start_at_login = bool(self._auto_var.get())
        self._apply_autostart()
        new = self.working.clone()
        try:
            self._store.save(new)
        except OSError:
            messagebox.showerror("Keypointer", "Failed to save settings.", parent=self.window)
            return
        if self._on_applied is not None:
            self._on_applied(new)
        self._close()

    def _apply_autostart(self):
        desired = bool(self._auto_var.get())
        try:
            if desired != is_autostart():
                set_autostart(desired)
        except OSError:
            messagebox.showwarning("Keypointer", "Failed to change autostart.", parent=self.window)

    def _close(self):
        if self._closed:
            return
        self._closed = True
        if self._capturing is not None:
            try:
                self._hook.set_capture(False)
            except (OSError, tk.TclError):
                pass
            self._capturing = None
        try:
            self._hook.stop()
        except Exception:
            pass
        try:
            if self.window.winfo_exists():
                self.window.destroy()
        except tk.TclError:
            pass
        if self._on_closed is not None:
            self._on_closed()


def show_settings(root, store, base, on_applied, on_closed):
    dlg = SettingsDialog(root, store, base, on_applied, on_closed)
    try:
        dlg.window.transient(root)
    except tk.TclError:
        pass
    try:
        dlg.window.grab_set()
    except tk.TclError:
        pass
    dlg.window.focus_set()
    root.wait_window(dlg.window)