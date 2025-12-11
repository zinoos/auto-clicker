# Advanced Auto-Clicker Toolkit

A Python desktop utility that bundles three automation helpers into one Tkinter GUI:

- **Simple Auto-Clicker**: choose mouse button, set click delay, and toggle via a global hotkey.
- **Macro Recorder**: capture keyboard and mouse actions with timings, then replay them in a loop with a hotkey.
- **Keyboard Auto-Presser**: repeatedly press a chosen key with a configurable delay and hotkey.

## Requirements

- Python 3.9+
- `pynput` and `keyboard` libraries for global input hooks and simulation

> **Linux hotkeys:** The `keyboard` library requires root access (or explicit
> device permissions) to register global hotkeys on many distributions. If
> registration fails, the app will show an error and still allow manual start/stop
> via the on-screen buttons.

Install dependencies:

```bash
pip install pynput keyboard
```

## Running

```bash
python autoclicker_app.py
```

Each tab includes controls for binding global hotkeys; the tools run on background threads so the interface stays responsive. Global hotkeys work even when the window is unfocused.
