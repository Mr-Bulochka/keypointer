# Keypointer

Control your mouse cursor and clicks entirely from the keyboard.

Keypointer runs quietly in the background — no main window, just a tray icon in the
Windows notification area. It glides the cursor with the arrow keys, performs clicks
and scrolling via global hotkeys, and ships with a **Magnet** mode that gently snaps
the cursor to interactive elements under it.

## Download

Grab the latest `Keypointer.exe` from the [Releases](https://github.com/<your-username>/keypointer/releases)
page — no installation required, just run it. Or build it yourself (see below).

## Features

- **Smooth arrow-key movement** — inertia-based cursor gliding with adjustable sensitivity.
- **Global hotkeys** for clicks and scrolling — fully remappable in the settings window.
- **Cursor overlay** — a colored ring with a soft trail highlights the current cursor position.
- **Magnet mode** — the cursor lightly "sticks" to buttons and UI elements, making precise hits much easier.
- **Tray icon** with a complete settings window.
- Settings persist in `%APPDATA%\Keypointer\settings.json`.

## Requirements

- Windows 7/8/10/11 (32- or 64-bit).
- Python 3.9+ with `Pillow` and `pystray` — **only** needed to run from source.

## Getting started

### Ready-made EXE

Run `dist\Keypointer.exe`. The app starts immediately in the tray; no windows appear
on launch.

### From source

```powershell
pip install -r requirements.txt
python main.py
```

### Build your own EXE

```powershell
build.bat
```

The script verifies Python, regenerates the icon, installs dependencies and
PyInstaller, then produces a single-file `dist\Keypointer.exe`.

### Quick environment self-check

```powershell
python main.py --check
```

Prints the import status of every module and the versions of `pystray` and `Pillow`.
Exits with code `1` if any check fails. A full log is written to
`%TEMP%\keypointer_check.log`.

## Default controls

| Key       | Action          |
|-----------|-----------------|
| Arrows    | Move the cursor |
| Insert    | Left click      |
| Delete    | Right click     |
| Home      | Double click    |
| End       | Middle click    |
| PageUp    | Scroll up       |
| PageDown  | Scroll down     |

Notes:

- Scrolling repeats while the key is held down.
- Pressing `Ctrl`, `Alt`, `Shift` or `Win` together with a scroll key cancels the
  scroll (modifier presses are never blocked and never treated as scrolling).
- Clicks are performed at the current cursor position.

## Tray icon

- **Settings…** — opens the settings window (double-clicking the icon also works).
- **Magnet: on / Magnet: off** — toggles Magnet mode instantly (state is saved).
- **Quit** — exits the application.

The settings window lets you remap hotkeys, tune movement sensitivity and
smoothness, change the overlay radius and color, adjust scrolling and magnet
parameters, and enable auto-start with Windows.

## Settings file

Path: `%APPDATA%\Keypointer\settings.json`

The file is created on the first settings save (e.g. toggling Magnet from the tray
or changing options in the settings window). On first run, built-in defaults are
used and the file is optional.

| Key                   | Default      | Description                                    |
|-----------------------|--------------|------------------------------------------------|
| `bindings`            | (see above)  | `action → virtual key code` mapping            |
| `sensitivity`         | `2.0`        | Movement sensitivity (0.5–4.0)                 |
| `smoothness`          | `6.0`        | Smoothness / inertia (1.0–30.0)                |
| `cursor_radius`       | `32`         | Overlay ring radius (24–200)                   |
| `color`               | `#ff66c4`    | Overlay color                                  |
| `scroll_delta`        | `40`         | Scroll amount per step (10–200)                |
| `scroll_interval_ms`  | `120`        | Scroll repeat interval in ms (40–400)          |
| `magnet_enabled`      | `true`       | Magnet mode enabled                            |
| `magnet_capture`      | `56`         | Target capture radius in px (16–200)           |
| `magnet_hold`         | `10`         | Extra hold radius in px (0–40)                 |
| `start_at_login`      | `false`      | Auto-start with Windows                        |

## Limitations

- Only one instance at a time: a second launch prints `Keypointer is already running`
  and exits.
- Global keyboard input uses a low-level Windows hook; behavior may differ when run
  as administrator (`UseRawInputLL`).