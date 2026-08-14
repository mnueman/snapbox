from pathlib import Path
from datetime import datetime
from queue import Queue
import json
import os
import time
import subprocess
import tempfile

from gpiozero import Button
from PIL import Image, ImageDraw, ImageFont
from picamera2 import Picamera2
import numpy as np
import pygame


BUTTON_GPIO = 16

LONG_PRESS_SECONDS = 1.0
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

CAPTURE_W, CAPTURE_H = 1280, 720
PREVIEW_W, PREVIEW_H = 640, 360
LIVE_PREVIEW_FPS = 8
SLOT_BLEED = 5

USE_LCD = True

PORTRAIT_UI_W = 480
PORTRAIT_UI_H = 720
PORTRAIT_TO_LCD_ROTATION = -90

PRINTER_NAME = None
PRINT_OPTIONS = [
    "-o", "PageSize=Postcard.Borderless",
]
PRINT_SCALE = 96


picam2 = Picamera2()
camera_config = picam2.create_still_configuration(
    main={"size": (CAPTURE_W, CAPTURE_H)},
    lores={"size": (PREVIEW_W, PREVIEW_H), "format": "YUV420"},
)
picam2.configure(camera_config)
picam2.start()
time.sleep(1.5)


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


frames = sorted(FRAME_DIR.glob("*.png"))
current_frame_index = 0

live_photos = [None, None, None, None]
current_slot = 0

mode = "creation"

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


def resize_live_photos(new_capacity):
    global live_photos, current_slot

    new_photos = [None] * new_capacity
    for i in range(min(len(live_photos), new_capacity)):
        new_photos[i] = live_photos[i]
    live_photos = new_photos
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


def portrait_strip_layout(area_box=None):
    if area_box is None:
        area_box = (0, 0, PORTRAIT_UI_W, PORTRAIT_UI_H)
    ax, ay, aw, ah = area_box
    scale = min(aw / STRIP_W, ah / STRIP_H)
    sw = max(1, int(STRIP_W * scale))
    sh = max(1, int(STRIP_H * scale))
    px = ax + (aw - sw) // 2
    py = ay + (ah - sh) // 2
    return px, py, sw, sh


def paste_strip_into_area(canvas, strip_img, area_box):
    x, y, w, h = area_box

    img = strip_img.convert("RGB")
    img.thumbnail((w, h), Image.LANCZOS)

    paste_x = x + (w - img.width) // 2
    paste_y = y + (h - img.height) // 2

    canvas.paste(img, (paste_x, paste_y))


def compose_portrait_display():
    canvas = Image.new("RGB", (PORTRAIT_UI_W, PORTRAIT_UI_H), "black")
    full_area = (0, 0, PORTRAIT_UI_W, PORTRAIT_UI_H)

    strip = None
    if mode == "browse" and browse_strips:
        browse_path = browse_strips[browse_index]
        try:
            strip = Image.open(browse_path).convert("RGB")
        except Exception as e:
            print(f"Could not open saved strip: {e}")
            strip = None

    if strip is None:
        strip = compose_single_strip(live_photos)

    paste_strip_into_area(canvas, strip, full_area)
    return canvas


def should_show_live_preview():
    return (
        lcd is not None
        and mode == "creation"
        and not strip_is_full()
        and 0 <= current_slot < current_capacity()
    )


def _live_preview_cache_key():
    return (
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

    photos_strip = compose_single_strip(live_photos, include_frame=False)
    px, py, sw, sh = portrait_strip_layout()
    photos_scaled = photos_strip.convert("RGB").resize((sw, sh), Image.BILINEAR)

    photos_canvas = Image.new("RGB", (PORTRAIT_UI_W, PORTRAIT_UI_H), "black")
    photos_canvas.paste(photos_scaled, (px, py))

    frame = load_current_frame()
    frame_canvas = None
    if frame is not None:
        frame_scaled = frame.resize((sw, sh), Image.BILINEAR)
        frame_canvas = Image.new("RGBA", (PORTRAIT_UI_W, PORTRAIT_UI_H), (0, 0, 0, 0))
        frame_canvas.paste(frame_scaled, (px, py), frame_scaled)

    x, y, w, h = slots[current_slot]
    left = max(0, x - SLOT_BLEED)
    top = max(0, y - SLOT_BLEED)
    right = min(STRIP_W, x + w + SLOT_BLEED)
    bottom = min(STRIP_H, y + h + SLOT_BLEED)
    slot_box = (
        px + int(left * sw / STRIP_W),
        py + int(top * sh / STRIP_H),
        max(1, int((right - left) * sw / STRIP_W)),
        max(1, int((bottom - top) * sh / STRIP_H)),
    )

    _live_preview_key = key
    _live_preview_photos = photos_canvas
    _live_preview_frame = frame_canvas
    _live_preview_slot_box = slot_box
    return True


def capture_preview_image():
    # Lores is YUV420 on Pi; fall back to the main still stream.
    try:
        yuv = picam2.capture_array("lores")
        rgb = picam2.helpers.yuv420_to_rgb(yuv)
        return Image.fromarray(rgb, "RGB")
    except Exception:
        pass

    arr = picam2.capture_array("main")
    if arr is None or arr.ndim != 3 or arr.shape[2] < 3:
        return None
    return Image.fromarray(np.ascontiguousarray(arr[:, :, :3]), "RGB")


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
    if lcd is None:
        return

    try:
        pygame.event.pump()

        screen_w, screen_h = lcd.get_size()

        if img is None:
            img = compose_portrait_display()

        if overlay_text is not None:
            img = img.copy()
            _draw_centered_banner(img, overlay_text)

        img = img.rotate(PORTRAIT_TO_LCD_ROTATION, expand=True)

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

    except pygame.error as e:
        print(f"LCD update failed: {e}")


def flash_message(text, seconds=1.0):
    if lcd is None:
        return

    update_lcd(overlay_text=text)
    time.sleep(seconds)
    update_lcd()


def save_preview():
    _invalidate_live_preview()
    preview = compose_portrait_display()

    path = BASE / "current_preview.jpg"
    preview.save(path, quality=90)

    print(f"Preview updated: {path}")

    update_lcd(preview)


def save_finished_strip():
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    jpg_archive_path = ARCHIVE_DIR / f"strip_{timestamp}.jpg"

    strip = compose_single_strip(live_photos)
    strip.convert("RGB").save(jpg_archive_path, quality=95)

    print("")
    print("FINISHED STRIP SAVED")
    print(f"JPG archive: {jpg_archive_path}")
    print("")

    return jpg_archive_path


def clear_live_strip():
    global live_photos, current_slot

    capacity = current_capacity()
    live_photos = [None] * capacity
    current_slot = 0
    _clear_photo_cache()


def start_fresh_strip():
    clear_live_strip()
    print("Started a fresh strip.")
    save_preview()


def save_and_advance():
    save_finished_strip()
    start_fresh_strip()
    flash_message("STRIP SAVED", seconds=0.8)


def take_next_photo():
    global current_slot

    capacity = current_capacity()
    if current_slot >= capacity:
        print("Strip is already full; not taking another photo.")
        return

    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    capture_path = CAPTURE_DIR / f"capture_{timestamp}.jpg"

    print(f"Capturing photo {current_slot + 1}/{capacity}...")
    picam2.capture_file(str(capture_path))

    img = Image.open(capture_path).convert("RGB")
    if img.width > CAPTURE_W or img.height > CAPTURE_H:
        img.thumbnail((CAPTURE_W, CAPTURE_H), Image.BILINEAR)
    live_photos[current_slot] = img

    current_slot += 1

    save_preview()

    if current_slot >= capacity:
        print("Strip full. Press again to save and start a new strip.")
        flash_message("STRIP FULL", seconds=0.6)


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


def browse_next():
    global browse_index

    if not _refresh_browse_list():
        return

    browse_index = (browse_index + 1) % len(browse_strips)

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


def print_current_browsed_item():
    if not browse_strips:
        return

    path = browse_strips[browse_index]
    strip = load_strip_image(path)
    if strip is None:
        return

    fd, tmp = tempfile.mkstemp(prefix="print_", suffix=".jpg")
    os.close(fd)
    tmp_path = Path(tmp)
    try:
        make_duplicate_print(strip).save(tmp_path, quality=95)
        print(f"Built duplicate print: {tmp_path}")
        if send_to_printer(tmp_path):
            flash_message("PRINT SENT", seconds=1.0)
        else:
            flash_message("PRINT FAILED", seconds=1.0)
    finally:
        try:
            tmp_path.unlink()
        except OSError:
            pass

    save_preview()


def shutdown_pi():
    print("Very-long press: shutting down Pi safely...")

    if lcd is not None:
        try:
            screen_w, screen_h = lcd.get_size()

            img = Image.new("RGB", (PORTRAIT_UI_W, PORTRAIT_UI_H), "black")
            _draw_centered_banner(img, "Shutting down...")
            img = img.rotate(PORTRAIT_TO_LCD_ROTATION, expand=True)

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


def handle_short_presses(count):
    if mode == "browse":
        if count == 1:
            browse_next()
        elif count == 3:
            print_current_browsed_item()
        else:
            print(f"Browse mode: ignoring {count} short presses")
        return

    if count == 1:
        if strip_is_full():
            save_and_advance()
        else:
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

save_preview()

pending_short_time = None
short_press_count = 0

try:
    while True:
        if lcd is not None:
            pygame.event.pump()

        while not action_queue.empty():
            action, ts = action_queue.get()

            if action == "shutdown":
                pending_short_time = None
                short_press_count = 0
                shutdown_pi()
            elif action == "toggle_mode":
                pending_short_time = None
                short_press_count = 0
                toggle_mode()
            elif action == "short":
                short_press_count += 1
                pending_short_time = ts
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

        update_live_slot_preview()
        time.sleep(0.03)

except KeyboardInterrupt:
    print("Exiting! Bye!")

finally:
    picam2.stop()
    pygame.quit()
