from pathlib import Path
from datetime import datetime
from queue import Queue
import json
import math
import os
import socket
import time
import subprocess
import tempfile
import threading

from gpiozero import Button, InputDevice
from PIL import Image, ImageDraw, ImageFont
from picamera2 import Picamera2
from libcamera import controls
import numpy as np
import pygame


# GPIO 16 is reserved for the Geekworm X1200 UPS; keep the button off it.
BUTTON_GPIO = 26

LONG_PRESS_SECONDS = 1.0
# Defaults for settings that can be changed in the touchscreen menu (saved in settings.json).
# Review screen: a full strip is kept automatically after this long without a press.
REVIEW_AUTO_KEEP_SECONDS = 20
# Screen sleep: backlight off after this long with no presses/touches. None to disable.
SCREEN_OFF_SECONDS = 120
SHUTDOWN_PRESS_SECONDS = 6.0

DOUBLE_CLICK_SECONDS = 0.4

BASE = Path.home() / "photobooth"
FRAME_DIR = BASE / "frames"
STRIP_DIR = BASE / "strips"
CAPTURE_DIR = BASE / "captures"
ARCHIVE_DIR = STRIP_DIR / "archive"

for d in [FRAME_DIR, STRIP_DIR, CAPTURE_DIR, ARCHIVE_DIR]:
    d.mkdir(parents=True, exist_ok=True)

STRIP_W, STRIP_H = 1200, 3600
PRINT_W, PRINT_H = STRIP_W * 2, STRIP_H

DEFAULT_SLOTS = [
    (120, 180, 960, 690),
    (120, 990, 960, 690),
    (120, 1800, 960, 690),
    (120, 2610, 960, 690),
]

CAPTURE_W, CAPTURE_H = 2304, 1296
# Longest shutter time allowed, in microseconds (20000 = 1/50 s). Shorter = less motion
# blur, but dim scenes get brighter via gain instead, so they look grainier. Menu default.
MAX_EXPOSURE_US = 20000
PREVIEW_W, PREVIEW_H = 640, 360
LIVE_PREVIEW_FPS = 8
SLOT_BLEED = 5
# A camera call that takes longer than this means the camera has stalled.
CAMERA_TIMEOUT_SECONDS = 5

USE_LCD = True

# The UI is drawn at 480x800 (portrait, one strip) or 800x480 (landscape, photos
# two per side) and rotated onto the 800x480 DSI panel.
# 5 quick presses (or the settings menu) changes the rotation.
PORTRAIT_UI_W = 480
PORTRAIT_UI_H = 800
SCREEN_ROTATIONS = [-90, 90, 0, 180]  # PIL degrees counter-clockwise
SCREEN_ROTATION_LABELS = {-90: "PORTRAIT", 90: "PORTRAIT (FLIPPED)", 0: "LANDSCAPE", 180: "LANDSCAPE (FLIPPED)"}
SCREEN_ROTATION_FILE = BASE / "screen_rotation.txt"  # older builds; read once as a default
ROTATE_SCREEN_PRESSES = 5
LANDSCAPE_CELL_PAD = 6

# Geekworm X1200 UPS: MAX17040 fuel gauge on I2C bus 1.
BATTERY_I2C_BUS = 1
BATTERY_I2C_ADDR = 0x36
BATTERY_POLL_SECONDS = 10
BATTERY_LOW_PERCENT = 20
BATTERY_CRITICAL_PERCENT = 5
BATTERY_CRITICAL_VOLTS = 3.20
BATTERY_CRITICAL_READINGS = 3
# X1200 power-loss detect: high while external power is connected. None to disable.
POWER_LOSS_GPIO = 6

PRINTER_NAME = None
PRINT_OPTIONS = [
    "-o", "PageSize=Postcard.Borderless",
]
PRINT_SCALE = 96


def _load_screen_rotation():
    try:
        value = int(SCREEN_ROTATION_FILE.read_text().strip())
        if value in SCREEN_ROTATIONS:
            return value
    except (OSError, ValueError):
        pass
    return SCREEN_ROTATIONS[0]


SETTINGS_FILE = BASE / "settings.json"

# Touchscreen settings menu: (key, label, [(value, text shown), ...], default).
CAMERA_SETTINGS = [
    ("brightness", "BRIGHTNESS", [
        (-1.5, "DARKEST"), (-1.0, "DARKER"), (-0.5, "A BIT DARKER"), (0.0, "NORMAL"),
        (0.5, "A BIT BRIGHTER"), (1.0, "BRIGHTER"), (1.5, "BRIGHTEST"),
    ], 0.0),
    ("colour", "COLOUR", [
        ("normal", "NORMAL"), ("bw", "BLACK & WHITE"), ("vivid", "VIVID"),
        ("film", "FILM (WARM)"), ("film_bw", "FILM (B&W)"),
    ], "normal"),
    ("motion", "MOVEMENT", [
        (10000, "SHARPEST (DARKER)"), (20000, "BALANCED"), (33333, "BRIGHTER (MORE BLUR)"),
    ], MAX_EXPOSURE_US),
    ("focus", "FOCUS", [
        ("auto", "AUTO"), ("near", "FIXED: CLOSE UP"), ("far", "FIXED: FARTHER AWAY"),
    ], "auto"),
    ("light", "LIGHTING", [
        ("auto", "AUTO"), ("tungsten", "WARM LIGHT BULBS"), ("fluorescent", "OFFICE LIGHTS"),
        ("indoor", "INDOOR"), ("daylight", "SUNNY"), ("cloudy", "CLOUDY"),
    ], "auto"),
    ("zoom", "ZOOM", [
        (1.0, "WIDE"), (1.2, "A BIT CLOSER"), (1.4, "CLOSER"), (1.7, "CLOSEST"),
    ], 1.0),
    ("mirror", "MIRROR PREVIEW", [
        (True, "ON (LIKE A MIRROR)"), (False, "OFF"),
    ], True),
]
BOOTH_SETTINGS = [
    ("rotation", "SCREEN", [
        (-90, "PORTRAIT"), (90, "PORTRAIT (FLIPPED)"), (0, "LANDSCAPE"), (180, "LANDSCAPE (FLIPPED)"),
    ], _load_screen_rotation()),
    ("sleep", "SCREEN OFF WHEN IDLE", [
        (60, "AFTER 1 MIN"), (120, "AFTER 2 MIN"), (300, "AFTER 5 MIN"),
        (900, "AFTER 15 MIN"), (None, "NEVER"),
    ], SCREEN_OFF_SECONDS),
    ("countdown", "COUNTDOWN BEFORE EACH PHOTO", [
        (0, "OFF"), (3, "3 SECONDS"), (5, "5 SECONDS"), (10, "10 SECONDS"),
    ], 3),
    ("review", "KEEP STRIP AUTOMATICALLY", [
        (10, "AFTER 10 SEC"), (20, "AFTER 20 SEC"), (30, "AFTER 30 SEC"), (60, "AFTER 1 MIN"),
    ], REVIEW_AUTO_KEEP_SECONDS),
]
SETTING_DEFS = {key: (label, choices, default)
                for key, label, choices, default in CAMERA_SETTINGS + BOOTH_SETTINGS}


def _load_settings():
    values = {key: default for key, (_, _, default) in SETTING_DEFS.items()}
    try:
        saved = json.loads(SETTINGS_FILE.read_text())
    except (OSError, ValueError):
        saved = {}
    if isinstance(saved, dict):
        for key, value in saved.items():
            if key in SETTING_DEFS and value in [v for v, _ in SETTING_DEFS[key][1]]:
                values[key] = value
    return values


settings = _load_settings()
screen_rotation = settings["rotation"]


picam2 = Picamera2()


AWB_MODES = {
    "auto": controls.AwbModeEnum.Auto,
    "tungsten": controls.AwbModeEnum.Tungsten,
    "fluorescent": controls.AwbModeEnum.Fluorescent,
    "indoor": controls.AwbModeEnum.Indoor,
    "daylight": controls.AwbModeEnum.Daylight,
    "cloudy": controls.AwbModeEnum.Cloudy,
}
SATURATION = {"normal": 1.0, "bw": 0.0, "vivid": 1.6, "film": 0.85, "film_bw": 0.0}
FOCUS_DIOPTRES = {"near": 1.5, "far": 0.3}  # 1 / distance in metres


def camera_controls_from_settings():
    cx, cy, cw, ch = picam2.camera_properties["ScalerCropMaximum"]
    zw, zh = int(cw / settings["zoom"]), int(ch / settings["zoom"])
    c = {
        # Exposure can't be longer than a frame, so this caps the shutter;
        # "Short" makes auto-exposure raise gain before shutter time.
        "FrameDurationLimits": (100, settings["motion"]),
        "AeExposureMode": controls.AeExposureModeEnum.Short,
        "ExposureValue": settings["brightness"],
        "Saturation": SATURATION[settings["colour"]],
        "AwbMode": AWB_MODES[settings["light"]],
        "ScalerCrop": (cx + (cw - zw) // 2, cy + (ch - zh) // 2, zw, zh),
    }
    if settings["focus"] == "auto":
        c["AfMode"] = controls.AfModeEnum.Continuous
    else:
        c["AfMode"] = controls.AfModeEnum.Manual
        c["LensPosition"] = FOCUS_DIOPTRES[settings["focus"]]
    return c


def _configure_camera():
    # Pi 5 can deliver lores as RGB (PIL-ready); older Pis only allow YUV420.
    for fmt in ("BGR888", "YUV420"):
        try:
            picam2.configure(picam2.create_still_configuration(
                main={"size": (CAPTURE_W, CAPTURE_H)},
                lores={"size": (PREVIEW_W, PREVIEW_H), "format": fmt},
                controls=camera_controls_from_settings(),
            ))
            return fmt
        except Exception as e:
            print(f"Lores format {fmt} not supported: {e}")
    raise RuntimeError("Could not configure camera")


LORES_FORMAT = _configure_camera()
print(f"Camera configured: main {CAPTURE_W}x{CAPTURE_H}, lores {LORES_FORMAT}")
picam2.start()
camera_running = True
time.sleep(1.5)


def camera_failed(what):
    # A stalled camera doesn't recover in-process (even stop() can hang), so exit and
    # let photobooth.service start a fresh process, which gets a working camera.
    print(f"Camera stalled during {what}; exiting so the service restarts the app.", flush=True)
    restore_backlight_if_dark()
    os._exit(1)


def _run_with_timeout(fn, what):
    done = threading.Event()
    error = []

    def worker():
        try:
            fn()
        except Exception as e:
            error.append(e)
        done.set()

    threading.Thread(target=worker, daemon=True).start()
    if not done.wait(CAMERA_TIMEOUT_SECONDS):
        camera_failed(what)
    if error:
        raise error[0]


def stop_camera():
    global camera_running
    if camera_running:
        _run_with_timeout(picam2.stop, "camera stop")
        camera_running = False


def start_camera():
    global camera_running
    if not camera_running:
        _run_with_timeout(picam2.start, "camera start")
        camera_running = True
        apply_camera_settings()


def apply_camera_settings():
    if camera_running:
        picam2.set_controls(camera_controls_from_settings())


def write_file_durably(path, write):
    # Temp file + fsync + rename: a power cut leaves the old file or the new one, never an empty one.
    path = Path(path)
    tmp = path.with_name(f".{path.name}.tmp")
    with open(tmp, "wb") as f:
        write(f)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)
    dir_fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(dir_fd)
    finally:
        os.close(dir_fd)


_NOTIFY_SOCKET = os.environ.get("NOTIFY_SOCKET")
_last_watchdog_ping = 0.0


def watchdog_ping():
    # Tells systemd the main loop is alive; if the pings stop (app frozen), systemd restarts it.
    global _last_watchdog_ping
    now = time.monotonic()
    if not _NOTIFY_SOCKET or now - _last_watchdog_ping < 5:
        return
    _last_watchdog_ping = now
    addr = _NOTIFY_SOCKET
    if addr.startswith("@"):
        addr = "\0" + addr[1:]
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as s:
            s.sendto(b"WATCHDOG=1", addr)
    except OSError as e:
        print(f"Watchdog ping failed: {e}")


def save_settings():
    data = (json.dumps(settings, indent=2) + "\n").encode()
    try:
        write_file_durably(SETTINGS_FILE, lambda f: f.write(data))
    except OSError as e:
        print(f"Could not save settings: {e}")


def set_setting(key, value):
    global screen_rotation
    settings[key] = value
    save_settings()
    print(f"Setting {key} = {value}")
    if key == "rotation":
        screen_rotation = value
        _invalidate_live_preview()
    elif key in {k for k, _, _, _ in CAMERA_SETTINGS}:
        apply_camera_settings()


pygame.init()

lcd = None

if USE_LCD:
    try:
        lcd = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        pygame.mouse.set_visible(False)
        print(f"LCD initialized: {lcd.get_size()}")
    except Exception as e:
        lcd = None
        print(f"LCD not available: {e}")
        if os.environ.get("INVOCATION_ID"):
            # Started by systemd: the screen may not be ready yet at boot. Exit so it retries
            # instead of running without a screen.
            raise SystemExit(1)


def _frame_sort_key(path):
    # frame2 before frame10: compare the number, not the text.
    digits = "".join(ch for ch in path.stem if ch.isdigit())
    return (int(digits) if digits else 0, path.name)


frames = sorted(FRAME_DIR.glob("*.png"), key=_frame_sort_key)
current_frame_index = 0

live_photos = [None, None, None, None]
live_capture_paths = [None, None, None, None]
current_slot = 0

mode = "creation"
screen_asleep = False
last_activity = time.monotonic()
review_started = None
_review_shown_seconds = None

browse_strips = []
browse_index = 0

try:
    button = Button(BUTTON_GPIO, pull_up=True, bounce_time=0.05)
except Exception as e:
    print(f"Button creation failed: {type(e).__name__}: {e}")
    raise

press_started = None

action_queue = Queue()

_slot_cache = {}
_frame_img_cache = {}
_frame_cfg_cache = {}

_live_preview_key = None
_live_preview_photos = None
_live_preview_frame = None
_live_preview_slot_box = None
_live_preview_last_ts = 0.0


def _clear_photo_cache():
    _slot_cache.clear()
    _invalidate_live_preview()


def _invalidate_live_preview():
    global _live_preview_key, _live_preview_photos, _live_preview_frame
    global _live_preview_slot_box
    _live_preview_key = None
    _live_preview_photos = None
    _live_preview_frame = None
    _live_preview_slot_box = None


def _mtime(path):
    try:
        return path.stat().st_mtime_ns
    except OSError:
        return None


def center_crop_to_slot(img, slot_w, slot_h, resample=Image.LANCZOS):
    img = img.convert("RGB")
    src_w, src_h = img.size

    target_ratio = slot_w / slot_h
    src_ratio = src_w / src_h

    if src_ratio > target_ratio:
        new_w = int(src_h * target_ratio)
        left = (src_w - new_w) // 2
        img = img.crop((left, 0, left + new_w, src_h))
    else:
        new_h = int(src_w / target_ratio)
        top = (src_h - new_h) // 2
        img = img.crop((0, top, src_w, top + new_h))

    return img.resize((slot_w, slot_h), resample)


def load_frame_image(frame_index):
    if not frames or frame_index < 0 or frame_index >= len(frames):
        return None

    frame_path = frames[frame_index]
    mtime = _mtime(frame_path)

    cached = _frame_img_cache.get(frame_index)
    if cached is not None and cached[0] == mtime:
        return cached[1]

    frame = Image.open(frame_path).convert("RGBA")
    frame = frame.resize((STRIP_W, STRIP_H), Image.LANCZOS)
    _frame_img_cache[frame_index] = (mtime, frame)
    return frame


def load_current_frame():
    return load_frame_image(current_frame_index)


def _normalize_slots(raw):
    return [tuple(int(v) for v in slot) for slot in raw]


def _load_frame_config(frame_path):
    slots = DEFAULT_SLOTS

    sidecar = frame_path.with_suffix(".json")
    if sidecar.exists():
        try:
            data = json.loads(sidecar.read_text())
            if isinstance(data, dict):
                if data.get("slots"):
                    slots = _normalize_slots(data["slots"])
            else:
                slots = _normalize_slots(data)
        except Exception as e:
            print(f"Bad frame config {sidecar.name}, using defaults: {e}")

    return slots


def frame_slots(frame_index):
    if not frames or frame_index < 0 or frame_index >= len(frames):
        return DEFAULT_SLOTS

    frame_path = frames[frame_index]
    mtime = _mtime(frame_path.with_suffix(".json"))

    cached = _frame_cfg_cache.get(frame_index)
    if cached is not None and cached[0] == mtime:
        return cached[1]

    slots = _load_frame_config(frame_path)
    _frame_cfg_cache[frame_index] = (mtime, slots)
    return slots


def current_frame_slots():
    return frame_slots(current_frame_index)


def frame_slot_count(frame_index):
    return len(frame_slots(frame_index))


def current_capacity():
    return frame_slot_count(current_frame_index)


def strip_is_full():
    return current_slot >= current_capacity() and current_capacity() > 0


def indices_for_capacity(capacity):
    return [i for i in range(len(frames)) if frame_slot_count(i) == capacity]


def delete_capture_file(path):
    if path is None:
        return
    try:
        Path(path).unlink()
    except FileNotFoundError:
        pass
    except OSError as e:
        print(f"Could not delete capture {path}: {e}")


def resize_live_photos(new_capacity):
    global live_photos, live_capture_paths, current_slot

    new_photos = [None] * new_capacity
    new_paths = [None] * new_capacity
    for i in range(min(len(live_photos), new_capacity)):
        new_photos[i] = live_photos[i]
        new_paths[i] = live_capture_paths[i]
    for path in live_capture_paths[new_capacity:]:
        delete_capture_file(path)
    live_photos = new_photos
    live_capture_paths = new_paths
    if current_slot > new_capacity:
        current_slot = new_capacity
    while current_slot > 0 and (
        current_slot > new_capacity or live_photos[current_slot - 1] is None
    ):
        current_slot -= 1


def _fitted_slot_image(photo, bleed_w, bleed_h):
    key = (id(photo), bleed_w, bleed_h)
    cached = _slot_cache.get(key)
    if cached is not None:
        return cached

    fitted = center_crop_to_slot(photo, bleed_w, bleed_h).convert("RGBA")
    _slot_cache[key] = fitted
    return fitted


def compose_single_strip(strip_photos, frame_index=None, include_frame=True):
    strip = Image.new("RGBA", (STRIP_W, STRIP_H), "white")

    if frame_index is None:
        frame_index = current_frame_index

    slots = frame_slots(frame_index)

    for i, photo in enumerate(strip_photos):
        if photo is None:
            continue
        if i >= len(slots):
            break

        x, y, w, h = slots[i]
        left = max(0, x - SLOT_BLEED)
        top = max(0, y - SLOT_BLEED)
        right = min(STRIP_W, x + w + SLOT_BLEED)
        bottom = min(STRIP_H, y + h + SLOT_BLEED)

        fitted = _fitted_slot_image(photo, right - left, bottom - top)
        strip.alpha_composite(fitted, (left, top))

    if include_frame:
        frame = load_frame_image(frame_index)
        if frame is not None:
            strip.alpha_composite(frame, (0, 0))

    return strip


def is_landscape():
    return screen_rotation in (0, 180)


def ui_size():
    if is_landscape():
        return PORTRAIT_UI_H, PORTRAIT_UI_W
    return PORTRAIT_UI_W, PORTRAIT_UI_H


def strip_halves(slots):
    """Cuts the strip in two between the middle photos: header + first photos, rest + footer."""
    first = (len(slots) + 1) // 2
    if len(slots) < 2:
        return [(0, 0, STRIP_W, STRIP_H)]
    above = slots[first - 1][1] + slots[first - 1][3]
    below = slots[first][1]
    cut = (above + below) // 2
    return [(0, 0, STRIP_W, cut), (0, cut, STRIP_W, STRIP_H)]


def display_layout(slots=None):
    """[(strip box, UI box)] pairs: where each piece of the strip goes on screen."""
    ui_w, ui_h = ui_size()

    if not is_landscape() or not slots:
        scale = min(ui_w / STRIP_W, ui_h / STRIP_H)
        sw = max(1, int(STRIP_W * scale))
        sh = max(1, int(STRIP_H * scale))
        dest = ((ui_w - sw) // 2, (ui_h - sh) // 2, sw, sh)
        return [((0, 0, STRIP_W, STRIP_H), dest)]

    # Landscape: the strip cut in half between the middle photos, halves side by side,
    # so the frame's header and footer stay visible.
    halves = strip_halves(slots)
    cell_w = ui_w // len(halves)
    half_h = max(b[3] - b[1] for b in halves)
    scale = min(
        (cell_w - 2 * LANDSCAPE_CELL_PAD) / STRIP_W,
        (ui_h - 2 * LANDSCAPE_CELL_PAD) / half_h,
    )

    layout = []
    for col, half in enumerate(halves):
        dw = max(1, int((half[2] - half[0]) * scale))
        dh = max(1, int((half[3] - half[1]) * scale))
        dx = col * cell_w + (cell_w - dw) // 2
        # Left half hangs from the top, right half sits on the bottom: one strip, folded.
        dy = LANDSCAPE_CELL_PAD if col == 0 else ui_h - LANDSCAPE_CELL_PAD - dh
        layout.append((half, (dx, dy, dw, dh)))
    return layout


def render_strip_to_ui(strip, layout, resample, transparent=False):
    if transparent:
        canvas = Image.new("RGBA", ui_size(), (0, 0, 0, 0))
    else:
        canvas = Image.new("RGB", ui_size(), "black")
        strip = strip.convert("RGB")

    for src, (dx, dy, dw, dh) in layout:
        piece = strip.crop(src).resize((dw, dh), resample)
        canvas.paste(piece, (dx, dy), piece if transparent else None)
    return canvas


def map_strip_box_to_ui(box, layout):
    left, top, right, bottom = box
    for (sx0, sy0, sx1, sy1), (dx, dy, dw, dh) in layout:
        if sy0 <= (top + bottom) / 2 < sy1:
            left, right = max(left, sx0), min(right, sx1)
            top, bottom = max(top, sy0), min(bottom, sy1)
            kx = dw / (sx1 - sx0)
            ky = dh / (sy1 - sy0)
            return (
                dx + int((left - sx0) * kx),
                dy + int((top - sy0) * ky),
                max(1, int((right - left) * kx)),
                max(1, int((bottom - top) * ky)),
            )
    return None


def saved_strip_slots(img):
    # Strips saved by this version carry their slot layout in the JPEG comment.
    try:
        data = json.loads(img.info.get("comment", b"") or b"null")
        if isinstance(data, dict) and data.get("slots"):
            return _normalize_slots(data["slots"])
    except Exception:
        pass
    return None


def compose_display():
    strip = None
    slots = None
    if mode == "browse" and browse_strips:
        browse_path = browse_strips[browse_index]
        try:
            with Image.open(browse_path) as saved:
                slots = saved_strip_slots(saved)
                strip = saved.convert("RGB")
        except Exception as e:
            print(f"Could not open saved strip: {e}")
            strip = None

    if strip is None:
        strip = compose_single_strip(live_photos)
        slots = current_frame_slots()

    return render_strip_to_ui(strip, display_layout(slots), Image.LANCZOS)


def should_show_live_preview():
    return (
        lcd is not None
        and not screen_asleep
        and not menu_open
        and mode == "creation"
        and not strip_is_full()
        and 0 <= current_slot < current_capacity()
    )


def _live_preview_cache_key():
    return (
        screen_rotation,
        current_slot,
        current_frame_index,
        tuple(id(p) if p is not None else None for p in live_photos),
        _mtime(frames[current_frame_index]) if frames else None,
        _mtime(frames[current_frame_index].with_suffix(".json")) if frames else None,
    )


def _ensure_live_preview_base():
    global _live_preview_key, _live_preview_photos, _live_preview_frame
    global _live_preview_slot_box

    key = _live_preview_cache_key()
    if (
        key == _live_preview_key
        and _live_preview_photos is not None
        and _live_preview_slot_box is not None
    ):
        return True

    slots = current_frame_slots()
    if current_slot < 0 or current_slot >= len(slots):
        _invalidate_live_preview()
        return False

    layout = display_layout(slots)
    photos_strip = compose_single_strip(live_photos, include_frame=False)
    photos_canvas = render_strip_to_ui(photos_strip, layout, Image.BILINEAR)

    frame = load_current_frame()
    frame_canvas = None
    if frame is not None:
        frame_canvas = render_strip_to_ui(frame, layout, Image.BILINEAR, transparent=True)

    x, y, w, h = slots[current_slot]
    slot_box = map_strip_box_to_ui((
        max(0, x - SLOT_BLEED),
        max(0, y - SLOT_BLEED),
        min(STRIP_W, x + w + SLOT_BLEED),
        min(STRIP_H, y + h + SLOT_BLEED),
    ), layout)
    if slot_box is None:
        _invalidate_live_preview()
        return False

    _live_preview_key = key
    _live_preview_photos = photos_canvas
    _live_preview_frame = frame_canvas
    _live_preview_slot_box = slot_box
    return True


def yuv420_to_image(yuv, w, h):
    # I420 buffer: Y plane, then U and V planes at half resolution, rows padded to stride.
    stride = yuv.shape[1]
    y = yuv[:h, :w].astype(np.float32)
    u = yuv[h:h + h // 4].reshape(h // 2, stride // 2)[:, :w // 2]
    v = yuv[h + h // 4:h + h // 2].reshape(h // 2, stride // 2)[:, :w // 2]
    u = u.repeat(2, axis=0).repeat(2, axis=1).astype(np.float32) - 128.0
    v = v.repeat(2, axis=0).repeat(2, axis=1).astype(np.float32) - 128.0

    rgb = np.empty((h, w, 3), dtype=np.float32)
    rgb[:, :, 0] = y + 1.402 * v
    rgb[:, :, 1] = y - 0.344136 * u - 0.714136 * v
    rgb[:, :, 2] = y + 1.772 * u
    return Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8), "RGB")


# Film looks: tone curve with faded blacks (+ warm tint for colour), vignette, grain.
FILM_LOOKS = {
    "film": {"bw": False, "grain": 5.0, "vignette": 0.28},
    "film_bw": {"bw": True, "grain": 8.0, "vignette": 0.32},
}
_film_luts = {}
_vignettes = {}


def _film_lut(bw):
    if bw not in _film_luts:
        x = np.arange(256) / 255.0
        s_curve = 0.5 - 0.5 * np.cos(np.pi * x)
        tone = (0.55 if bw else 0.65) * x + (0.45 if bw else 0.35) * s_curve
        tone = 0.05 + 0.9 * tone  # lifted blacks, softened whites
        if bw:
            r = g = b = tone
        else:
            r = tone ** 0.93
            g = tone ** 0.98
            b = 0.04 + 0.92 * tone ** 1.06  # bluer shadows, warmer highlights
        lut = []
        for channel in (r, g, b):
            lut.extend(np.clip(channel * 255.0, 0, 255).astype(np.uint8).tolist())
        _film_luts[bw] = lut
    return _film_luts[bw]


def _vignette(w, h, strength):
    key = (w, h, strength)
    if key not in _vignettes:
        ys = np.linspace(-1.0, 1.0, h, dtype=np.float32)[:, None]
        xs = np.linspace(-1.0, 1.0, w, dtype=np.float32)[None, :]
        r2 = (xs * xs + ys * ys) / 2.0
        _vignettes[key] = (1.0 - strength * r2 ** 1.5)[..., None]
    return _vignettes[key]


def apply_colour_look(img):
    look = FILM_LOOKS.get(settings["colour"])
    if look is None:
        return img
    img = img.convert("RGB").point(_film_lut(look["bw"]))
    a = np.asarray(img, dtype=np.float32)
    h, w = a.shape[:2]
    a = a * _vignette(w, h, look["vignette"])
    # Grain at half resolution so it stays visible once the photo is scaled down.
    grain = np.random.normal(0.0, look["grain"], ((h + 1) // 2, (w + 1) // 2))
    grain = grain.astype(np.float32).repeat(2, axis=0).repeat(2, axis=1)[:h, :w]
    a += grain[..., None]
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), "RGB")


def capture_preview_image():
    if LORES_FORMAT == "YUV420":
        lores = picam2.capture_array("lores", wait=CAMERA_TIMEOUT_SECONDS)
        img = yuv420_to_image(lores, PREVIEW_W, PREVIEW_H)
    else:
        img = picam2.capture_image("lores", wait=CAMERA_TIMEOUT_SECONDS)
    if settings["mirror"]:
        img = img.transpose(Image.FLIP_LEFT_RIGHT)
    return apply_colour_look(img)


def update_live_slot_preview(overlay_text=None, force=False):
    global _live_preview_last_ts

    if not should_show_live_preview():
        return False

    now = time.monotonic()
    if not force and now - _live_preview_last_ts < (1.0 / LIVE_PREVIEW_FPS):
        return False

    if not _ensure_live_preview_base():
        return False

    try:
        cam = capture_preview_image()
    except TimeoutError:
        camera_failed("live preview")
    except Exception as e:
        print(f"Live preview capture failed: {e}")
        return False
    if cam is None:
        return False

    sx, sy, sw, sh = _live_preview_slot_box
    fitted = center_crop_to_slot(cam, sw, sh, resample=Image.BILINEAR)

    canvas = _live_preview_photos.copy()
    canvas.paste(fitted, (sx, sy))
    if _live_preview_frame is not None:
        canvas = canvas.convert("RGBA")
        canvas.alpha_composite(_live_preview_frame)
        canvas = canvas.convert("RGB")

    _live_preview_last_ts = now
    update_lcd(canvas, overlay_text=overlay_text, fast=True)
    return True


def pil_to_pygame_surface(img):
    img = img.convert("RGB")
    return pygame.image.fromstring(img.tobytes(), img.size, "RGB")


def _draw_centered_banner(img, text):
    draw = ImageDraw.Draw(img, "RGBA")

    try:
        font = ImageFont.load_default(size=24)
    except TypeError:
        font = ImageFont.load_default()

    lines = text.split("\n")
    line_sizes = []
    max_w = 0
    total_h = 0
    line_gap = 6
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        line_sizes.append((w, h, bbox[0], bbox[1]))
        max_w = max(max_w, w)
        total_h += h
    if len(lines) > 1:
        total_h += line_gap * (len(lines) - 1)

    cx = img.width // 2
    cy = img.height // 2
    pad = 12

    box = [
        cx - max_w // 2 - pad,
        cy - total_h // 2 - pad,
        cx + max_w // 2 + pad,
        cy + total_h // 2 + pad,
    ]
    draw.rectangle(box, fill=(0, 0, 0, 190))

    y = cy - total_h // 2
    for (w, h, bx, by), line in zip(line_sizes, lines):
        draw.text(
            (cx - w // 2 - bx, y - by),
            line,
            font=font,
            fill=(255, 255, 255, 255),
        )
        y += h + line_gap


def update_lcd(img=None, overlay_text=None, fast=False):
    global _lcd_xform
    if lcd is None or screen_asleep:
        return

    try:
        pygame.event.pump()

        screen_w, screen_h = lcd.get_size()

        if img is None:
            img = render_menu(_menu_last_cam) if menu_open else compose_display()

        img = img.copy()
        if countdown_value is not None:
            _draw_countdown(img)
        if overlay_text is not None:
            _draw_centered_banner(img, overlay_text)
        elif not menu_open:
            if in_review() and review_started is not None:
                _draw_review_hint(img, review_seconds_left())
            _draw_gear_button(img)
        _draw_battery_indicator(img)

        img = img.rotate(screen_rotation, expand=True)

        img_w, img_h = img.size
        scale = min(screen_w / img_w, screen_h / img_h)

        new_w = int(img_w * scale)
        new_h = int(img_h * scale)

        resample = Image.BILINEAR if fast else Image.LANCZOS
        img = img.resize((new_w, new_h), resample)
        surface = pil_to_pygame_surface(img)

        lcd.fill((0, 0, 0))

        x = (screen_w - new_w) // 2
        y = (screen_h - new_h) // 2

        lcd.blit(surface, (x, y))
        pygame.display.flip()
        _lcd_xform = (x, y, scale)

    except pygame.error as e:
        print(f"LCD update failed: {e}")


def _backlight_path():
    for path in sorted(Path("/sys/class/backlight").glob("*/brightness")):
        if os.access(path, os.W_OK):
            return path
    return None


_backlight = _backlight_path()
_backlight_on_level = None


def _set_backlight(on):
    global _backlight_on_level
    if _backlight is None:
        return False
    try:
        if on:
            level = _backlight_on_level
            if level is None:
                level = (_backlight.parent / "max_brightness").read_text().strip()
            _backlight.write_text(f"{level}\n")
        else:
            _backlight_on_level = _backlight.read_text().strip()
            _backlight.write_text("0\n")
        return True
    except OSError as e:
        print(f"Backlight control failed: {e}")
        return False


def restore_backlight_if_dark():
    # A crash while asleep would leave the panel dark for the next run or the console.
    try:
        if _backlight is not None and _backlight.read_text().strip() == "0":
            _set_backlight(True)
    except OSError:
        pass


restore_backlight_if_dark()


def note_activity():
    global last_activity
    last_activity = time.monotonic()


def sleep_screen():
    global screen_asleep
    if lcd is None or screen_asleep:
        return
    print("Screen off (idle).")
    # Black frame first, so the panel is dark even without backlight control.
    lcd.fill((0, 0, 0))
    pygame.display.flip()
    _set_backlight(False)
    screen_asleep = True
    close_menu(redraw=False)
    # Left streaming with nothing reading it, the camera can stall; it also saves power.
    stop_camera()


def wake_screen(camera=True):
    """Turns the screen back on. Returns True if it was asleep."""
    global screen_asleep
    note_activity()
    if not screen_asleep:
        return False
    screen_asleep = False
    print("Screen on.")
    if camera:
        start_camera()
    _invalidate_live_preview()
    update_lcd()
    _set_backlight(True)
    return True


def flash_message(text, seconds=1.0):
    if lcd is None:
        return

    wake_screen()
    update_lcd(overlay_text=text)
    time.sleep(seconds)
    update_lcd()


def save_preview():
    _invalidate_live_preview()
    preview = compose_display()

    path = BASE / "current_preview.jpg"
    preview.save(path, quality=90)

    print(f"Preview updated: {path}")

    update_lcd(preview)


def save_finished_strip():
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    jpg_archive_path = ARCHIVE_DIR / f"strip_{timestamp}.jpg"

    strip = compose_single_strip(live_photos)
    slots_json = json.dumps({"slots": current_frame_slots()[:len(live_photos)]})
    # Durable before returning: the raw captures are deleted right after this.
    write_file_durably(jpg_archive_path, lambda f: strip.convert("RGB").save(
        f, format="JPEG", quality=95, comment=slots_json.encode()))

    print("")
    print("FINISHED STRIP SAVED")
    print(f"JPG archive: {jpg_archive_path}")
    print("")

    return jpg_archive_path


def delete_live_captures():
    for path in live_capture_paths:
        delete_capture_file(path)


def clear_live_strip():
    global live_photos, live_capture_paths, current_slot

    capacity = current_capacity()
    live_photos = [None] * capacity
    live_capture_paths = [None] * capacity
    current_slot = 0
    _clear_photo_cache()


def start_fresh_strip():
    clear_live_strip()
    print("Started a fresh strip.")
    save_preview()


def save_and_advance():
    save_finished_strip()
    # The strip JPG is the keeper; raw captures are only needed until it's built.
    delete_live_captures()
    start_fresh_strip()
    flash_message("STRIP SAVED", seconds=0.8)


def in_review():
    return mode == "creation" and strip_is_full()


def retake_last_photo():
    global current_slot

    if current_slot <= 0:
        return
    current_slot -= 1
    live_photos[current_slot] = None
    delete_capture_file(live_capture_paths[current_slot])
    live_capture_paths[current_slot] = None
    _clear_photo_cache()
    print(f"Retaking photo {current_slot + 1}.")
    save_preview()
    flash_message("RETAKE", seconds=0.6)


def _draw_review_hint(img, seconds_left):
    draw = ImageDraw.Draw(img, "RGBA")
    try:
        font = ImageFont.load_default(size=18)
    except TypeError:
        font = ImageFont.load_default()

    lines = ["1x KEEP   2x RETAKE   3x FRAME", f"Keeping in {seconds_left}s"]
    line_h = 22
    bar_h = line_h * len(lines) + 10
    draw.rectangle((0, img.height - bar_h, img.width, img.height), fill=(0, 0, 0, 190))
    y = img.height - bar_h + 5
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        w = bbox[2] - bbox[0]
        draw.text(((img.width - w) // 2 - bbox[0], y - bbox[1]), line,
                  font=font, fill=(255, 255, 255, 255))
        y += line_h


countdown_value = None


def _draw_countdown(img):
    # Big number over the photo being taken, see-through enough to still pose.
    box = _live_preview_slot_box
    if box is None:
        box = (0, 0, img.width, img.height)
    x, y, w, h = box
    size = max(40, int(min(w, h) * 0.75))
    draw = ImageDraw.Draw(img, "RGBA")
    draw.text((x + w // 2, y + h // 2), str(countdown_value), font=menu_font(size, True),
              fill=(255, 255, 255, 215), stroke_width=max(2, size // 25),
              stroke_fill=(0, 0, 0, 200), anchor="mm")


def run_countdown():
    global countdown_value
    seconds = settings["countdown"]
    if not seconds or not should_show_live_preview():
        return
    end = time.monotonic() + seconds
    try:
        while (left := end - time.monotonic()) > 0:
            countdown_value = math.ceil(left)
            update_live_slot_preview(force=True)
            watchdog_ping()
            time.sleep(1.0 / LIVE_PREVIEW_FPS)
    finally:
        countdown_value = None
    # Presses made while counting down are not new photo requests.
    kept = []
    while not action_queue.empty():
        item = action_queue.get()
        if item[0] not in ("short", "toggle_mode"):
            kept.append(item)
    for item in kept:
        action_queue.put(item)


def take_next_photo():
    global current_slot

    capacity = current_capacity()
    if current_slot >= capacity:
        print("Strip is already full; not taking another photo.")
        return

    run_countdown()

    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    capture_path = CAPTURE_DIR / f"capture_{timestamp}.jpg"

    print(f"Capturing photo {current_slot + 1}/{capacity}...")
    try:
        picam2.capture_file(str(capture_path), wait=CAMERA_TIMEOUT_SECONDS * 2)
    except TimeoutError:
        camera_failed("photo capture")

    img = Image.open(capture_path).convert("RGB")
    if img.width > CAPTURE_W or img.height > CAPTURE_H:
        img.thumbnail((CAPTURE_W, CAPTURE_H), Image.BILINEAR)
    img = apply_colour_look(img)
    live_photos[current_slot] = img
    live_capture_paths[current_slot] = capture_path

    current_slot += 1

    save_preview()

    if current_slot >= capacity:
        print("Strip full: review it (1x keep, 2x retake, 3x frame).")


def browsable_paths():
    entries = []
    for path in ARCHIVE_DIR.glob("*.jpg"):
        if path.name.endswith("_base.jpg") or path.name.endswith("_clean.jpg"):
            continue
        entries.append(path)
    return sorted(entries, key=lambda p: _mtime(p) or 0, reverse=True)


def enter_browse_mode():
    global mode, browse_strips, browse_index

    browse_strips = browsable_paths()
    if not browse_strips:
        print("Nothing saved to browse yet.")
        flash_message("NOTHING TO BROWSE", seconds=1.0)
        return False

    mode = "browse"
    browse_index = 0
    print(
        f"Entered browse mode: {browse_index + 1}/{len(browse_strips)}: "
        f"{browse_strips[browse_index].name}"
    )
    save_preview()
    flash_message("BROWSE", seconds=0.6)
    return True


def enter_creation_mode(announce=True):
    global mode

    if mode != "creation":
        mode = "creation"
        if announce:
            print("Returned to creation mode.")
            flash_message("CREATE", seconds=0.6)
        save_preview()


def toggle_mode():
    if mode == "creation":
        enter_browse_mode()
    else:
        enter_creation_mode()


def _refresh_browse_list():
    global browse_index, browse_strips

    browse_strips = browsable_paths()
    if not browse_strips:
        print("Nothing left to browse.")
        enter_creation_mode()
        return False

    if browse_index >= len(browse_strips):
        browse_index = len(browse_strips) - 1
    return True


def browse_step(step):
    global browse_index

    if not _refresh_browse_list():
        return

    browse_index = (browse_index + step) % len(browse_strips)

    print(
        f"Browsing {browse_index + 1}/{len(browse_strips)}: "
        f"{browse_strips[browse_index].name}"
    )
    save_preview()


def next_frame_same_capacity():
    global current_frame_index

    if not frames:
        print("No frame PNGs found in ~/photobooth/frames")
        return

    capacity = current_capacity()
    group = indices_for_capacity(capacity)
    if not group:
        print(f"No frames with {capacity} slots.")
        return

    try:
        pos = group.index(current_frame_index)
        current_frame_index = group[(pos + 1) % len(group)]
    except ValueError:
        current_frame_index = group[0]

    print(
        f"Changed frame to: {frames[current_frame_index].name} "
        f"(slots={current_capacity()})"
    )
    save_preview()


def toggle_strip_capacity():
    global current_frame_index, current_slot

    if not frames:
        print("No frame PNGs found in ~/photobooth/frames")
        return

    capacity = current_capacity()
    target = 3 if capacity == 4 else 4
    group = indices_for_capacity(target)
    if not group:
        print(f"No {target}-picture frames available yet.")
        flash_message(f"NO {target}-PIC FRAMES", seconds=1.0)
        return

    if capacity == 4 and target == 3 and current_slot >= 4:
        current_slot = 3
        live_photos[3] = None
        delete_capture_file(live_capture_paths[3])
        live_capture_paths[3] = None
        _clear_photo_cache()
        print("Removed 4th photo to fit 3-picture frame.")

    current_frame_index = group[0]
    resize_live_photos(target)

    print(
        f"Switched to {target}-picture frames: {frames[current_frame_index].name}"
    )
    save_preview()
    flash_message(f"{target}-PIC", seconds=0.6)


def load_strip_image(path):
    try:
        strip = Image.open(path).convert("RGB")
    except Exception as e:
        print(f"Could not open saved strip: {e}")
        return None

    if strip.size != (STRIP_W, STRIP_H):
        strip = strip.resize((STRIP_W, STRIP_H), Image.LANCZOS)
    return strip


def make_duplicate_print(strip_img):
    print_img = Image.new("RGB", (PRINT_W, PRINT_H), "white")
    print_img.paste(strip_img, (0, 0))
    print_img.paste(strip_img, (STRIP_W, 0))
    return print_img


def detect_printer():
    if PRINTER_NAME:
        return PRINTER_NAME

    try:
        result = subprocess.run(
            ["lpstat", "-p"], capture_output=True, text=True, timeout=10
        )
    except Exception:
        return None

    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0] == "printer":
            name = parts[1]
            low = name.lower()
            if "selphy" in low or "cp1500" in low or "canon" in low:
                return name

    return None


def _prepare_print_image(path):
    # Shrink onto a white canvas so borderless overscan crops margin, not strips.
    if PRINT_SCALE >= 100:
        return str(path), None

    try:
        img = Image.open(path).convert("RGB")
    except Exception as e:
        print(f"Could not prepare print image {path}: {e}")
        return str(path), None

    w, h = img.size
    scale = PRINT_SCALE / 100.0
    new_w = max(1, int(round(w * scale)))
    new_h = max(1, int(round(h * scale)))

    shrunk = img.resize((new_w, new_h), Image.LANCZOS)
    canvas = Image.new("RGB", (w, h), "white")
    canvas.paste(shrunk, ((w - new_w) // 2, (h - new_h) // 2))

    try:
        fd, tmp_path = tempfile.mkstemp(prefix="print_", suffix=".jpg")
        os.close(fd)
        canvas.save(tmp_path, quality=95)
        return tmp_path, tmp_path
    except Exception as e:
        print(f"Could not write scaled print image: {e}")
        return str(path), None


def send_to_printer(path):
    printer = detect_printer()

    print_path, temp_path = _prepare_print_image(path)

    cmd = ["lp"]
    if printer:
        cmd += ["-d", printer]
    cmd += PRINT_OPTIONS + [print_path]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    except FileNotFoundError:
        print("Print failed: `lp` not found (is CUPS installed?)")
        return False
    except Exception as e:
        print(f"Print failed: {e}")
        return False
    finally:
        if temp_path is not None:
            try:
                Path(temp_path).unlink()
            except OSError:
                pass

    if result.returncode != 0:
        print(f"Print failed (rc={result.returncode}): {result.stderr.strip()}")
        return False

    print(f"Print submitted: {result.stdout.strip()}")
    return True


_print_busy = threading.Event()


def _build_and_send_print(path):
    strip = load_strip_image(path)
    if strip is None:
        return False

    fd, tmp = tempfile.mkstemp(prefix="print_", suffix=".jpg")
    os.close(fd)
    tmp_path = Path(tmp)
    try:
        make_duplicate_print(strip).save(tmp_path, quality=95)
        print(f"Built duplicate print: {tmp_path}")
        return send_to_printer(tmp_path)
    finally:
        try:
            tmp_path.unlink()
        except OSError:
            pass


def _print_worker(path):
    # Runs off the UI thread; reports back via action_queue, never touches pygame.
    ok = False
    try:
        ok = _build_and_send_print(path)
    except Exception as e:
        print(f"Print failed: {e}")
    finally:
        _print_busy.clear()
        action_queue.put(("print_done", ok))


def print_current_browsed_item():
    if not browse_strips:
        return

    if _print_busy.is_set():
        print("Print already in progress; ignoring.")
        flash_message("ALREADY PRINTING", seconds=0.8)
        return

    path = browse_strips[browse_index]
    _print_busy.set()
    threading.Thread(target=_print_worker, args=(path,), daemon=True).start()
    flash_message("PRINTING...", seconds=0.6)


def shutdown_pi(message="Shutting down..."):
    print("Shutting down Pi safely...")
    wake_screen(camera=False)

    if lcd is not None:
        try:
            screen_w, screen_h = lcd.get_size()

            img = Image.new("RGB", ui_size(), "black")
            _draw_centered_banner(img, message)
            img = img.rotate(screen_rotation, expand=True)

            img_w, img_h = img.size
            scale = min(screen_w / img_w, screen_h / img_h)
            new_w = int(img_w * scale)
            new_h = int(img_h * scale)
            img = img.resize((new_w, new_h), Image.LANCZOS)
            surface = pil_to_pygame_surface(img)

            lcd.fill((0, 0, 0))
            x = (screen_w - new_w) // 2
            y = (screen_h - new_h) // 2
            lcd.blit(surface, (x, y))
            pygame.display.flip()
            time.sleep(1)
        except Exception as e:
            print(f"Could not show shutdown screen: {e}")

    subprocess.run(["sudo", "-n", "shutdown", "now"], check=False)


class FuelGauge:
    """MAX17040 on the Geekworm X1200. Registers are 16-bit big-endian."""

    REG_VCELL = 0x02
    REG_SOC = 0x04
    REG_VERSION = 0x08

    def __init__(self, bus_num, addr):
        from smbus2 import SMBus

        self.addr = addr
        self.bus = SMBus(bus_num)
        try:
            self._read(self.REG_VERSION)
        except Exception:
            self.bus.close()
            raise

    def _read(self, reg):
        hi, lo = self.bus.read_i2c_block_data(self.addr, reg, 2)
        return (hi << 8) | lo

    def volts(self):
        # 12-bit reading in the top bits, 1.25 mV per LSB.
        return (self._read(self.REG_VCELL) >> 4) * 1.25 / 1000

    def percent(self):
        return max(0.0, min(100.0, self._read(self.REG_SOC) / 256))


def init_battery():
    try:
        gauge = FuelGauge(BATTERY_I2C_BUS, BATTERY_I2C_ADDR)
    except Exception as e:
        print(f"No X1200 fuel gauge detected ({e}); battery display disabled.")
        return None, None

    power_pin = None
    if POWER_LOSS_GPIO is not None:
        try:
            power_pin = InputDevice(POWER_LOSS_GPIO, pull_up=None, active_state=True)
        except Exception as e:
            print(f"Power-loss detect on GPIO {POWER_LOSS_GPIO} unavailable: {e}")

    print("X1200 fuel gauge detected.")
    return gauge, power_pin


battery_gauge, power_detect = init_battery()
battery_percent = None
battery_volts = None
battery_external_power = False
_battery_last_poll = 0.0
_battery_read_failures = 0
_battery_critical_count = 0
_battery_low_warned = False


def battery_level_color():
    if battery_percent is None:
        return (255, 255, 255)
    if battery_percent <= BATTERY_CRITICAL_PERCENT:
        return (255, 60, 60)
    if battery_percent <= BATTERY_LOW_PERCENT:
        return (255, 190, 0)
    return (255, 255, 255)


def _draw_battery_indicator(img):
    if battery_percent is None:
        return

    draw = ImageDraw.Draw(img, "RGBA")
    try:
        font = ImageFont.load_default(size=18)
    except TypeError:
        font = ImageFont.load_default()

    color = battery_level_color()
    text = f"{battery_percent:.0f}%"
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]

    body_w, body_h = 30, 14
    right = img.width - 10
    top = 10
    body = (right - body_w - 3, top, right - 3, top + body_h)
    draw.rectangle(body, outline=color, width=2)
    draw.rectangle((right - 3, top + 4, right, top + body_h - 4), fill=color)
    fill_w = int((body_w - 6) * battery_percent / 100)
    if fill_w > 0:
        draw.rectangle(
            (body[0] + 3, top + 3, body[0] + 3 + fill_w, top + body_h - 3), fill=color
        )
    if battery_external_power:
        cx, cy = (body[0] + body[2]) // 2, top + body_h // 2
        draw.polygon(
            [(cx + 2, cy - 6), (cx - 4, cy + 1), (cx, cy + 1),
             (cx - 2, cy + 6), (cx + 4, cy - 1), (cx, cy - 1)],
            fill=(0, 0, 0), outline=(255, 255, 255),
        )

    draw.text((body[0] - 6 - text_w - bbox[0], top - 3 - bbox[1] + 1), text,
              font=font, fill=color)


def save_partial_strip_before_shutdown():
    if not any(p is not None for p in live_photos):
        return
    try:
        save_finished_strip()
        delete_live_captures()
    except Exception as e:
        print(f"Could not save partial strip: {e}")


def poll_battery():
    """Returns True if the on-screen battery state changed."""
    global battery_percent, battery_volts, battery_external_power
    global _battery_last_poll, _battery_read_failures, _battery_critical_count
    global _battery_low_warned

    if battery_gauge is None:
        return False

    now = time.monotonic()
    if _battery_last_poll and now - _battery_last_poll < BATTERY_POLL_SECONDS:
        return False
    _battery_last_poll = now

    before = (
        None if battery_percent is None else round(battery_percent),
        battery_external_power,
    )

    try:
        percent = battery_gauge.percent()
        volts = battery_gauge.volts()
    except Exception as e:
        _battery_read_failures += 1
        print(f"Battery read failed ({_battery_read_failures}): {e}")
        if _battery_read_failures >= 3 and battery_percent is not None:
            battery_percent = None
            return True
        return False

    _battery_read_failures = 0
    battery_percent = percent
    battery_volts = volts
    battery_external_power = power_detect is not None and power_detect.is_active

    critical = (
        percent <= BATTERY_CRITICAL_PERCENT or volts <= BATTERY_CRITICAL_VOLTS
    )
    if critical and not battery_external_power:
        _battery_critical_count += 1
        print(
            f"Battery critical: {percent:.0f}% {volts:.2f}V "
            f"({_battery_critical_count}/{BATTERY_CRITICAL_READINGS})"
        )
        if _battery_critical_count >= BATTERY_CRITICAL_READINGS:
            save_partial_strip_before_shutdown()
            shutdown_pi("BATTERY EMPTY\nShutting down...")
            return False
    else:
        _battery_critical_count = 0

    if percent <= BATTERY_LOW_PERCENT and not battery_external_power:
        if not _battery_low_warned:
            _battery_low_warned = True
            print(f"Battery low: {percent:.0f}% {volts:.2f}V")
            flash_message(f"BATTERY LOW\n{percent:.0f}%", seconds=1.5)
    elif percent > BATTERY_LOW_PERCENT + 3 or battery_external_power:
        _battery_low_warned = False

    return before != (round(percent), battery_external_power)


def cycle_screen_rotation():
    i = SCREEN_ROTATIONS.index(screen_rotation)
    set_setting("rotation", SCREEN_ROTATIONS[(i + 1) % len(SCREEN_ROTATIONS)])
    label = SCREEN_ROTATION_LABELS[screen_rotation]
    flash_message(f"SCREEN\n{label}", seconds=1.0)


# ---------------------------------------------------------------------------
# Touchscreen settings menu (opened with the gear icon in the top-left corner)
# ---------------------------------------------------------------------------

MENU_BG = (22, 22, 26)
MENU_ROW = (46, 46, 54)
MENU_TEXT = (255, 255, 255)
MENU_DIM = (150, 150, 160)
MENU_ACCENT = (255, 190, 40)
MENU_DONE = (40, 150, 70)
MENU_DANGER = (190, 45, 45)
GEAR_SIZE = 44
GEAR_HIT = 80  # generous tap area around the gear
TAP_DEBOUNCE_SECONDS = 0.3
SHUTDOWN_CONFIRM_SECONDS = 4

_fonts = {}


def menu_font(size, bold=False):
    key = (size, bold)
    if key not in _fonts:
        name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
        try:
            _fonts[key] = ImageFont.truetype(f"/usr/share/fonts/truetype/dejavu/{name}", size)
        except OSError:
            _fonts[key] = ImageFont.load_default(size=size)
    return _fonts[key]


def _draw_text_centered(draw, box, text, font, fill):
    x0, y0, x1, y1 = box
    bbox = draw.textbbox((0, 0), text, font=font)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text((x0 + (x1 - x0 - w) // 2 - bbox[0], y0 + (y1 - y0 - h) // 2 - bbox[1]),
              text, font=font, fill=fill)


def _fit_font(draw, text, max_w, size, bold=True):
    while size > 10:
        font = menu_font(size, bold)
        bbox = draw.textbbox((0, 0), text, font=font)
        if bbox[2] - bbox[0] <= max_w:
            return font
        size -= 1
    return menu_font(size, bold)


def _draw_gear(draw, cx, cy, r, color, bg):
    teeth = 8
    for i in range(teeth):
        a = 2 * math.pi * i / teeth
        dx, dy = math.cos(a), math.sin(a)
        px, py = -dy, dx
        tw, r0, r1 = r * 0.22, r * 0.6, r
        draw.polygon([
            (cx + dx * r0 + px * tw, cy + dy * r0 + py * tw),
            (cx + dx * r1 + px * tw, cy + dy * r1 + py * tw),
            (cx + dx * r1 - px * tw, cy + dy * r1 - py * tw),
            (cx + dx * r0 - px * tw, cy + dy * r0 - py * tw),
        ], fill=color)
    rb = r * 0.78
    draw.ellipse((cx - rb, cy - rb, cx + rb, cy + rb), fill=color)
    rh = r * 0.32
    draw.ellipse((cx - rh, cy - rh, cx + rh, cy + rh), fill=bg)


def _draw_gear_button(img):
    if lcd is None:
        return
    draw = ImageDraw.Draw(img, "RGBA")
    m = 8
    draw.ellipse((m, m, m + GEAR_SIZE, m + GEAR_SIZE), fill=(0, 0, 0, 150))
    c = m + GEAR_SIZE / 2
    _draw_gear(draw, c, c, GEAR_SIZE * 0.36, (255, 255, 255, 230), (0, 0, 0, 255))


menu_open = False
menu_tab = "camera"
menu_buttons = []  # [((x0, y0, x1, y1) in UI coords, callback)]
_menu_last_cam = None
_menu_last_ts = 0.0
_shutdown_confirm_until = 0.0
_lcd_xform = None  # (x, y, scale) of the last frame drawn on the panel
_last_tap_ts = 0.0


def open_menu():
    global menu_open, menu_tab, _menu_last_cam
    print("Settings menu opened.")
    menu_open = True
    menu_tab = "camera"
    _menu_last_cam = None
    update_menu(force=True)


def close_menu(redraw=True):
    global menu_open
    if not menu_open:
        return
    print("Settings menu closed.")
    menu_open = False
    _invalidate_live_preview()
    if redraw:
        update_lcd()


def set_menu_tab(tab):
    global menu_tab
    menu_tab = tab


def step_setting(key, step):
    choices = [v for v, _ in SETTING_DEFS[key][1]]
    i = choices.index(settings[key]) + step
    if 0 <= i < len(choices):
        set_setting(key, choices[i])


def press_shutdown():
    global _shutdown_confirm_until
    if time.monotonic() < _shutdown_confirm_until:
        close_menu(redraw=False)
        shutdown_pi()
    else:
        _shutdown_confirm_until = time.monotonic() + SHUTDOWN_CONFIRM_SECONDS


def _draw_setting_row(draw, box, key, buttons):
    x0, y0, x1, y1 = box
    label, choices = SETTING_DEFS[key][0], SETTING_DEFS[key][1]
    values = [v for v, _ in choices]
    i = values.index(settings[key])
    text = choices[i][1]
    h = y1 - y0
    arrow_w = min(72, h + 12)

    draw.rounded_rectangle(box, radius=10, fill=MENU_ROW)
    for direction, ax0, enabled in (
        (-1, x0, i > 0),
        (1, x1 - arrow_w, i < len(values) - 1),
    ):
        abox = (ax0, y0, ax0 + arrow_w, y1)
        color = MENU_ACCENT if enabled else (80, 80, 88)
        cx, cy, t = (abox[0] + abox[2]) / 2, (y0 + y1) / 2, min(14, h * 0.25)
        if direction < 0:
            pts = [(cx + t * 0.7, cy - t), (cx + t * 0.7, cy + t), (cx - t * 0.9, cy)]
        else:
            pts = [(cx - t * 0.7, cy - t), (cx - t * 0.7, cy + t), (cx + t * 0.9, cy)]
        draw.polygon(pts, fill=color)
        buttons.append((abox, lambda k=key, d=direction: step_setting(k, d)))

    mid = (x0 + arrow_w, y0, x1 - arrow_w, y1)
    max_w = mid[2] - mid[0] - 8
    label_font = menu_font(13 if h < 64 else 15)
    value_font = _fit_font(draw, text, max_w, 20 if h < 64 else 22)
    split = y0 + int(h * 0.42)
    _draw_text_centered(draw, (mid[0], y0 + 2, mid[2], split), label, label_font, MENU_DIM)
    _draw_text_centered(draw, (mid[0], split, mid[2], y1 - 4), text, value_font, MENU_TEXT)


def _draw_setting_rows(draw, area, keys, buttons, max_row_h=76):
    x0, y0, x1, y1 = area
    gap = 6
    row_h = min(max_row_h, (y1 - y0 + gap) // len(keys) - gap)
    for n, key in enumerate(keys):
        top = y0 + n * (row_h + gap)
        _draw_setting_row(draw, (x0, top, x1, top + row_h), key, buttons)
    return y0 + len(keys) * (row_h + gap)


HELP_LINES = [
    "BUTTON: 1 press = photo   2 = next frame",
    "3 = 3 or 4 photos   hold 1 sec = browse",
    "In browse: 1 = older  2 = newer  3 = print",
    "Hold 6 sec = shut down",
]


def render_menu(cam=None):
    global menu_buttons
    w, h = ui_size()
    img = Image.new("RGB", (w, h), MENU_BG)
    draw = ImageDraw.Draw(img)
    buttons = []
    pad = 8
    bar_h = 64

    tab_w = 136 if w < 600 else 160
    x = pad
    for tab, text in (("camera", "CAMERA"), ("booth", "BOOTH")):
        box = (x, pad, x + tab_w, bar_h - 6)
        active = tab == menu_tab
        draw.rounded_rectangle(box, radius=10, fill=MENU_ACCENT if active else MENU_ROW)
        _draw_text_centered(draw, box, text, menu_font(20, True),
                            (0, 0, 0) if active else MENU_TEXT)
        buttons.append((box, lambda t=tab: set_menu_tab(t)))
        x += tab_w + pad
    done = (w - pad - 120, pad, w - pad, bar_h - 6)
    draw.rounded_rectangle(done, radius=10, fill=MENU_DONE)
    _draw_text_centered(draw, done, "DONE", menu_font(20, True), MENU_TEXT)
    buttons.append((done, close_menu))

    if menu_tab == "camera":
        keys = [k for k, _, _, _ in CAMERA_SETTINGS]
        if is_landscape():
            pw = w // 2 - 2 * pad
            ph = pw * PREVIEW_H // PREVIEW_W
            pbox = (pad, bar_h + (h - bar_h - ph) // 2, pad + pw, 0)
            rows = (w // 2, bar_h + 2, w - pad, h - pad)
        else:
            pw = w - 2 * pad
            ph = pw * PREVIEW_H // PREVIEW_W
            pbox = (pad, bar_h + 2, pad + pw, 0)
            rows = (pad, bar_h + ph + 12, w - pad, h - pad)
        px, py = pbox[0], pbox[1]
        if cam is not None:
            img.paste(center_crop_to_slot(cam, pw, ph, resample=Image.BILINEAR), (px, py))
        else:
            draw.rectangle((px, py, px + pw, py + ph), fill=(0, 0, 0))
            _draw_text_centered(draw, (px, py, px + pw, py + ph), "CAMERA STARTING...",
                                menu_font(18), MENU_DIM)
        _draw_setting_rows(draw, rows, keys, buttons)
    else:
        keys = [k for k, _, _, _ in BOOTH_SETTINGS]
        # Leave room under the rows for the shut-down button and the help text.
        rows_h = min(len(keys) * 82, h - bar_h - 2 - 68 - (len(HELP_LINES) * 22 + 12))
        bottom = _draw_setting_rows(
            draw, (pad, bar_h + 2, w - pad, bar_h + 2 + rows_h), keys, buttons)
        confirming = time.monotonic() < _shutdown_confirm_until
        sbox = (pad, bottom + 4, w - pad, bottom + 4 + 64)
        draw.rounded_rectangle(sbox, radius=10, fill=MENU_DANGER)
        _draw_text_centered(draw, sbox, "TAP AGAIN TO SHUT DOWN" if confirming else "SHUT DOWN",
                            menu_font(22, True), MENU_TEXT)
        buttons.append((sbox, press_shutdown))
        y = sbox[3] + 12
        help_font = _fit_font(draw, max(HELP_LINES, key=len), w - 2 * pad, 16, bold=False)
        for line in HELP_LINES:
            if y + 20 > h:
                break
            _draw_text_centered(draw, (pad, y, w - pad, y + 20), line, help_font, MENU_DIM)
            y += 22

    menu_buttons = buttons
    return img


def update_menu(force=False):
    global _menu_last_cam, _menu_last_ts
    now = time.monotonic()
    if not force and now - _menu_last_ts < 1.0 / LIVE_PREVIEW_FPS:
        return
    _menu_last_ts = now
    if menu_tab == "camera" and camera_running:
        try:
            _menu_last_cam = capture_preview_image()
        except TimeoutError:
            camera_failed("settings preview")
        except Exception as e:
            print(f"Menu preview capture failed: {e}")
    update_lcd(fast=True)


def screen_to_ui(px, py):
    """Maps a point on the panel to UI coordinates (undoes the rotation and scaling)."""
    if _lcd_xform is None:
        return None
    ox, oy, scale = _lcd_xform
    rx, ry = (px - ox) / scale, (py - oy) / scale
    w, h = ui_size()
    if screen_rotation == 0:
        return rx, ry
    if screen_rotation == 180:
        return w - rx, h - ry
    if screen_rotation == 90:
        return w - ry, rx
    return ry, h - rx  # -90


def next_tap(events):
    """Returns the panel position of a new tap in these events, or None."""
    global _last_tap_ts
    screen_w, screen_h = lcd.get_size()
    for event in events:
        if event.type == pygame.FINGERDOWN:
            pos = (event.x * screen_w, event.y * screen_h)
        elif event.type == pygame.MOUSEBUTTONDOWN:
            pos = event.pos
        else:
            continue
        # A touch can arrive as both a finger and a mouse event; count it once.
        now = time.monotonic()
        if now - _last_tap_ts < TAP_DEBOUNCE_SECONDS:
            continue
        _last_tap_ts = now
        return pos
    return None


def handle_tap(pos):
    point = screen_to_ui(*pos)
    if point is None:
        return
    x, y = point
    print(f"Tap at panel {pos[0]:.0f},{pos[1]:.0f} -> screen {x:.0f},{y:.0f}")
    if menu_open:
        for (x0, y0, x1, y1), action in menu_buttons:
            if x0 <= x <= x1 and y0 <= y <= y1:
                action()
                if menu_open:
                    update_menu(force=True)
                return
    elif x < GEAR_HIT and y < GEAR_HIT:
        open_menu()


def handle_short_presses(count):
    global review_started

    if count == ROTATE_SCREEN_PRESSES:
        cycle_screen_rotation()
        return

    if mode == "browse":
        if count == 1:
            browse_step(1)
        elif count == 2:
            browse_step(-1)
        elif count == 3:
            print_current_browsed_item()
        else:
            print(f"Browse mode: ignoring {count} short presses")
        return

    if in_review():
        review_started = time.monotonic()
        if count == 1:
            save_and_advance()
        elif count == 2:
            retake_last_photo()
        elif count == 3:
            next_frame_same_capacity()
        else:
            print(f"Review: ignoring {count} short presses")
        return

    if count == 1:
        take_next_photo()
    elif count == 2:
        next_frame_same_capacity()
    elif count == 3:
        toggle_strip_capacity()
    else:
        print(f"Creation mode: ignoring {count} short presses")


def on_press():
    global press_started
    press_started = time.monotonic()


def on_release():
    global press_started

    if press_started is None:
        return

    now = time.monotonic()
    duration = now - press_started
    press_started = None

    if duration >= SHUTDOWN_PRESS_SECONDS:
        action_queue.put(("shutdown", now))
    elif duration >= LONG_PRESS_SECONDS:
        action_queue.put(("toggle_mode", now))
    else:
        action_queue.put(("short", now))


button.when_pressed = on_press
button.when_released = on_release

resize_live_photos(current_capacity())


print("")
print("Vintage photobooth app started.")
print("Modes: create (default) and browse — long press to switch.")
print("")

poll_battery()
save_preview()

pending_short_time = None
short_press_count = 0


def review_seconds_left():
    elapsed = time.monotonic() - review_started
    return max(0, int(settings["review"] - elapsed + 0.999))


def tick_review():
    """Starts the review timer when a strip fills, refreshes its countdown, auto-keeps."""
    global review_started, _review_shown_seconds

    if not in_review():
        review_started = None
        _review_shown_seconds = None
        return

    if review_started is None or menu_open:
        # The countdown waits while the settings menu is open.
        review_started = time.monotonic()

    left = review_seconds_left()
    if left <= 0:
        print("Review timed out: keeping strip.")
        review_started = None
        _review_shown_seconds = None
        save_and_advance()
    elif left != _review_shown_seconds:
        _review_shown_seconds = left
        update_lcd()

try:
    while True:
        if lcd is not None:
            tap = next_tap(pygame.event.get())
            # A tap on a sleeping screen only wakes it.
            if tap is not None and not wake_screen():
                handle_tap(tap)

        while not action_queue.empty():
            action, payload = action_queue.get()

            if action in ("short", "toggle_mode"):
                # The press that wakes the screen only wakes it; one in the menu closes it.
                if wake_screen() or menu_open:
                    close_menu()
                    pending_short_time = None
                    short_press_count = 0
                    continue

            if action == "print_done":
                flash_message("PRINT SENT" if payload else "PRINT FAILED", seconds=1.0)
            elif action == "shutdown":
                pending_short_time = None
                short_press_count = 0
                shutdown_pi()
            elif action == "toggle_mode":
                pending_short_time = None
                short_press_count = 0
                toggle_mode()
            elif action == "short":
                short_press_count += 1
                pending_short_time = payload
            else:
                print(f"Unknown action: {action}")

        if (
            pending_short_time is not None
            and time.monotonic() - pending_short_time > DOUBLE_CLICK_SECONDS
        ):
            count = short_press_count
            pending_short_time = None
            short_press_count = 0
            handle_short_presses(count)

        if poll_battery() and not should_show_live_preview():
            update_lcd()

        tick_review()

        if (
            settings["sleep"] is not None
            and not screen_asleep
            and not _print_busy.is_set()
            and not in_review()
            and time.monotonic() - last_activity > settings["sleep"]
        ):
            sleep_screen()

        if menu_open:
            update_menu()
        else:
            update_live_slot_preview()
        watchdog_ping()
        time.sleep(0.03)

except KeyboardInterrupt:
    print("Exiting! Bye!")

finally:
    restore_backlight_if_dark()
    try:
        stop_camera()
    except Exception as e:
        print(f"Camera stop failed: {e}")
    pygame.quit()
