"""
Advanced Auto-Clicker & Macro Utility

Dependencies:
    pip install pynput keyboard

Notes:
    - On many Linux distributions, the `keyboard` library requires root
      privileges for global hotkeys. When unavailable, the app now shows
      a clear warning instead of raising an exception.

This script provides a Tkinter-based GUI with multiple tools:
    - Simple Auto-Clicker
    - Macro Recorder
    - Keyboard Auto-Presser

Global hotkeys rely on the `keyboard` library when available and will
warn if the environment blocks registration.
"""

import threading
import time
import tkinter as tk
from dataclasses import dataclass
from typing import Optional, Set
from tkinter import ttk, messagebox

try:
    import keyboard
    KEYBOARD_AVAILABLE = True
    KEYBOARD_ERROR = None
except Exception as exc:  # keyboard can fail to import without permissions
    keyboard = None
    KEYBOARD_AVAILABLE = False
    KEYBOARD_ERROR = exc
from pynput import mouse, keyboard as pynput_keyboard


def safe_add_hotkey(hotkey: str, callback):
    """Attempt to register a hotkey via the keyboard library."""
    if not KEYBOARD_AVAILABLE or keyboard is None:
        raise RuntimeError(
            "Global hotkeys unavailable: keyboard library failed to load. "
            "Linux users may need to run as root or grant input device access."
        ) from KEYBOARD_ERROR
    try:
        return keyboard.add_hotkey(hotkey, callback)
    except Exception as exc:  # catch permission errors from keyboard on Linux
        raise RuntimeError(
            f"Could not register hotkey '{hotkey}'. On Linux, root access is often required."
        ) from exc


def safe_remove_hotkey(handle):
    if KEYBOARD_AVAILABLE and keyboard is not None and handle is not None:
        try:
            keyboard.remove_hotkey(handle)
        except Exception:
            pass


def _normalize_hotkey_part(part: str) -> Optional[str]:
    """Normalize a single hotkey token into a comparable string."""
    if not part:
        return None
    normalized = part.lower().strip()
    aliases = {
        "ctrl": "ctrl",
        "control": "ctrl",
        "shift": "shift",
        "alt": "alt",
        "option": "alt",
        "cmd": "cmd",
        "command": "cmd",
        "win": "cmd",
    }
    return aliases.get(normalized, normalized)


def _key_to_string(key) -> str:
    if isinstance(key, pynput_keyboard.Key):
        return _normalize_hotkey_part(str(key).replace("Key.", "")) or str(key)
    if isinstance(key, pynput_keyboard.KeyCode):
        return _normalize_hotkey_part(key.char) if key.char else str(key)
    return _normalize_hotkey_part(str(key)) or str(key)


def _parse_hotkey(hotkey: str) -> Set[str]:
    parts = [_normalize_hotkey_part(part) for part in hotkey.split("+")]
    return {p for p in parts if p}


class FallbackHotkey:
    """Fallback listener using pynput when keyboard hotkeys are unavailable."""

    def __init__(self, hotkey: str, callback):
        self.hotkey = hotkey
        self.callback = callback
        self.combo = _parse_hotkey(hotkey)
        if not self.combo:
            raise RuntimeError("Invalid hotkey")
        self.pressed: Set[str] = set()
        self.triggered = False
        self.listener = pynput_keyboard.Listener(
            on_press=self._on_press, on_release=self._on_release
        )
        self.listener.start()

    def _on_press(self, key):
        self.pressed.add(_key_to_string(key))
        if self.combo.issubset(self.pressed) and not self.triggered:
            self.triggered = True
            try:
                self.callback()
            except Exception:
                pass

    def _on_release(self, key):
        self.pressed.discard(_key_to_string(key))
        if not self.combo.issubset(self.pressed):
            self.triggered = False

    def stop(self):
        if self.listener:
            self.listener.stop()


@dataclass
class HotkeyHandle:
    kind: str
    handle: object
    warning: Optional[str] = None


def register_hotkey_with_fallback(hotkey: str, callback) -> HotkeyHandle:
    """Register a hotkey, falling back to pynput listener if needed."""
    try:
        handle = safe_add_hotkey(hotkey, callback)
        return HotkeyHandle(kind="keyboard", handle=handle, warning=None)
    except RuntimeError as exc:
        try:
            fallback = FallbackHotkey(hotkey, callback)
            return HotkeyHandle(kind="fallback", handle=fallback, warning=str(exc))
        except Exception as fallback_exc:
            raise RuntimeError(f"{exc} Fallback listener failed: {fallback_exc}") from fallback_exc


def unregister_hotkey(handle: Optional[HotkeyHandle]) -> None:
    if not handle:
        return
    if handle.kind == "keyboard":
        safe_remove_hotkey(handle.handle)
    elif handle.kind == "fallback" and isinstance(handle.handle, FallbackHotkey):
        handle.handle.stop()


class StatusLabel(ttk.Label):
    def set_status(self, text: str) -> None:
        self.config(text=f"Status: {text}")


class AutoClicker:
    def __init__(self, parent: ttk.Frame):
        self.parent = parent
        self.running = False
        self.stop_event = threading.Event()
        self.hotkey_handle: Optional[HotkeyHandle] = None

        self.mouse_controller = mouse.Controller()

        self._build_ui()

    def _build_ui(self) -> None:
        button_frame = ttk.Frame(self.parent)
        button_frame.pack(fill=tk.X, pady=5)

        ttk.Label(button_frame, text="Mouse Button:").grid(row=0, column=0, sticky="w")
        self.button_var = tk.StringVar(value="left")
        self.button_combo = ttk.Combobox(
            button_frame,
            textvariable=self.button_var,
            values=["left", "right", "middle"],
            state="readonly",
            width=10,
        )
        self.button_combo.grid(row=0, column=1, padx=5, pady=2)

        ttk.Label(button_frame, text="Delay (ms):").grid(row=1, column=0, sticky="w")
        self.delay_var = tk.StringVar(value="100")
        self.delay_entry = ttk.Entry(button_frame, textvariable=self.delay_var, width=12)
        self.delay_entry.grid(row=1, column=1, padx=5, pady=2)

        ttk.Label(button_frame, text="Hotkey (e.g., ctrl+alt+c):").grid(row=2, column=0, sticky="w")
        self.hotkey_var = tk.StringVar(value="ctrl+alt+c")
        self.hotkey_entry = ttk.Entry(button_frame, textvariable=self.hotkey_var, width=20)
        self.hotkey_entry.grid(row=2, column=1, padx=5, pady=2)

        self.bind_button = ttk.Button(button_frame, text="Bind Hotkey", command=self.bind_hotkey)
        self.bind_button.grid(row=3, column=0, columnspan=2, pady=4, sticky="ew")

        control_frame = ttk.Frame(self.parent)
        control_frame.pack(fill=tk.X, pady=5)

        self.start_button = ttk.Button(control_frame, text="Start", command=self.start_clicking)
        self.start_button.pack(side=tk.LEFT, padx=5)

        self.stop_button = ttk.Button(control_frame, text="Stop", command=self.stop_clicking)
        self.stop_button.pack(side=tk.LEFT, padx=5)

        self.status_label = StatusLabel(self.parent, text="Status: Idle")
        self.status_label.pack(anchor="w", pady=5)

    def bind_hotkey(self) -> None:
        if self.hotkey_handle:
            unregister_hotkey(self.hotkey_handle)
        hotkey = self.hotkey_var.get().strip()
        if not hotkey:
            messagebox.showwarning("Hotkey", "Please enter a hotkey combination.")
            return
        try:
            self.hotkey_handle = register_hotkey_with_fallback(hotkey, self.toggle)
        except RuntimeError as exc:
            self.hotkey_handle = None
            messagebox.showerror("Hotkey", str(exc))
            self.status_label.set_status("Hotkey unavailable")
            return
        suffix = " (fallback)" if self.hotkey_handle.warning else ""
        if self.hotkey_handle.warning:
            messagebox.showwarning(
                "Hotkey (fallback)",
                f"Keyboard hotkey backend unavailable: {self.hotkey_handle.warning}\n"
                "Using a fallback listener that should work without root privileges.",
            )
        self.status_label.set_status(f"Hotkey bound to {hotkey}{suffix}")

    def _button_choice(self) -> mouse.Button:
        choice = self.button_var.get()
        mapping = {
            "left": mouse.Button.left,
            "right": mouse.Button.right,
            "middle": mouse.Button.middle,
        }
        return mapping.get(choice, mouse.Button.left)

    def _delay_seconds(self) -> float:
        try:
            delay_ms = float(self.delay_var.get())
            return max(0.001, delay_ms / 1000.0)
        except ValueError:
            messagebox.showerror("Delay", "Invalid delay value. Please enter a number.")
            return 0.1

    def toggle(self) -> None:
        if self.running:
            self.stop_clicking()
        else:
            self.start_clicking()

    def start_clicking(self) -> None:
        if self.running:
            return
        delay = self._delay_seconds()
        self.stop_event.clear()
        self.running = True
        thread = threading.Thread(target=self._click_loop, args=(delay,), daemon=True)
        thread.start()
        self.status_label.set_status("Auto-clicking...")

    def _click_loop(self, delay: float) -> None:
        button_choice = self._button_choice()
        while not self.stop_event.wait(delay):
            self.mouse_controller.click(button_choice)
        self.running = False
        self.status_label.set_status("Stopped")

    def stop_clicking(self) -> None:
        if not self.running:
            return
        self.stop_event.set()

    def shutdown(self) -> None:
        self.stop_clicking()
        if self.hotkey_handle:
            unregister_hotkey(self.hotkey_handle)


class MacroRecorder:
    def __init__(self, parent: ttk.Frame):
        self.parent = parent
        self.recording = False
        self.playing = False
        self.events = []
        self.last_timestamp = None

        self.mouse_listener = None
        self.key_listener = None
        self.playback_stop = threading.Event()
        self.hotkey_handle: Optional[HotkeyHandle] = None

        self.mouse_controller = mouse.Controller()
        self.keyboard_controller = pynput_keyboard.Controller()

        self._build_ui()

    def _build_ui(self) -> None:
        control_frame = ttk.Frame(self.parent)
        control_frame.pack(fill=tk.X, pady=5)

        self.record_button = ttk.Button(control_frame, text="Record", command=self.start_recording)
        self.record_button.pack(side=tk.LEFT, padx=5)

        self.stop_button = ttk.Button(control_frame, text="Stop", command=self.stop_recording)
        self.stop_button.pack(side=tk.LEFT, padx=5)

        self.play_button = ttk.Button(control_frame, text="Play", command=self.toggle_playback)
        self.play_button.pack(side=tk.LEFT, padx=5)

        ttk.Label(control_frame, text="Playback Hotkey:").pack(side=tk.LEFT, padx=5)
        self.hotkey_var = tk.StringVar(value="ctrl+alt+p")
        self.hotkey_entry = ttk.Entry(control_frame, textvariable=self.hotkey_var, width=18)
        self.hotkey_entry.pack(side=tk.LEFT, padx=5)

        self.hotkey_button = ttk.Button(control_frame, text="Bind", command=self.bind_hotkey)
        self.hotkey_button.pack(side=tk.LEFT, padx=5)

        self.status_label = StatusLabel(self.parent, text="Status: Idle")
        self.status_label.pack(anchor="w", pady=5)

        self.log = tk.Text(self.parent, height=10, state="disabled")
        self.log.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def log_event(self, message: str) -> None:
        self.log.configure(state="normal")
        self.log.insert(tk.END, message + "\n")
        self.log.see(tk.END)
        self.log.configure(state="disabled")

    def bind_hotkey(self) -> None:
        if self.hotkey_handle:
            unregister_hotkey(self.hotkey_handle)
        hotkey = self.hotkey_var.get().strip()
        if not hotkey:
            messagebox.showwarning("Hotkey", "Please enter a hotkey combination.")
            return
        try:
            self.hotkey_handle = register_hotkey_with_fallback(hotkey, self.toggle_playback)
        except RuntimeError as exc:
            self.hotkey_handle = None
            messagebox.showerror("Hotkey", str(exc))
            self.status_label.set_status("Hotkey unavailable")
            return
        suffix = " (fallback)" if self.hotkey_handle.warning else ""
        if self.hotkey_handle.warning:
            messagebox.showwarning(
                "Hotkey (fallback)",
                f"Keyboard hotkey backend unavailable: {self.hotkey_handle.warning}\n"
                "Using a fallback listener that should work without root privileges.",
            )
        self.status_label.set_status(f"Hotkey bound to {hotkey}{suffix}")

    def start_recording(self) -> None:
        if self.recording:
            return
        self.events = []
        self.last_timestamp = time.time()
        self.recording = True
        self.status_label.set_status("Recording...")

        self.mouse_listener = mouse.Listener(on_click=self._on_click)
        self.key_listener = pynput_keyboard.Listener(on_press=self._on_press, on_release=self._on_release)
        self.mouse_listener.start()
        self.key_listener.start()
        self.log_event("Recording started")

    def stop_recording(self) -> None:
        if not self.recording:
            return
        self.recording = False
        if self.mouse_listener:
            self.mouse_listener.stop()
        if self.key_listener:
            self.key_listener.stop()
        self.status_label.set_status("Recording stopped")
        self.log_event(f"Recording stopped. {len(self.events)} events captured")

    def _timestamp(self) -> float:
        now = time.time()
        delta = now - self.last_timestamp if self.last_timestamp else 0
        self.last_timestamp = now
        return delta

    def _on_click(self, x, y, button, pressed):
        if not self.recording:
            return
        delay = self._timestamp()
        self.events.append({"type": "mouse", "delay": delay, "button": button, "pressed": pressed, "pos": (x, y)})
        self.log_event(f"Mouse {button} {'down' if pressed else 'up'} at ({x}, {y}) after {delay:.3f}s")

    def _normalize_key(self, key):
        if isinstance(key, pynput_keyboard.KeyCode):
            return key.char if key.char else str(key)
        return str(key)

    def _on_press(self, key):
        if not self.recording:
            return
        delay = self._timestamp()
        norm = self._normalize_key(key)
        self.events.append({"type": "key", "delay": delay, "key": norm, "action": "press"})
        self.log_event(f"Key press {norm} after {delay:.3f}s")

    def _on_release(self, key):
        if not self.recording:
            return
        delay = self._timestamp()
        norm = self._normalize_key(key)
        self.events.append({"type": "key", "delay": delay, "key": norm, "action": "release"})
        self.log_event(f"Key release {norm} after {delay:.3f}s")

    def toggle_playback(self) -> None:
        if self.playing:
            self.stop_playback()
        else:
            self.start_playback()

    def start_playback(self) -> None:
        if self.playing:
            return
        if not self.events:
            messagebox.showinfo("Playback", "No macro recorded yet.")
            return
        self.playing = True
        self.playback_stop.clear()
        thread = threading.Thread(target=self._play_loop, daemon=True)
        thread.start()
        self.status_label.set_status("Playing macro...")

    def _play_loop(self) -> None:
        while not self.playback_stop.is_set():
            for event in self.events:
                if self.playback_stop.wait(event["delay"]):
                    break
                if event["type"] == "mouse":
                    self.mouse_controller.position = event["pos"]
                    if event["pressed"]:
                        self.mouse_controller.press(event["button"])
                    else:
                        self.mouse_controller.release(event["button"])
                elif event["type"] == "key":
                    key_value = event["key"]
                    try:
                        key_obj = getattr(pynput_keyboard.Key, key_value.replace("Key.", "")) if key_value.startswith("Key.") else key_value
                    except AttributeError:
                        key_obj = key_value
                    if event["action"] == "press":
                        self.keyboard_controller.press(key_obj)
                    else:
                        self.keyboard_controller.release(key_obj)
            else:
                continue
            break
        self.playing = False
        self.status_label.set_status("Playback stopped")

    def stop_playback(self) -> None:
        if not self.playing:
            return
        self.playback_stop.set()

    def shutdown(self) -> None:
        self.stop_recording()
        self.stop_playback()
        if self.hotkey_handle:
            unregister_hotkey(self.hotkey_handle)


class KeyAutoPresser:
    def __init__(self, parent: ttk.Frame):
        self.parent = parent
        self.running = False
        self.stop_event = threading.Event()
        self.hotkey_handle: Optional[HotkeyHandle] = None

        self.keyboard_controller = pynput_keyboard.Controller()

        self._build_ui()

    def _build_ui(self) -> None:
        form = ttk.Frame(self.parent)
        form.pack(fill=tk.X, pady=5)

        ttk.Label(form, text="Key to press:").grid(row=0, column=0, sticky="w")
        self.key_var = tk.StringVar(value="a")
        self.key_entry = ttk.Entry(form, textvariable=self.key_var, width=10)
        self.key_entry.grid(row=0, column=1, padx=5, pady=2)

        ttk.Label(form, text="Delay (ms):").grid(row=1, column=0, sticky="w")
        self.delay_var = tk.StringVar(value="200")
        self.delay_entry = ttk.Entry(form, textvariable=self.delay_var, width=12)
        self.delay_entry.grid(row=1, column=1, padx=5, pady=2)

        ttk.Label(form, text="Hotkey (e.g., ctrl+alt+k):").grid(row=2, column=0, sticky="w")
        self.hotkey_var = tk.StringVar(value="ctrl+alt+k")
        self.hotkey_entry = ttk.Entry(form, textvariable=self.hotkey_var, width=20)
        self.hotkey_entry.grid(row=2, column=1, padx=5, pady=2)

        self.bind_button = ttk.Button(form, text="Bind Hotkey", command=self.bind_hotkey)
        self.bind_button.grid(row=3, column=0, columnspan=2, sticky="ew", pady=4)

        control_frame = ttk.Frame(self.parent)
        control_frame.pack(fill=tk.X, pady=5)

        self.start_button = ttk.Button(control_frame, text="Start", command=self.start_pressing)
        self.start_button.pack(side=tk.LEFT, padx=5)

        self.stop_button = ttk.Button(control_frame, text="Stop", command=self.stop_pressing)
        self.stop_button.pack(side=tk.LEFT, padx=5)

        self.status_label = StatusLabel(self.parent, text="Status: Idle")
        self.status_label.pack(anchor="w", pady=5)

    def bind_hotkey(self) -> None:
        if self.hotkey_handle:
            unregister_hotkey(self.hotkey_handle)
        hotkey = self.hotkey_var.get().strip()
        if not hotkey:
            messagebox.showwarning("Hotkey", "Please enter a hotkey combination.")
            return
        try:
            self.hotkey_handle = register_hotkey_with_fallback(hotkey, self.toggle)
        except RuntimeError as exc:
            self.hotkey_handle = None
            messagebox.showerror("Hotkey", str(exc))
            self.status_label.set_status("Hotkey unavailable")
            return
        suffix = " (fallback)" if self.hotkey_handle.warning else ""
        if self.hotkey_handle.warning:
            messagebox.showwarning(
                "Hotkey (fallback)",
                f"Keyboard hotkey backend unavailable: {self.hotkey_handle.warning}\n"
                "Using a fallback listener that should work without root privileges.",
            )
        self.status_label.set_status(f"Hotkey bound to {hotkey}{suffix}")

    def _delay_seconds(self) -> float:
        try:
            delay_ms = float(self.delay_var.get())
            return max(0.001, delay_ms / 1000.0)
        except ValueError:
            messagebox.showerror("Delay", "Invalid delay value. Please enter a number.")
            return 0.1

    def toggle(self) -> None:
        if self.running:
            self.stop_pressing()
        else:
            self.start_pressing()

    def start_pressing(self) -> None:
        if self.running:
            return
        key = self.key_var.get()
        if not key:
            messagebox.showwarning("Key", "Please enter a key to press.")
            return
        delay = self._delay_seconds()
        self.stop_event.clear()
        self.running = True
        thread = threading.Thread(target=self._press_loop, args=(key, delay), daemon=True)
        thread.start()
        self.status_label.set_status("Auto-pressing...")

    def _press_loop(self, key: str, delay: float) -> None:
        while not self.stop_event.wait(delay):
            self.keyboard_controller.press(key)
            self.keyboard_controller.release(key)
        self.running = False
        self.status_label.set_status("Stopped")

    def stop_pressing(self) -> None:
        if not self.running:
            return
        self.stop_event.set()

    def shutdown(self) -> None:
        self.stop_pressing()
        if self.hotkey_handle:
            unregister_hotkey(self.hotkey_handle)


class AutoClickerApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Advanced Auto-Clicker Toolkit")
        self.root.geometry("640x480")

        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        self.clicker_tab = ttk.Frame(self.notebook)
        self.macro_tab = ttk.Frame(self.notebook)
        self.key_tab = ttk.Frame(self.notebook)

        self.notebook.add(self.clicker_tab, text="Simple Auto-Clicker")
        self.notebook.add(self.macro_tab, text="Macro Recorder")
        self.notebook.add(self.key_tab, text="Keyboard Auto-Presser")

        self.auto_clicker = AutoClicker(self.clicker_tab)
        self.macro_recorder = MacroRecorder(self.macro_tab)
        self.key_presser = KeyAutoPresser(self.key_tab)

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def on_close(self) -> None:
        self.auto_clicker.shutdown()
        self.macro_recorder.shutdown()
        self.key_presser.shutdown()
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    app = AutoClickerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
