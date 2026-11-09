# ruff: noqa: I001, SIM105  (style only; evidence tools are frozen as used for the study)
"""Window recorder for research evidence (not part of the agent).

Captures one top-level window with PrintWindow (works when the window is covered by others, not when minimized)
and pipes the frames to ffmpeg: an .mp4 video plus single-frame .png screenshots. Windows only.
"""

from __future__ import annotations

import ctypes
import glob
import os
import shutil
import subprocess
import threading
import time
from ctypes import wintypes
from pathlib import Path

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
PW_RENDERFULLCONTENT = 2


def ffmpeg_exe() -> str:
    found = os.environ.get("SFBOT_FFMPEG") or shutil.which("ffmpeg")
    if found:
        return found
    pattern = os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Packages\Gyan.FFmpeg*\**\bin\ffmpeg.exe")
    hits = glob.glob(pattern, recursive=True)
    if not hits:
        raise FileNotFoundError("ffmpeg not found (winget install Gyan.FFmpeg.Essentials)")
    return hits[0]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG), ("biHeight", wintypes.LONG),
                ("biPlanes", wintypes.WORD), ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG),
                ("biYPelsPerMeter", wintypes.LONG), ("biClrUsed", wintypes.DWORD),
                ("biClrImportant", wintypes.DWORD)]


def capture(hwnd: int, size: tuple[int, int] | None = None) -> tuple[int, int, bytes] | None:
    """BGRA pixels of the whole window (top-down), or None if it cannot be captured right now.
    With `size`, the window is drawn at the top-left of a fixed w×h canvas (cropped / black padding) by GDI."""
    rect = wintypes.RECT()
    if not user32.GetWindowRect(hwnd, ctypes.byref(rect)) or user32.IsIconic(hwnd):
        return None
    w, h = size or (rect.right - rect.left, rect.bottom - rect.top)
    if w <= 0 or h <= 0:
        return None
    hdc_win = user32.GetWindowDC(hwnd)
    hdc = gdi32.CreateCompatibleDC(hdc_win)
    bmp = gdi32.CreateCompatibleBitmap(hdc_win, w, h)
    old = gdi32.SelectObject(hdc, bmp)
    try:
        user32.PrintWindow(hwnd, hdc, PW_RENDERFULLCONTENT)
        bih = BITMAPINFOHEADER()
        bih.biSize, bih.biWidth, bih.biHeight = ctypes.sizeof(BITMAPINFOHEADER), w, -h
        bih.biPlanes, bih.biBitCount, bih.biCompression = 1, 32, 0
        buf = ctypes.create_string_buffer(w * h * 4)
        if not gdi32.GetDIBits(hdc, bmp, 0, h, buf, ctypes.byref(bih), 0):
            return None
        return w, h, buf.raw
    finally:
        gdi32.SelectObject(hdc, old)
        gdi32.DeleteObject(bmp)
        gdi32.DeleteDC(hdc)
        user32.ReleaseDC(hwnd, hdc_win)


def canvas_size(first: tuple[int, int, bytes]) -> tuple[int, int]:
    """Video size: big enough for the first frame and for a maximized window (screen + borders), even numbers."""
    sw, sh = user32.GetSystemMetrics(0) + 16, user32.GetSystemMetrics(1) + 16
    w, h = max(first[0], sw), max(first[1], sh)
    return w - w % 2, h - h % 2


def save_png(frame: tuple[int, int, bytes] | None, path: Path) -> bool:
    if frame is None:
        return False
    w, h, data = frame
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgra",
                    "-s", f"{w}x{h}", "-i", "-", "-frames:v", "1", str(path)], input=data, check=False,
                   creationflags=subprocess.CREATE_NO_WINDOW)
    return path.exists()


class Recorder:
    """Background thread: captures `hwnd_getter()` at `fps` and writes an H.264 mp4."""

    def __init__(self, hwnd_getter, out: Path, fps: int = 4, fixed: bool = False) -> None:
        """fixed=True: the window keeps its size (video = window size); else video = screen-sized canvas."""
        self.hwnd_getter, self.out, self.fps, self.fixed = hwnd_getter, out, fps, fixed
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self.frames = 0

    def start(self) -> Recorder:
        self._thread.start()
        return self

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=30)

    def _run(self) -> None:
        first = None
        while first is None and not self._stop.is_set():
            first = capture(self.hwnd_getter())
            time.sleep(0.2)
        if first is None:
            return
        w, h = (first[0] - first[0] % 2, first[1] - first[1] % 2) if self.fixed else canvas_size(first)
        self.out.parent.mkdir(parents=True, exist_ok=True)
        proc = subprocess.Popen([ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo",
                                 "-pix_fmt", "bgra", "-s", f"{w}x{h}", "-r", str(self.fps), "-i", "-",
                                 "-c:v", "libx264", "-preset", "veryfast", "-crf", "28", "-pix_fmt", "yuv420p",
                                 str(self.out)], stdin=subprocess.PIPE, creationflags=subprocess.CREATE_NO_WINDOW)
        last, period = first, 1.0 / self.fps
        try:
            while not self._stop.is_set():
                t = time.time()
                frame = capture(self.hwnd_getter(), (w, h)) or last
                last = frame
                proc.stdin.write(frame[2])
                self.frames += 1
                time.sleep(max(0.0, period - (time.time() - t)))
        except (OSError, ValueError):
            pass
        finally:
            try:
                proc.stdin.close()
            except OSError:
                pass
            proc.wait(timeout=120)
