#!/usr/bin/env python3
"""winbot - drive a real UZDoom window with synthetic keyboard input and
capture what the player actually sees.

Windows-only, ctypes, no deps beyond Pillow for PNG saving. Input goes
through SendInput at the system level (scan codes included), which is the
same channel a real keyboard uses - games polling keyboard state see it.
Window capture uses PrintWindow(PW_RENDERFULLCONTENT) with a screen-region
BitBlt fallback for GPU surfaces.

Ops accepted by run_steps:
  ("wait", seconds)
  ("key", name, hold_seconds)      hold a key down for N seconds
  ("tap", name)                    quick press (default 0.08 s)
  ("console", "command")           open console, type command, Enter, close
  ("shot", "label")                capture the window to PNG
  ("spam", [names], interval, total)  cycle key taps for N seconds
"""
from __future__ import annotations

import ctypes
import time
from ctypes import wintypes as wt
from pathlib import Path

from PIL import Image

# DPI awareness: without this GetClientRect is virtualized and captures
# come back cropped (the status bar falls off the bottom).
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)  # per-monitor v2
except Exception:  # noqa: BLE001
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:  # noqa: BLE001
        pass

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)

PW_RENDERFULLCONTENT = 2
SRCCOPY = 0x00CC0020
CAPTUREBLT = 0x40000000
KEYEVENTF_KEYUP = 0x0002
INPUT_KEYBOARD = 1

VK = {
    "w": 0x57, "a": 0x41, "s": 0x53, "d": 0x44, "e": 0x45, "q": 0x51,
    "r": 0x52, "f": 0x46, "y": 0x59, "n": 0x4E, "g": 0x47,
    "f1": 0x70, "f2": 0x71, "f3": 0x72, "f4": 0x73, "f5": 0x74,
    "f6": 0x75, "f7": 0x76, "f8": 0x77, "f9": 0x78, "f10": 0x79,
    "f11": 0x7A, "f12": 0x7B,
    "space": 0x20, "enter": 0x0D, "esc": 0x1B, "tab": 0x09,
    "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27,
    "ctrl": 0xA2, "shift": 0xA1, "alt": 0xA4, "grave": 0xC0,
}

CHAR_VK = {c: 0x41 + i for i, c in enumerate("abcdefghijklmnopqrstuvwxyz")}
CHAR_VK.update({str(i): 0x30 + i for i in range(10)})
CHAR_VK.update({
    " ": 0x20, ".": 0xBE, ",": 0xBC, "/": 0xBF, "-": 0xBD, "=": 0xBB,
    ";": 0xBA, "'": 0xDE, "[": 0xDB, "]": 0xDD, "`": 0xC0,
})
CHAR_SHIFT = {"_": 0xBD, "+": 0xBB, '"': 0xDE, ":": 0xBA, "?": 0xBF,
              "<": 0xBC, ">": 0xBE, "~": 0xC0}


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wt.WORD), ("wScan", wt.WORD), ("dwFlags", wt.DWORD),
                ("time", wt.DWORD), ("dwExtraInfo", ctypes.c_void_p)]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("wVk", wt.WORD), ("wScan", wt.WORD), ("dwFlags", wt.DWORD),
                ("time", wt.DWORD), ("dwExtraInfo", ctypes.c_void_p),
                ("dx", wt.LONG), ("dy", wt.LONG)]


class _INPUTU(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wt.DWORD), ("u", _INPUTU)]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", wt.DWORD), ("biWidth", wt.LONG),
                ("biHeight", wt.LONG), ("biPlanes", wt.WORD),
                ("biBitCount", wt.WORD), ("biCompression", wt.DWORD),
                ("biSizeImage", wt.DWORD), ("biXPelsPerMeter", wt.LONG),
                ("biYPelsPerMeter", wt.LONG), ("biClrUsed", wt.DWORD),
                ("biClrImportant", wt.DWORD)]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", wt.DWORD * 3)]


WNDENUMPROC = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)

PSAPI = ctypes.WinDLL("psapi", use_last_error=True)


def _exe_name(hwnd: int) -> str:
    pid = wt.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if not pid.value:
        return ""
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    h = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False,
                             pid.value)
    if not h:
        return ""
    try:
        buf = ctypes.create_unicode_buffer(512)
        size = wt.DWORD(512)
        if kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
            return buf.value
        return ""
    finally:
        kernel32.CloseHandle(h)


def find_uzdoom(min_area: int = 0, pid: int | None = None) -> int | None:
    """Find the LARGEST visible uzdoom.exe window (batchrun creates more
    than one: console panes, startup windows). Windows smaller than
    min_area (client px^2) are ignored."""
    hits = []

    def cb(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        if pid is not None:
            wpid = wt.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(wpid))
            if wpid.value != pid:
                return True
        elif not _exe_name(hwnd).lower().endswith("uzdoom.exe"):
            return True
        cc = wt.RECT()
        user32.GetClientRect(hwnd, ctypes.byref(cc))
        area = (cc.right - cc.left) * (cc.bottom - cc.top)
        if area >= min_area:
            hits.append((area, hwnd))
        return True

    user32.EnumWindows(WNDENUMPROC(cb), 0)
    if not hits:
        return None
    hits.sort(reverse=True)
    return hits[0][1]


def find_window(substr: str) -> int | None:
    hits = []

    def cb(hwnd, _lparam):
        buf = ctypes.create_unicode_buffer(256)
        user32.GetWindowTextW(hwnd, buf, 256)
        if substr.lower() in buf.value.lower():
            hits.append(hwnd)
        return True

    user32.EnumWindows(WNDENUMPROC(cb), 0)
    return hits[0] if hits else None


def focus(hwnd: int) -> bool:
    """Bring the game window to the foreground without simulating ALT
    (synthetic ALT can leak into menus as a modifier press)."""
    if user32.GetForegroundWindow() == hwnd:
        return True
    fg = user32.GetForegroundWindow()
    ftid = user32.GetWindowThreadProcessId(fg, None) if fg else 0
    ctid = kernel32.GetCurrentThreadId()
    attach = bool(ftid) and ftid != ctid
    if attach:
        user32.AttachThreadInput(ctid, ftid, True)
    user32.ShowWindow(hwnd, 9)  # SW_RESTORE
    user32.SetForegroundWindow(hwnd)
    user32.BringWindowToTop(hwnd)
    user32.SetFocus(hwnd)
    if attach:
        user32.AttachThreadInput(ctid, ftid, False)
    time.sleep(0.12)
    return user32.GetForegroundWindow() == hwnd


KEYEVENTF_SCANCODE = 0x0008


def _send_key(vk: int, up: bool = False) -> int:
    """Send a key as a hardware scan code. Raw-input backends (SDL) can
    drop synthetic VK events for some keys (Escape was the notorious one);
    scancode injection goes through the same path as a real keyboard."""
    scan = user32.MapVirtualKeyW(vk, 0) & 0xFF
    flags = KEYEVENTF_SCANCODE | (KEYEVENTF_KEYUP if up else 0)
    inp = INPUT()
    inp.type = INPUT_KEYBOARD
    inp.u.ki = KEYBDINPUT(0, scan, flags, 0, None)
    arr = (INPUT * 1)(inp)
    return user32.SendInput(1, arr, ctypes.sizeof(INPUT))


def tap(name: str, hold: float = 0.08) -> int:
    vk = VK[name.lower()]
    n1 = _send_key(vk)
    time.sleep(hold)
    n2 = _send_key(vk, up=True)
    return min(n1, n2)


def hold_key(name: str, seconds: float) -> None:
    vk = VK[name.lower()]
    _send_key(vk)
    time.sleep(seconds)
    _send_key(vk, up=True)


def type_text(text: str, cadence: float = 0.02) -> None:
    for ch in text:
        low = ch.lower()
        need_shift = ch.isupper() or ch in CHAR_SHIFT
        base = CHAR_SHIFT.get(low) if low in CHAR_SHIFT else CHAR_VK.get(low)
        if base is None:
            if ch == " ":
                base = 0x20
            else:
                continue
        if need_shift:
            _send_key(0xA1)
        _send_key(base)
        time.sleep(cadence)
        _send_key(base, up=True)
        if need_shift:
            _send_key(0xA1, up=True)
        time.sleep(cadence)


def console_cmd(hwnd: int, command: str, shot_dir: Path | None = None,
                label: str = "") -> None:
    focus(hwnd)
    tap("grave", 0.15)
    time.sleep(0.35)
    type_text(command)
    tap("enter", 0.15)
    time.sleep(0.45)
    if shot_dir is not None and label:
        capture(hwnd, shot_dir / f"console_{label}.png")
    tap("grave", 0.15)
    time.sleep(0.25)


def _client_size(hwnd: int) -> tuple[int, int, int, int]:
    cc = wt.RECT()
    user32.GetClientRect(hwnd, ctypes.byref(cc))
    pt = wt.POINT(0, 0)
    user32.ClientToScreen(hwnd, ctypes.byref(pt))
    return cc.right - cc.left, cc.bottom - cc.top, pt.x, pt.y


def capture(hwnd: int, path: Path) -> Path:
    focus(hwnd)
    cw, ch, sx, sy = _client_size(hwnd)
    if cw <= 0 or ch <= 0:
        raise RuntimeError("window has no client area")

    def grab(printwindow: bool) -> Image.Image:
        if printwindow:
            src = user32.GetWindowDC(hwnd)
        else:
            src = user32.GetDC(None)
        mem = gdi32.CreateCompatibleDC(src)
        bmp = gdi32.CreateCompatibleBitmap(src, cw, ch)
        old = gdi32.SelectObject(mem, bmp)
        if printwindow:
            user32.PrintWindow(hwnd, mem, PW_RENDERFULLCONTENT)
        else:
            gdi32.BitBlt(mem, 0, 0, cw, ch, src, sx, sy,
                         SRCCOPY | CAPTUREBLT)
        bmi = BITMAPINFO()
        bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmi.bmiHeader.biWidth = cw
        bmi.bmiHeader.biHeight = -ch  # top-down
        bmi.bmiHeader.biPlanes = 1
        bmi.bmiHeader.biBitCount = 32
        bmi.bmiHeader.biCompression = 0
        buf = ctypes.create_string_buffer(cw * ch * 4)
        gdi32.GetDIBits(mem, bmp, 0, ch, buf, ctypes.byref(bmi), 0)
        gdi32.SelectObject(mem, old)
        gdi32.DeleteObject(bmp)
        gdi32.DeleteDC(mem)
        user32.ReleaseDC(hwnd if printwindow else None, src)
        img = Image.frombuffer("RGB", (cw, ch), buf, "raw", "BGRX", 0, 1)
        return img.copy()

    img = grab(True)
    if _is_black(img):
        img = grab(False)
    img.save(path)
    return path


def _is_black(img: Image.Image, sample: int = 24) -> bool:
    w, h = img.size
    px = img.load()
    for y in range(0, h, max(1, h // sample)):
        for x in range(0, w, max(1, w // sample)):
            p = px[x, y]
            if p[0] + p[1] + p[2] > 24:
                return False
    return True


def run_steps(hwnd: int, steps: list, shot_dir: Path) -> None:
    for step in steps:
        op = step[0]
        if op == "wait":
            time.sleep(step[1])
        elif op == "key":
            focus(hwnd)
            hold_key(step[1], step[2])
        elif op == "tap":
            focus(hwnd)
            tap(step[1])
        elif op == "console":
            console_cmd(hwnd, step[1], shot_dir, step[2] if len(step) > 2 else "")
        elif op == "shot":
            capture(hwnd, shot_dir / f"{step[1]}.png")
        elif op == "spam":
            _, names, interval, total = step
            deadline = time.time() + total
            i = 0
            while time.time() < deadline:
                focus(hwnd)
                tap(names[i % len(names)], 0.08)
                i += 1
                time.sleep(max(0.05, interval - 0.08))
        else:
            raise ValueError(f"unknown op {op!r}")
