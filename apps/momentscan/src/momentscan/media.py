"""Media utilities — the pixel/encoding conventions, single-homed.

General-purpose media editing (crop-pad-resize, H.264 encode/transcode) used by
any layer; no domain knowledge lives here (ROI GEOMETRY like portrait_box stays
with the subject contract in subjects/crops.py — this module only executes cuts).

The system-wide encoding convention: **H.264 all-intra (keyint=1)** = every frame
an IDR frame → frame-accurate seek everywhere (crop tracks, inspector video).
Declared once here; previously the same ffmpeg recipe was typed in two homes
(crops inline + inspector._transcode_h264).
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import cv2
import numpy as np


def letterbox(frame: np.ndarray, box: tuple[int, int, int, int],
              size: tuple[int, int]) -> np.ndarray:
    """Crop `box` from frame (black-padding where it exceeds bounds — honest: no
    source there), resize to `size` (w, h) preserving aspect (caller guarantees
    box aspect == canvas aspect, so this is distortion-free)."""
    fh, fw = frame.shape[:2]
    x1, y1, x2, y2 = box
    bw, bh = x2 - x1, y2 - y1
    canvas = np.zeros((bh, bw, 3), np.uint8)
    sx1, sy1, sx2, sy2 = max(0, x1), max(0, y1), min(fw, x2), min(fh, y2)
    if sx2 > sx1 and sy2 > sy1:
        canvas[sy1 - y1:sy2 - y1, sx1 - x1:sx2 - x1] = frame[sy1:sy2, sx1:sx2]
    return cv2.resize(canvas, size, interpolation=cv2.INTER_AREA)


def h264_writer(path: Path, fps: int, size: tuple[int, int]) -> subprocess.Popen:
    """ffmpeg stdin(rawvideo BGR, `size`=(w,h)) → H.264 all-intra mp4
    (frame-accurate seek)."""
    w, h = size
    return subprocess.Popen(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "bgr24",
         "-s", f"{w}x{h}", "-r", str(fps), "-i", "pipe:0",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-x264-params", "keyint=1",
         "-an", str(path)], stdin=subprocess.PIPE)


def transcode_h264(src, dst, *, fps: int | None = None, zero_pts: bool = False,
                   cached: bool = False) -> Path:
    """File → H.264 all-intra mp4. fps=N re-samples. zero_pts additionally zeroes
    the first PTS (setpts=PTS-STARTPTS + reset_timestamps) — phone sources carry a
    start_time offset (cap_1 ≈1.33s) that a browser's TIME-based seek honors but
    cv2's FRAME-index extraction ignores; zeroing aligns browser time with frame
    index (needed for the inspector; frame-index-only consumers like the crop
    track don't need it). cached=True skips when dst exists."""
    dst = Path(dst)
    if cached and dst.exists():
        return dst
    vf = ([f"fps={fps}"] if fps else []) + (["setpts=PTS-STARTPTS"] if zero_pts else [])
    args = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(src)]
    if vf:
        args += ["-vf", ",".join(vf)]
    args += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-x264-params", "keyint=1", "-an"]
    if zero_pts:
        args += ["-reset_timestamps", "1", "-muxdelay", "0", "-muxpreload", "0"]
    subprocess.run([*args, str(dst)], check=True)
    return dst
