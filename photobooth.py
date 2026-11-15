from pathlib import Path
from datetime import datetime
from queue import Queue
import base64
import http.server
import io
import json
import math
import os
import random
import re
import shutil
import socket
import time
import subprocess
import sys
import tempfile
import threading
import traceback
import urllib.parse

from gpiozero import Button, InputDevice
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont, ImageOps
from picamera2 import Picamera2
from libcamera import controls, Transform
import numpy as np
import pygame

try:
    import looks  # the MODERN and CLASSIC CAMERA looks (looks.py); without it, the original look
except Exception as e:  # a broken or missing file must not stop the booth
    print(f"Looks unavailable ({e}); using the original look.")
    looks = None


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

# Raw captures only live until their strip is saved. Any here at startup belong to a strip that
# was interrupted (crash, power cut) and can't be resumed, so clear them before they pile up.
for _leftover in CAPTURE_DIR.glob("capture_*.jpg"):
    try:
        _leftover.unlink()
        print(f"Removed leftover capture {_leftover.name}")
    except OSError:
        pass

STRIP_W, STRIP_H = 1200, 3600
PRINT_W, PRINT_H = STRIP_W * 2, STRIP_H
# BIG SHEET designs fill the whole 4x6 print by themselves (300 dpi, the printer's own
# resolution): landscape 6x4 sheets in frames/sheets/, portrait 4x6 ones in frames/portrait/.
SHEET_W, SHEET_H = 1800, 1200
PSHEET_W, PSHEET_H = 1200, 1800
# Designs come from three places: frames/ (every booth), gifts/<person>/ (made for this booth's
# person, in a folder per collection; see system/gifts.py) and ~/my-designs (the owner's own;
# updates never touch it). Every design folder is laid out the same: strips at the top, landscape
# sheets in sheets/, portrait ones in portrait/. Gifts and the owner's own can be in subfolders.
GIFTS_DIR = BASE / "gifts"
MY_DESIGNS_DIR = Path.home() / "my-designs"
DESIGN_SUBFOLDERS = {"strip": None, "sheet": "sheets", "psheet": "portrait"}
DESIGN_SIZES = {"strip": (STRIP_W, STRIP_H), "sheet": (SHEET_W, SHEET_H), "psheet": (PSHEET_W, PSHEET_H)}
MAX_DESIGN_PHOTOS = 8
DESIGN_RESCAN_SECONDS = 15  # while idle, look for designs added or gone (no restart needed)
LAYOUTS = ["strip", "sheet", "psheet"]  # the order the main screen's layout button goes through
LAYOUT_NAMES = {"strip": "PHOTO STRIPS (2x6)", "sheet": "BIG SHEET: LANDSCAPE (6x4)",
                "psheet": "BIG SHEET: PORTRAIT (4x6)"}

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
# Used to turn the bezel margin (BOOTH tab, in mm) into pixels.
SCREEN_DIAGONAL_INCHES = 2.8
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
# How much of a borderless 4x6 the SELPHY loses on each side, in mm of the picture as sent (the
# printer enlarges it a little and it isn't centred), measured at the middle of each edge. From
# 3 ruler prints on booth-1's CP1500, 5 photos (system/print_calibration.py,
# system/measure_calibration.py), corrected by the measurement's own self-check. Top and bottom are the perforations.
PRINT_TRIM_MM = {"top": 4.70, "bottom": 5.88, "left": 2.21, "right": 2.94}
# The picture also sits very slightly turned on the paper (about 0.09 degrees): how much each
# edge's cut-off changes per mm along it (top and bottom: left to right; left and right: top to
# bottom).
PRINT_SLANT = {"top": 0.00159, "bottom": -0.00066, "left": -0.00154, "right": 0.00152}
# Prints are fitted so the design's edges land on the perforations and paper edges, reaching
# this far past them so a print that lands slightly differently shows design, not a gap.
# Chosen with system/print_fit_sim.py.
PRINT_BLEED_MM = 0.5


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
        ("normal", "NORMAL"), ("vivid", "VIVID"), ("warm", "WARM"), ("cool", "COOL"),
        ("soft", "SOFT & DREAMY"), ("bw", "BLACK & WHITE"), ("noir", "NOIR (HIGH CONTRAST B&W)"),
        ("sepia", "SEPIA"), ("film", "FILM (WARM)"), ("film_bw", "FILM (B&W)"),
        ("portrait", "FILM: PORTRAIT"), ("golden", "FILM: GOLDEN"), ("green", "FILM: COOL GREEN"),
        ("instant", "INSTANT PHOTO"), ("faded70s", "70s FADED"), ("cross", "CROSS-PROCESSED"),
    ], "normal"),
    ("motion", "MOVEMENT", [
        (10000, "SHARPEST (DARKER)"), (20000, "BALANCED"), (33333, "BRIGHTER (MORE BLUR)"),
    ], MAX_EXPOSURE_US),
    ("focus", "FOCUS", [
        ("auto", "AUTO"), ("near", "FIXED: CLOSE UP"), ("far", "FIXED: FARTHER AWAY"),
    ], "auto"),
    ("light", "LIGHTING", [
        ("auto", "AUTO"), ("tungsten", "WARM LIGHT BULBS"), ("indoor", "INDOOR"),
        ("fluorescent", "OFFICE LIGHTS"), ("daylight", "SUNNY"), ("cloudy", "CLOUDY / SHADE"),
    ], "auto"),
    ("zoom", "ZOOM", [
        (1.0, "WIDE"), (1.2, "A BIT CLOSER"), (1.4, "CLOSER"), (1.7, "CLOSEST"),
    ], 1.0),
    ("mirror", "MIRROR PREVIEW", [
        (True, "ON (LIKE A MIRROR)"), (False, "OFF"),
    ], True),
]
# Vintage add-ons, drawn on every photo on top of any frame; they all stack. Each style always
# looks the same (same place, same strength) so you know what you'll get. Positions and sizes
# are fractions of the photo (sizes of its shorter side); colours are (r, g, b); k = strength.
_ORANGE, _RED, _GOLD, _YELLOW, _PINK = (255, 96, 20), (255, 38, 26), (255, 168, 40), (255, 214, 120), (255, 70, 120)
LEAK_STYLES = [
    # (name, edge band (side, width, k) or None, [(x, y, size x, size y, colour, k)])
    ("SOFT LEFT GLOW", ("left", 0.05, 0.45), [(-0.02, 0.5, 0.4, 0.7, _ORANGE, 0.6)]),
    ("WARM RIGHT EDGE", ("right", 0.08, 0.8),
     [(1.0, 0.3, 0.35, 0.5, _ORANGE, 0.9), (1.02, 0.78, 0.3, 0.4, _RED, 0.8)]),
    ("GOLDEN TOP", ("top", 0.06, 0.6), [(0.3, -0.04, 0.5, 0.3, _GOLD, 0.9), (0.78, 0.0, 0.4, 0.25, _YELLOW, 0.7)]),
    ("RED CORNER", None, [(0.0, 0.0, 0.4, 0.4, _RED, 1.0), (0.14, 0.06, 0.22, 0.22, _ORANGE, 0.8)]),
    ("SUNSET BOTTOM", ("bottom", 0.07, 0.7),
     [(0.25, 1.03, 0.5, 0.3, _ORANGE, 0.9), (0.72, 1.05, 0.45, 0.3, _PINK, 0.7)]),
    ("BOTH EDGES", None, [(-0.03, 0.4, 0.3, 0.6, _ORANGE, 0.8), (1.03, 0.62, 0.3, 0.6, _RED, 0.8)]),
    ("BURNT BAND", ("left", 0.15, 1.0), [(0.05, 0.3, 0.3, 0.5, _RED, 0.9), (0.04, 0.8, 0.25, 0.4, _GOLD, 0.8)]),
    ("PEACH WASH", None, [(0.55, 0.5, 0.9, 0.9, (255, 150, 90), 0.35), (1.0, 0.2, 0.35, 0.4, _ORANGE, 0.6)]),
    ("FIERY CORNERS", None, [(0, 0, 0.3, 0.3, _RED, 0.9), (1, 0, 0.3, 0.3, _ORANGE, 0.9),
                             (0, 1, 0.3, 0.3, _GOLD, 0.8), (1, 1, 0.3, 0.3, _RED, 0.9)]),
    ("FULL BURN", ("right", 0.2, 1.0), [(0.95, 0.5, 0.55, 0.9, _RED, 1.0), (0.82, 0.25, 0.35, 0.4, _ORANGE, 1.0),
                                        (0.8, 0.8, 0.35, 0.4, _YELLOW, 0.9)]),
]
SPOT_STYLES = [
    # (name, [("orb", x, y, radius, colour, k) or ("ring", x, y, radius, colour, k)])
    ("SMALL RED ORB", [("orb", 0.72, 0.3, 0.09, _RED, 0.9)]),
    ("TWO RED ORBS", [("orb", 0.25, 0.35, 0.1, _RED, 0.85), ("orb", 0.7, 0.66, 0.08, _RED, 0.8)]),
    ("BIG SOFT RED", [("orb", 0.6, 0.45, 0.24, _RED, 0.65)]),
    ("ORANGE FLARE", [("orb", 0.8, 0.2, 0.13, _ORANGE, 1.0), ("orb", 0.64, 0.4, 0.06, _ORANGE, 0.7),
                      ("orb", 0.5, 0.58, 0.035, _ORANGE, 0.55)]),
    ("RED RING", [("ring", 0.5, 0.5, 0.3, _RED, 0.9)]),
    ("ORB IN A RING", [("orb", 0.35, 0.42, 0.1, _RED, 0.9), ("ring", 0.35, 0.42, 0.21, _RED, 0.8)]),
    ("CORNER HOTSPOT", [("orb", 0.96, 0.06, 0.28, (255, 60, 30), 1.0)]),
    ("FLARE CHAIN", [("orb", 0.18, 0.2, 0.1, _RED, 0.9), ("orb", 0.36, 0.38, 0.065, _ORANGE, 0.75),
                     ("orb", 0.54, 0.56, 0.045, _RED, 0.65), ("orb", 0.72, 0.74, 0.03, _ORANGE, 0.55)]),
    ("PINK HAZE", [("orb", 0.3, 0.3, 0.18, _PINK, 0.6), ("orb", 0.72, 0.6, 0.2, _PINK, 0.5),
                   ("orb", 0.5, 0.85, 0.12, _RED, 0.5)]),
    ("STROBE BURST", [("orb", 0.62, 0.38, 0.16, (255, 60, 30), 1.0), ("ring", 0.62, 0.38, 0.34, _RED, 0.85),
                      ("orb", 0.2, 0.75, 0.07, _RED, 0.8), ("orb", 0.85, 0.85, 0.05, _ORANGE, 0.7)]),
]
LINE_STYLES = [
    # (name, {dust: specks, hairs, scratches: thin white lines, streaks: [(x, width, k)]})
    ("LIGHT DUST", {"dust": 25}),
    ("HEAVY DUST", {"dust": 90, "big": True}),
    ("ONE STREAK", {"streaks": [(0.3, 0.008, 0.9)]}),
    ("TWO STREAKS", {"streaks": [(0.18, 0.006, 0.8), (0.78, 0.01, 0.9)]}),
    ("FINE SCRATCHES", {"scratches": 6}),
    ("HAIR & DUST", {"hairs": 6, "dust": 40}),
    ("STREAK & DUST", {"streaks": [(0.65, 0.009, 0.85)], "dust": 40, "hairs": 2}),
    ("EDGE STREAKS", {"streaks": [(0.03, 0.02, 0.9), (0.97, 0.02, 0.9)]}),
    ("OLD MOVIE", {"scratches": 8, "dust": 60, "hairs": 3, "streaks": [(0.44, 0.004, 0.5)]}),
    ("WORN OUT", {"scratches": 10, "dust": 120, "big": True, "hairs": 8,
                  "streaks": [(0.12, 0.012, 1.0), (0.58, 0.006, 0.7), (0.9, 0.015, 0.9)]}),
]


def _style_choices(styles):
    return [(0, "OFF")] + [(i + 1, f"{i + 1}. {name}") for i, (name, *_) in enumerate(styles)]


EFFECT_SETTINGS = [
    # "custom": a date typed in on the number pad (settings "stamp_date"), for when the clock is
    # wrong (no WiFi to set it) or to stamp a special day.
    ("stamp", "DATE STAMP", [(False, "OFF"), (True, "ON: TODAY"), ("custom", "ON: MY DATE")], False),
    # A new pick for every photo, instead of the three settings below.
    ("random", "RANDOM EFFECT EACH PHOTO", [(0, "OFF"), (1, "ON")], 0),
    ("leaks", "LIGHT LEAKS (WARM GLOW)", _style_choices(LEAK_STYLES), 0),
    ("spots", "RED LIGHT SPOTS", _style_choices(SPOT_STYLES), 0),
    ("lines", "LIGHT STREAKS & DUST", _style_choices(LINE_STYLES), 0),
]
# Short names for the setting buttons along the full-screen preview.
SETTING_SHORT = {"brightness": "BRIGHT", "colour": "COLOUR", "motion": "MOVE", "focus": "FOCUS",
                 "light": "LIGHT", "zoom": "ZOOM", "mirror": "MIRROR", "stamp": "DATE",
                 "random": "RANDOM", "leaks": "LEAKS", "spots": "SPOTS", "lines": "STREAKS"}
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
    # A 3D-printed bezel can cover the left edge of the screen: shift everything right.
    ("edge", "SHIFT SCREEN RIGHT (BEZEL)", [
        (0, "NO SHIFT"), (1, "1 MM"), (2, "2 MM"), (3, "3 MM"), (4, "4 MM"), (5, "5 MM"),
        (6, "6 MM"),
    ], 2),
    # The whole look of the screens (looks.py). ORIGINAL is the one MENU COLOURS applies to.
    ("look", "LOOK", [
        ("original", "ORIGINAL"), ("modern", "MODERN"), ("classic", "CLASSIC CAMERA"),
    ], "original"),
    # Colours of the menus and buttons (THEMES, further down).
    ("theme", "MENU COLOURS", [
        ("classic", "CLASSIC"), ("sunshine", "SUNSHINE"), ("bubblegum", "BUBBLEGUM"),
        ("ocean", "OCEAN"), ("mint", "MINT"), ("party", "PARTY"), ("midnight", "MIDNIGHT"),
    ], "classic"),
    # Saves the battery or power bank (and works on mains too).
    ("auto_off", "AUTO SHUT DOWN WHEN IDLE", [
        (None, "OFF"), (900, "AFTER 15 MIN"), (1800, "AFTER 30 MIN"), (3600, "AFTER 1 HOUR"),
        (7200, "AFTER 2 HOURS"), (14400, "AFTER 4 HOURS"),
    ], None),
]
SETTING_DEFS = {key: (label, choices, default)
                for key, label, choices, default in CAMERA_SETTINGS + EFFECT_SETTINGS + BOOTH_SETTINGS}


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
    values["stamp_date"] = None  # "YYYY-MM-DD", for the date stamp's "custom" setting
    if isinstance(saved, dict) and isinstance(saved.get("stamp_date"), str):
        try:
            datetime.strptime(saved["stamp_date"], "%Y-%m-%d")
            values["stamp_date"] = saved["stamp_date"]
        except ValueError:
            pass
    if values["stamp"] == "custom" and values["stamp_date"] is None:
        values["stamp"] = True
    return values


settings = _load_settings()


# Colours of the menus, main screen and review screen, by theme (BOOTH tab > MENU COLOURS).
# The accent is always light enough for black text on it.
#   bg: behind everything      row: buttons and setting rows   text / dim: writing on bg and row
#   accent: the chosen thing   done / danger: green and red buttons
#   off: a button that can't be used   busy: a button that's working   key: plain keys
#   field: where typing shows  inset: a quiet box   good / bad: status writing on bg
#   disc: the round buttons on the main screen (white icons on them)
#   main: behind the strip on the main and review screens
THEMES = {
    "classic": dict(bg=(22, 22, 26), row=(46, 46, 54), text=(255, 255, 255), dim=(150, 150, 160),
                    accent=(255, 190, 40), done=(40, 150, 70), danger=(190, 45, 45),
                    off=(30, 30, 36), busy=(80, 80, 88), key=(70, 70, 80), field=(0, 0, 0),
                    inset=(34, 34, 40), good=(120, 220, 140), bad=(255, 110, 110),
                    disc=(0, 0, 0), main=(0, 0, 0)),
    "sunshine": dict(bg=(255, 236, 170), row=(255, 252, 240), text=(74, 44, 10), dim=(150, 112, 60),
                     accent=(255, 150, 20), done=(70, 200, 110), danger=(245, 96, 80),
                     off=(246, 222, 150), busy=(226, 204, 150), key=(255, 214, 110),
                     field=(255, 255, 255), inset=(255, 226, 140), good=(20, 130, 60),
                     bad=(200, 40, 40), disc=(230, 110, 0), main=(255, 224, 130)),
    "bubblegum": dict(bg=(255, 200, 226), row=(255, 244, 250), text=(96, 16, 64), dim=(170, 90, 130),
                      accent=(255, 96, 170), done=(60, 200, 150), danger=(240, 70, 100),
                      off=(250, 184, 212), busy=(230, 176, 204), key=(255, 160, 205),
                      field=(255, 255, 255), inset=(255, 178, 214), good=(10, 130, 90),
                      bad=(200, 30, 70), disc=(226, 50, 140), main=(255, 178, 214)),
    "ocean": dict(bg=(170, 226, 250), row=(240, 250, 255), text=(8, 48, 92), dim=(70, 120, 160),
                  accent=(40, 190, 255), done=(60, 205, 150), danger=(245, 100, 95),
                  off=(150, 210, 238), busy=(150, 196, 220), key=(120, 204, 245),
                  field=(255, 255, 255), inset=(140, 212, 245), good=(0, 120, 80),
                  bad=(200, 40, 50), disc=(0, 110, 200), main=(130, 208, 246)),
    "mint": dict(bg=(186, 242, 214), row=(242, 255, 248), text=(10, 66, 48), dim=(70, 130, 105),
                 accent=(60, 220, 160), done=(50, 190, 110), danger=(245, 105, 95),
                 off=(166, 228, 198), busy=(160, 212, 188), key=(130, 226, 186),
                 field=(255, 255, 255), inset=(156, 232, 196), good=(0, 120, 70),
                 bad=(200, 40, 50), disc=(0, 150, 100), main=(150, 230, 190)),
    "party": dict(bg=(84, 30, 170), row=(128, 66, 220), text=(255, 255, 255), dim=(216, 190, 255),
                  accent=(255, 224, 40), done=(30, 200, 140), danger=(255, 70, 120),
                  off=(70, 24, 140), busy=(140, 110, 200), key=(160, 90, 240),
                  field=(40, 10, 90), inset=(104, 46, 196), good=(120, 255, 190),
                  bad=(255, 150, 170), disc=(255, 60, 160), main=(100, 40, 196)),
    "midnight": dict(bg=(10, 16, 34), row=(28, 40, 72), text=(255, 255, 255), dim=(140, 155, 190),
                     accent=(90, 200, 255), done=(30, 140, 120), danger=(200, 60, 80),
                     off=(16, 24, 48), busy=(70, 82, 110), key=(52, 66, 104), field=(0, 0, 0),
                     inset=(20, 30, 58), good=(120, 220, 170), bad=(255, 120, 130),
                     disc=(28, 40, 72), main=(10, 16, 34)),
}


def look():
    """The look of the main screen: "original", "modern" or "classic". The new looks are laid out
    for a screen on its side; upright, the main screen stays original (menus keep the look's
    colours and type)."""
    lk = settings.get("look", "original")
    if looks is None or lk not in looks.LOOKS or settings["rotation"] not in (0, 180):
        return "original"
    return lk


def apply_theme():
    global MENU_BG, MENU_ROW, MENU_TEXT, MENU_DIM, MENU_ACCENT, MENU_DONE, MENU_DANGER, MENU_OFF
    global MENU_BUSY, MENU_KEY, MENU_FIELD, MENU_INSET, MENU_GOOD, MENU_BAD, MENU_DISC, MAIN_BG
    lk = settings.get("look", "original")
    if looks is not None and lk in looks.THEMES:
        t = looks.THEMES[lk]
    else:
        t = THEMES.get(settings["theme"], THEMES["classic"])
    MENU_BG, MENU_ROW, MENU_TEXT, MENU_DIM = t["bg"], t["row"], t["text"], t["dim"]
    MENU_ACCENT, MENU_DONE, MENU_DANGER = t["accent"], t["done"], t["danger"]
    MENU_OFF, MENU_BUSY, MENU_KEY, MENU_FIELD = t["off"], t["busy"], t["key"], t["field"]
    MENU_INSET, MENU_GOOD, MENU_BAD, MENU_DISC, MAIN_BG = (t["inset"], t["good"], t["bad"],
                                                            t["disc"], t["main"])
    if look() != "original":
        MAIN_BG = looks.STAGE_BG[look()]  # behind the strip, inside the look's frame


apply_theme()
screen_rotation = settings["rotation"]


def to_panel_rotation(rotation, panel_w, panel_h):
    """The SCREEN setting assumes a landscape panel (800x480). A panel that is natively
    portrait (e.g. 480x640) needs an extra quarter turn so LANDSCAPE really is landscape."""
    if panel_h > panel_w:
        return {0: -90, 180: 90, -90: 180, 90: 0}[rotation]
    return rotation


SPLASH_PICTURE = Path("/usr/share/plymouth/themes/snapbox/bg.png")  # system/setup-splash.sh


def end_boot_splash():
    """The boot splash (system/setup-splash.sh) stays up until the app is about to draw; this ends
    it, so the screen never sits black in between. Nothing to do when there's no splash."""
    if not Path("/run/plymouth/pid").exists():
        return
    try:
        subprocess.run(["systemctl", "start", "snapbox-splash-quit.service"], capture_output=True,
                       timeout=8)
    except Exception as e:
        print(f"Could not end the boot splash: {e}")


def _fatal_screen(message, seconds=15):
    """Shows a problem on the booth screen before the app's UI exists, then exits so the
    service tries again (the problem may get fixed, e.g. a camera cable pushed back in)."""
    print(message.replace("\n", " "), flush=True)
    try:
        end_boot_splash()
        pygame.init()
        screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        pygame.mouse.set_visible(False)
        sw, sh = screen.get_size()
        rotation = settings["rotation"]
        w, h = (max(sw, sh), min(sw, sh)) if rotation in (0, 180) else (min(sw, sh), max(sw, sh))
        img = Image.new("RGB", (w, h), "black")
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24)
        except OSError:
            font = ImageFont.load_default()
        ImageDraw.Draw(img).multiline_text((w / 2, h / 2), message, font=font, fill="white",
                                           anchor="mm", align="center", spacing=10)
        img = img.rotate(to_panel_rotation(rotation, sw, sh), expand=True).resize((sw, sh))
        screen.blit(pygame.image.fromstring(img.tobytes(), img.size, "RGB"), (0, 0))
        pygame.display.flip()
        time.sleep(seconds)
    except Exception as e:
        print(f"Could not show the problem on screen: {e}")
    os._exit(1)


try:
    picam2 = Picamera2()
except Exception as e:
    print(f"Camera not found: {e}")
    _fatal_screen("CAMERA NOT FOUND\n\nTurn the booth off and check\nthe camera cable is pushed in.\n\nTrying again...")


# Each LIGHTING preset locks the white balance to one colour temperature (kelvin). libcamera's
# own AWB modes only narrow the range auto white balance searches, and most of them overlap
# AUTO, so in many rooms picking one changed nothing.
LIGHT_KELVIN = {"tungsten": 2900, "indoor": 3600, "fluorescent": 4300, "daylight": 5600,
                "cloudy": 7000}
AWB_MODES = {
    "tungsten": controls.AwbModeEnum.Tungsten,
    "fluorescent": controls.AwbModeEnum.Fluorescent,
    "indoor": controls.AwbModeEnum.Indoor,
    "daylight": controls.AwbModeEnum.Daylight,
    "cloudy": controls.AwbModeEnum.Cloudy,
}


def _load_ct_curve():
    """The sensor's colour temperature curve [(kelvin, r, b)] from its libcamera tuning file:
    r and b are the red/green and blue/green ratios of grey at that temperature."""
    model = picam2.camera_properties.get("Model", "")
    for platform in ("pisp", "vc4"):
        path = Path(f"/usr/share/libcamera/ipa/rpi/{platform}/{model}.json")
        try:
            tuning = json.loads(path.read_text())
        except (OSError, ValueError):
            continue
        for algo in tuning.get("algorithms", []):
            curve = algo.get("rpi.awb", {}).get("ct_curve")
            if curve and len(curve) >= 6:
                return [tuple(curve[i:i + 3]) for i in range(0, len(curve) - 2, 3)]
    print(f"No colour temperature curve for camera {model!r}; LIGHTING uses AWB modes.")
    return None


def colour_gains(kelvin):
    """(red gain, blue gain) that make grey come out grey under light of this temperature."""
    curve = _ct_curve
    if kelvin <= curve[0][0]:
        _, r, b = curve[0]
    elif kelvin >= curve[-1][0]:
        _, r, b = curve[-1]
    else:
        for (k0, r0, b0), (k1, r1, b1) in zip(curve, curve[1:]):
            if k0 <= kelvin <= k1:
                t = (kelvin - k0) / (k1 - k0)
                r, b = r0 + (r1 - r0) * t, b0 + (b1 - b0) * t
                break
    return 1.0 / r, 1.0 / b


_ct_curve = _load_ct_curve()
FOCUS_DIOPTRES = {"near": 1.5, "far": 0.3}  # 1 / distance in metres
# The camera is mounted upside down in the box, so the sensor turns every frame 180 degrees
# (preview and photos alike).
CAMERA_TRANSFORM = Transform(hflip=True, vflip=True)

# Colour looks. "sat" is the camera's saturation (so the live preview matches); "curve" is a tone
# curve applied after capture; plus optional vignette and grain (film looks).
#   contrast: 0 = straight line .. 1 = full S-curve    fade/roll: output black and white levels
#   gamma/lift/gain (r, g, b): per-channel shape, shadow tint and highlight level
COLOUR_LOOKS = {
    "normal": {"sat": 1.0},
    "vivid": {"sat": 1.6, "curve": {"contrast": 0.25}},
    "warm": {"sat": 1.1, "curve": {"gamma": (0.94, 0.99, 1.08), "gain": (1.0, 0.99, 0.93)}},
    "cool": {"sat": 1.0, "curve": {"gamma": (1.07, 1.0, 0.94), "lift": (0.0, 0.01, 0.03)}},
    "soft": {"sat": 0.85, "curve": {"contrast": -0.25, "fade": 0.06, "roll": 0.97,
                                    "gamma": (0.95, 0.97, 0.98)}, "vignette": 0.12},
    "bw": {"sat": 0.0},
    "noir": {"sat": 0.0, "curve": {"contrast": 1.0, "gamma": (1.15, 1.15, 1.15)},
             "grain": 9.0, "vignette": 0.45},
    "sepia": {"sat": 0.0, "curve": {"contrast": 0.3, "fade": 0.04, "roll": 0.96,
                                    "gamma": (0.92, 1.0, 1.2), "gain": (1.0, 0.92, 0.74),
                                    "lift": (0.04, 0.02, 0.0)}, "grain": 6.0, "vignette": 0.3},
    "film": {"sat": 0.85, "curve": {"contrast": 0.35, "fade": 0.05, "roll": 0.95,
                                    "gamma": (0.93, 0.98, 1.06), "lift": (0.0, 0.0, 0.04),
                                    "gain": (1.0, 1.0, 0.96)}, "grain": 5.0, "vignette": 0.28},
    "film_bw": {"sat": 0.0, "curve": {"contrast": 0.45, "fade": 0.05, "roll": 0.95},
                "grain": 8.0, "vignette": 0.32},
    "portrait": {"sat": 0.9, "curve": {"contrast": 0.15, "fade": 0.04, "roll": 0.97,
                                       "gamma": (0.95, 0.98, 1.03), "gain": (1.0, 0.99, 0.96)},
                 "grain": 3.0, "vignette": 0.15},
    "golden": {"sat": 1.15, "curve": {"contrast": 0.45, "fade": 0.03, "roll": 0.97,
                                      "gamma": (0.88, 0.96, 1.12), "gain": (1.0, 0.98, 0.88)},
               "grain": 4.0, "vignette": 0.25},
    "green": {"sat": 1.0, "curve": {"contrast": 0.4, "fade": 0.04, "roll": 0.96,
                                    "gamma": (1.04, 0.95, 0.99), "lift": (0.0, 0.03, 0.02)},
              "grain": 4.0, "vignette": 0.22},
    "instant": {"sat": 0.8, "curve": {"contrast": 0.2, "fade": 0.12, "roll": 0.92,
                                      "gamma": (0.94, 0.97, 1.05), "lift": (0.0, 0.02, 0.04),
                                      "gain": (1.0, 0.98, 0.9)}, "grain": 4.0, "vignette": 0.38},
    "faded70s": {"sat": 0.75, "curve": {"contrast": 0.2, "fade": 0.09, "roll": 0.93,
                                        "gamma": (0.85, 0.95, 1.2), "lift": (0.03, 0.01, 0.0),
                                        "gain": (1.0, 0.95, 0.82)}, "grain": 6.0, "vignette": 0.3},
    "cross": {"sat": 1.25, "curve": {"contrast": 0.7, "gamma": (0.9, 0.88, 1.2),
                                     "lift": (0.0, 0.0, 0.06), "gain": (1.0, 1.0, 0.82)},
              "grain": 3.0, "vignette": 0.2},
}


def camera_controls_from_settings():
    cx, cy, cw, ch = picam2.camera_properties["ScalerCropMaximum"]
    zw, zh = int(cw / settings["zoom"]), int(ch / settings["zoom"])
    c = {
        # Exposure can't be longer than a frame, so this caps the shutter;
        # "Short" makes auto-exposure raise gain before shutter time.
        "FrameDurationLimits": (100, settings["motion"]),
        "AeExposureMode": controls.AeExposureModeEnum.Short,
        "ExposureValue": settings["brightness"],
        "Saturation": COLOUR_LOOKS[settings["colour"]]["sat"],
    }
    light = settings["light"]
    if light == "auto":
        c["AwbEnable"] = True
        c["AwbMode"] = controls.AwbModeEnum.Auto
    elif _ct_curve:
        c["AwbEnable"] = False
        c["ColourGains"] = colour_gains(LIGHT_KELVIN[light])
    else:
        c["AwbEnable"] = True
        c["AwbMode"] = AWB_MODES[light]
    # The sensor size is only known once the camera is configured; until then it reads as 0.
    if cw and ch:
        c["ScalerCrop"] = (cx + (cw - zw) // 2, cy + (ch - zh) // 2, zw, zh)
    if settings["focus"] == "auto":
        c["AfMode"] = controls.AfModeEnum.Continuous
    else:
        c["AfMode"] = controls.AfModeEnum.Manual
        c["LensPosition"] = FOCUS_DIOPTRES[settings["focus"]]
    return c


def _configure_camera():
    # Outside the try: a mistake here is a bug to see, not an unsupported format.
    camera_controls = camera_controls_from_settings()
    # Pi 5 can deliver lores as RGB (PIL-ready); older Pis only allow YUV420.
    for fmt in ("BGR888", "YUV420"):
        try:
            picam2.configure(picam2.create_still_configuration(
                main={"size": (CAPTURE_W, CAPTURE_H)},
                lores={"size": (PREVIEW_W, PREVIEW_H), "format": fmt},
                transform=CAMERA_TRANSFORM,
                controls=camera_controls,
            ))
            return fmt
        except Exception as e:
            print(f"Lores format {fmt} not supported: {e}")
    raise RuntimeError("Could not configure camera")


try:
    LORES_FORMAT = _configure_camera()
    print(f"Camera configured: main {CAPTURE_W}x{CAPTURE_H}, lores {LORES_FORMAT}")
    picam2.start()
    # Again now the sensor size is known, so the zoom (ScalerCrop) applies from the start.
    picam2.set_controls(camera_controls_from_settings())
except RuntimeError as e:
    print(f"Camera failed to start: {e}")
    _fatal_screen("CAMERA PROBLEM\n\nTurn the booth off and on again.\n\nTrying again...")
camera_running = True
time.sleep(1.5)


def camera_failed(what):
    # A stalled camera doesn't recover in-process (even stop() can hang), so exit and
    # let photobooth.service start a fresh process, which gets a working camera.
    print(f"Camera stalled during {what}; exiting so the service restarts the app.", flush=True)
    try:
        save_partial_strip_before_shutdown()  # startup deletes leftover captures
    except Exception as e:
        print(f"Could not save the strip in progress: {e}", flush=True)
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


def sd_notify(message):
    if not _NOTIFY_SOCKET:
        return
    addr = _NOTIFY_SOCKET
    if addr.startswith("@"):
        addr = "\0" + addr[1:]
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as s:
            s.sendto(message, addr)
    except OSError as e:
        print(f"systemd notify failed: {e}")


def watchdog_ping():
    # Tells systemd the main loop is alive; if the pings stop (app frozen), systemd restarts it.
    global _last_watchdog_ping
    now = time.monotonic()
    if now - _last_watchdog_ping < 5:
        return
    _last_watchdog_ping = now
    sd_notify(b"WATCHDOG=1")


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
        apply_theme()  # the new looks only apply on its side
        _invalidate_live_preview()
    elif key in ("theme", "look"):
        apply_theme()
        _invalidate_live_preview()
    elif key == "edge" or key in EFFECT_KEYS:
        _invalidate_live_preview()
    elif key in {k for k, _, _, _ in CAMERA_SETTINGS}:
        apply_camera_settings()


end_boot_splash()
pygame.init()

lcd = None

if USE_LCD:
    try:
        lcd = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        pygame.mouse.set_visible(False)
        print(f"LCD initialized: {lcd.get_size()}")
        try:
            # The splash's picture again, until the first real screen is ready (a second or so).
            if SPLASH_PICTURE.exists():
                still = pygame.image.load(str(SPLASH_PICTURE))
                if still.get_size() == lcd.get_size():
                    lcd.blit(still, (0, 0))
                    pygame.display.flip()
        except Exception as e:
            print(f"Could not show the splash picture: {e}")
    except Exception as e:
        lcd = None
        print(f"LCD not available: {e}")
        if os.environ.get("INVOCATION_ID"):
            # Started by systemd: the screen may not be ready yet at boot. Exit so it retries
            # instead of running without a screen.
            raise SystemExit(1)


def _mtime(path):
    try:
        return path.stat().st_mtime_ns
    except OSError:
        return None


def _frame_sort_key(path):
    # frame2 before frame10: compare the number, not the text.
    digits = "".join(ch for ch in path.stem if ch.isdigit())
    return (int(digits) if digits else 0, path.name, str(path))


def _booth_name():
    """The person this booth was set up for (system/gifts.py), or None."""
    try:
        result = subprocess.run(["git", "-C", str(BASE), "config", "--get", "snapbox.booth"],
                                capture_output=True, text=True, timeout=10)
    except Exception as e:
        print(f"Could not read the booth's name: {e}")
        return None
    return result.stdout.strip() or None


BOOTH_NAME = None
for _sub in ("", "sheets", "portrait"):
    try:
        (MY_DESIGNS_DIR / _sub).mkdir(parents=True, exist_ok=True)
    except OSError as e:
        print(f"Could not make {MY_DESIGNS_DIR / _sub}: {e}")


def design_id(path):
    """Which design a saved strip used: its path from the home folder, e.g.
    "photobooth/gifts/Nick & Maddy Atkinson/army/frame32.png" or "my-designs/sheets/party.png"."""
    try:
        return str(path.relative_to(Path.home()))
    except ValueError:
        return str(path)


def read_design_slots(path, kind):
    """(the photo openings from the design's JSON, None), or (None, why it can't be used)."""
    sidecar = path.with_suffix(".json")
    if not sidecar.exists():
        # The original strips work without one; anything else must say where its photos go.
        return (DEFAULT_SLOTS, None) if kind == "strip" else (None, "no .json with its photo openings")
    try:
        data = json.loads(sidecar.read_text())
        raw = data.get("slots") if isinstance(data, dict) else data
        slots = [tuple(int(v) for v in slot) for slot in raw]
        if any(len(slot) != 4 for slot in slots):
            return None, "each opening needs x, y, width and height"
    except Exception as e:
        return None, f"its .json can't be read ({e})"
    w, h = DESIGN_SIZES[kind]
    if not 1 <= len(slots) <= MAX_DESIGN_PHOTOS:
        return None, f"it has {len(slots)} photo openings (1 to {MAX_DESIGN_PHOTOS} work)"
    for x, y, sw, sh in slots:
        if sw < 20 or sh < 20 or x < 0 or y < 0 or x + sw > w or y + sh > h:
            return None, f"opening {[x, y, sw, sh]} isn't inside {w}x{h}"
    return slots, None


_design_checks = {}  # (path, PNG mtime, JSON mtime) -> why it can't be used, or None


def design_problem(path, kind):
    """Why this design can't be used (logged once), or None if it's fine."""
    key = (path, _mtime(path), _mtime(path.with_suffix(".json")))
    if key not in _design_checks:
        w, h = DESIGN_SIZES[kind]
        try:
            with Image.open(path) as im:
                iw, ih = im.size
        except Exception as e:
            why = f"the picture can't be opened ({e})"
        else:
            if abs(iw * h - ih * w) > 0.02 * iw * h:
                why = f"it's {iw}x{ih}, but a design in this folder is {w}x{h}"
            elif iw * ih > 4 * w * h:
                why = f"it's {iw}x{ih}, far bigger than {w}x{h}"
            else:
                why = read_design_slots(path, kind)[1]
        if why:
            print(f"Skipping design {design_id(path)}: {why}")
        _design_checks[key] = why
    return _design_checks[key]


def _design_folders(root, nested=True):
    """root, and (if nested) every folder below it except the sheets/ and portrait/ in each."""
    if not root.is_dir():
        return []
    folders = [root]
    if nested:
        for d in sorted(root.rglob("*")):
            parts = d.relative_to(root).parts
            if d.is_dir() and not any(p in ("sheets", "portrait") or p.startswith((".", "__"))
                                      for p in parts):
                folders.append(d)
    return folders


def _gift_roots():
    """This booth's gifts: its person's folder; every person's on the master booth (the
    creator's) and on a booth never set up."""
    if BOOTH_NAME and BOOTH_NAME != "master":
        return [GIFTS_DIR / BOOTH_NAME]
    return sorted(p for p in GIFTS_DIR.iterdir() if p.is_dir()) if GIFTS_DIR.is_dir() else []


def _find_designs():
    """(designs, {path: kind}): strips first, then BIG SHEET designs; each kind is browsed on its
    own. Shared and gift designs are in number order together; the owner's own come after.
    Designs that can't be used (wrong size, no photo openings, damaged) are left out."""
    global BOOTH_NAME
    name = _booth_name()
    if name != BOOTH_NAME:
        print(f"This booth is now set up for: {name or 'nobody, so every gift'}")
        BOOTH_NAME = name
    ours = [f for f in _design_folders(FRAME_DIR, nested=False)]
    ours += [f for root in _gift_roots() for f in _design_folders(root)]
    mine = _design_folders(MY_DESIGNS_DIR)
    found, kinds = [], {}
    for kind, sub in DESIGN_SUBFOLDERS.items():
        def scan(folders):
            paths = []
            for folder in folders:
                try:
                    paths += [p for p in (folder / sub if sub else folder).glob("*.png")
                              if p.is_file() and not design_problem(p, kind)]
                except OSError as e:
                    print(f"Could not look in {folder}: {e}")
            return sorted(paths, key=_frame_sort_key)
        for path in scan(ours) + scan(mine):
            found.append(path)
            kinds[path] = kind
    return found, kinds


frames, _frame_kinds = _find_designs()
current_frame_index = 0
_designs_stale = False  # a design went missing or broke: look again right away
print(f"{len(frames)} designs (booth: {BOOTH_NAME or 'not set up, so every gift'}; "
      f"{sum(MY_DESIGNS_DIR in p.parents for p in frames)} in {MY_DESIGNS_DIR})")


def frame_kind(frame_index):
    if not frames:
        return "strip"
    return _frame_kinds.get(frames[frame_index], "strip")


def frame_size(frame_index):
    return {"sheet": (SHEET_W, SHEET_H), "psheet": (PSHEET_W, PSHEET_H)}.get(frame_kind(frame_index),
                                                                         (STRIP_W, STRIP_H))


def current_kind():
    return frame_kind(current_frame_index)


def image_kind(size):
    """A saved picture's layout from its shape: strips are 1:3, sheets 3:2 either way."""
    w, h = size
    return "sheet" if w > h else "strip" if h >= 2.5 * w else "psheet"


def is_sheet_size(size):
    return image_kind(size) != "strip"  # either sheet: shown whole, prints on its own

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
    global _designs_stale
    if not frames or frame_index < 0 or frame_index >= len(frames):
        return None

    frame_path = frames[frame_index]
    mtime = _mtime(frame_path)

    cached = _frame_img_cache.get(frame_index)
    if cached is not None and cached[0] == mtime:
        return cached[1]

    try:
        frame = Image.open(frame_path).convert("RGBA")
        frame = frame.resize(frame_size(frame_index), Image.LANCZOS)
    except Exception as e:
        # A missing or damaged design: the photos show without it this once, the design is
        # dropped and the booth moves on to one that's there (refresh_designs).
        print(f"Could not load design {design_id(frame_path)}: {e}")
        _design_checks[(frame_path, mtime, _mtime(frame_path.with_suffix(".json")))] = str(e)
        _designs_stale = True
        frame = None
    # Each frame is ~17 MB at full size; keep only the few most recent.
    while len(_frame_img_cache) >= 4:
        del _frame_img_cache[next(iter(_frame_img_cache))]
    _frame_img_cache[frame_index] = (mtime, frame)
    return frame


def load_current_frame():
    return load_frame_image(current_frame_index)


def _normalize_slots(raw):
    return [tuple(int(v) for v in slot) for slot in raw]


def _load_frame_config(frame_path):
    global _designs_stale
    slots, why = read_design_slots(frame_path, _frame_kinds.get(frame_path, "strip"))
    if why:
        # Broke since the booth found it: use the defaults until it's dropped (refresh_designs).
        print(f"Bad design {design_id(frame_path)}, using default openings: {why}")
        _designs_stale = True
        return DEFAULT_SLOTS
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


def indices_for_kind(kind=None):
    kind = kind or current_kind()
    return [i for i in range(len(frames)) if frame_kind(i) == kind]


def indices_for_capacity(capacity, kind=None):
    return [i for i in indices_for_kind(kind) if frame_slot_count(i) == capacity]


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


def compose_single_strip(strip_photos, frame_index=None, include_frame=True, fx=None):
    if frame_index is None:
        frame_index = current_frame_index
    canvas_w, canvas_h = frame_size(frame_index)
    strip = Image.new("RGBA", (canvas_w, canvas_h), "white")

    slots = frame_slots(frame_index)

    for i, photo in enumerate(strip_photos):
        if photo is None:
            continue
        if i >= len(slots):
            break

        x, y, w, h = slots[i]
        left = max(0, x - SLOT_BLEED)
        top = max(0, y - SLOT_BLEED)
        right = min(canvas_w, x + w + SLOT_BLEED)
        bottom = min(canvas_h, y + h + SLOT_BLEED)

        fitted = apply_effects(_fitted_slot_image(photo, right - left, bottom - top), i, fx,
                               frame_stamp_corner(frame_index))
        strip.alpha_composite(fitted, (left, top))

    if include_frame:
        frame = load_frame_image(frame_index)
        if frame is not None:
            strip.alpha_composite(frame, (0, 0))

    return strip


def is_landscape():
    return screen_rotation in (0, 180)


def panel_rotation():
    """How far (PIL degrees) to turn the UI to draw it on the panel."""
    if lcd is None:
        return screen_rotation
    return to_panel_rotation(screen_rotation, *lcd.get_size())


def full_ui_size():
    """The whole panel, turned the way the SCREEN setting shows it. The UI is drawn at the
    panel's real size (not scaled down), so text and buttons are as big as they can be."""
    if lcd is None:
        short, long = PORTRAIT_UI_W, PORTRAIT_UI_H
    else:
        short, long = sorted(lcd.get_size())
    return (long, short) if is_landscape() else (short, long)


def px_per_mm():
    w, h = full_ui_size()
    return math.hypot(w, h) / (SCREEN_DIAGONAL_INCHES * 25.4)


def ui_inset():
    """Blank strip on the viewer's left, where a 3D-printed bezel can cover the panel."""
    return round(settings["edge"] * px_per_mm())


def ui_size():
    """The area the app draws in: the panel, minus the bezel strip on the left."""
    w, h = full_ui_size()
    return w - ui_inset(), h


def strip_halves(slots):
    """Cuts the strip in two between the middle photos: header + first photos, rest + footer."""
    first = (len(slots) + 1) // 2
    if len(slots) < 2:
        return [(0, 0, STRIP_W, STRIP_H)]
    above = slots[first - 1][1] + slots[first - 1][3]
    below = slots[first][1]
    cut = (above + below) // 2
    return [(0, 0, STRIP_W, cut), (0, cut, STRIP_W, STRIP_H)]


def display_layout(slots=None, size=(STRIP_W, STRIP_H)):
    """[(strip box, UI box)] pairs: where each piece of the strip (or sheet) goes on screen."""
    ui_w, ui_h = ui_size()
    # The part of the screen the strip may use: beside the round buttons, or inside the look's frame.
    if look() != "original":
        geo = looks.geometry(look(), ui_w, ui_h)
        rx0, ry0, rx1, ry1 = (round(v) for v in geo["stage"])
        pad = round(geo["pad"])
    else:
        rx0, ry0, rx1, ry1 = ICON_SIZE + 2 * ICON_MARGIN, 0, ui_w, ui_h
        pad = LANDSCAPE_CELL_PAD
    rw, rh = rx1 - rx0, ry1 - ry0

    if is_sheet_size(size):
        # A sheet is shown whole.
        scale = min((rw - 2 * pad) / size[0], (rh - 2 * pad) / size[1])
        sw, sh = max(1, int(size[0] * scale)), max(1, int(size[1] * scale))
        dest = (rx0 + (rw - sw) // 2, ry0 + (rh - sh) // 2, sw, sh)
        return [((0, 0) + tuple(size), dest)]

    if not is_landscape() or not slots:
        scale = min(ui_w / STRIP_W, ui_h / STRIP_H)
        sw = max(1, int(STRIP_W * scale))
        sh = max(1, int(STRIP_H * scale))
        dest = ((ui_w - sw) // 2, (ui_h - sh) // 2, sw, sh)
        return [((0, 0, STRIP_W, STRIP_H), dest)]

    # Landscape: the strip cut in half between the middle photos, halves side by side,
    # so the frame's header and footer stay visible.
    halves = strip_halves(slots)
    cell_w = rw // len(halves)
    half_h = max(b[3] - b[1] for b in halves)
    scale = min(
        (cell_w - 2 * pad) / STRIP_W,
        (rh - 2 * pad) / half_h,
    )

    layout = []
    for col, half in enumerate(halves):
        dw = max(1, int((half[2] - half[0]) * scale))
        dh = max(1, int((half[3] - half[1]) * scale))
        dx = rx0 + col * cell_w + (cell_w - dw) // 2
        # Left half hangs from the top, right half sits on the bottom: one strip, folded.
        dy = ry0 + pad if col == 0 else ry1 - pad - dh
        layout.append((half, (dx, dy, dw, dh)))
    return layout


_main_layout_rects = ()  # where the strip's pieces are on the main screen right now


def render_strip_to_ui(strip, layout, resample, transparent=False):
    global _main_layout_rects
    _main_layout_rects = tuple((dx, dy, dx + dw, dy + dh) for _, (dx, dy, dw, dh) in layout)
    if transparent:
        canvas = Image.new("RGBA", ui_size(), (0, 0, 0, 0))
    else:
        canvas = Image.new("RGB", ui_size(), MAIN_BG)
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

    return render_strip_to_ui(strip, display_layout(slots, strip.size), Image.LANCZOS)


def should_show_live_preview():
    return (
        lcd is not None
        and not screen_asleep
        and not menu_open
        and not gallery_open
        and _photo_show_img is None
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

    size = frame_size(current_frame_index)
    layout = display_layout(slots, size)
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
        min(size[0], x + w + SLOT_BLEED),
        min(size[1], y + h + SLOT_BLEED),
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


_colour_luts = {}
_vignettes = {}


def _colour_lut(name):
    if name not in _colour_luts:
        c = COLOUR_LOOKS[name]["curve"]
        x = np.arange(256) / 255.0
        s_curve = 0.5 - 0.5 * np.cos(np.pi * x)
        k = c.get("contrast", 0.0)
        tone = (1.0 - k) * x + k * s_curve  # negative contrast flattens instead
        fade, roll = c.get("fade", 0.0), c.get("roll", 1.0)
        tone = fade + (roll - fade) * np.clip(tone, 0.0, 1.0)
        lut = []
        for i in range(3):
            gamma = c.get("gamma", (1.0, 1.0, 1.0))[i]
            lift = c.get("lift", (0.0, 0.0, 0.0))[i]
            gain = c.get("gain", (1.0, 1.0, 1.0))[i]
            channel = lift + (gain - lift) * tone ** gamma
            lut.extend(np.clip(channel * 255.0, 0, 255).astype(np.uint8).tolist())
        _colour_luts[name] = lut
    return _colour_luts[name]


def _vignette(w, h, strength):
    key = (w, h, strength)
    if key not in _vignettes:
        if len(_vignettes) > 8:
            _vignettes.clear()
        ys = np.linspace(-1.0, 1.0, h, dtype=np.float32)[:, None]
        xs = np.linspace(-1.0, 1.0, w, dtype=np.float32)[None, :]
        r2 = (xs * xs + ys * ys) / 2.0
        _vignettes[key] = (1.0 - strength * r2 ** 1.5)[..., None]
    return _vignettes[key]


def apply_colour_look(img, name=None):
    name = name or settings["colour"]
    look = COLOUR_LOOKS.get(name, COLOUR_LOOKS["normal"])
    if look["sat"] != 0 and "curve" not in look and "grain" not in look and "vignette" not in look:
        return img
    img = img.convert("RGB")
    if look["sat"] == 0:
        # The camera's saturation change takes a second or more to arrive, so B&W looks
        # also go grey here: right away, and certain for the photo.
        img = img.convert("L").convert("RGB")
    if "curve" in look:
        img = img.point(_colour_lut(name))
    if "grain" not in look and "vignette" not in look:
        return img
    a = np.asarray(img, dtype=np.float32)
    h, w = a.shape[:2]
    if "vignette" in look:
        a = a * _vignette(w, h, look["vignette"])
    if "grain" in look:
        # Grain at half resolution so it stays visible once the photo is scaled down.
        grain = np.random.normal(0.0, look["grain"], ((h + 1) // 2, (w + 1) // 2))
        grain = grain.astype(np.float32).repeat(2, axis=0).repeat(2, axis=1)[:h, :w]
        a += grain[..., None]
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), "RGB")


# ---------------------------------------------------------------------------
# Vintage add-ons (EFFECTS tab): date stamp, light leaks, red light spots, streaks and dust.
# Drawn on each photo after it is fitted to its slot, under the frame, so they work with every
# frame and stack. Every size is relative to the photo and every random choice comes from the
# photo's seed, so the small live preview and the full-size strip get the same effect.
# ---------------------------------------------------------------------------

EFFECT_KEYS = [k for k, _, _, _ in EFFECT_SETTINGS]
FX_KEYS = ("stamp", "leaks", "spots", "lines")  # what a strip's fx "opts" holds, in this order
FX_STYLES = {"leaks": LEAK_STYLES, "spots": SPOT_STYLES, "lines": LINE_STYLES}
# RANDOM's styles (by number). One on its own is at full strength, so the heaviest (FULL BURN,
# STROBE BURST, HEAVY DUST, WORN OUT) are left out; a mix is two gentle ones at RANDOM_SOFT.
RANDOM_ONE = {"leaks": range(1, 10), "spots": range(1, 10), "lines": (1, 3, 4, 5, 6, 7, 8, 9)}
RANDOM_GENTLE = {"leaks": (1, 2, 3, 4, 5, 8), "spots": (1, 2, 3, 4, 6, 7), "lines": (1, 3, 4, 5, 6, 7)}
RANDOM_SOFT = 0.55
RANDOM_NONE = 0.35  # chance a photo gets no effect at all; otherwise half one, half a subtle two
STAMP_COLOUR = (255, 138, 28)
# Seven-segment digits, like the date imprint of a 90s film camera.
SEGMENTS = {"0": "abcdef", "1": "bc", "2": "abdeg", "3": "abcdg", "4": "bcfg", "5": "acdfg",
            "6": "acdefg", "7": "abc", "8": "abcdefg", "9": "abcdfg"}
strip_seed = random.randrange(1 << 30)  # saved with each strip (older versions varied by it)
random_rolls = {}  # photo number -> what the RANDOM effect picks from; cleared for every strip
_effect_cache = {}


def effects_on():
    return any(settings[k] for k in EFFECT_KEYS)


def stamp_date():
    """The day the date stamp shows: the one typed in (MY DATE), or the clock's."""
    if settings["stamp"] == "custom" and settings.get("stamp_date"):
        try:
            return datetime.strptime(settings["stamp_date"], "%Y-%m-%d")
        except ValueError:
            pass
    return datetime.now()


def stamp_text():
    return stamp_date().strftime("%m %d '%y")  # 10 06 '26


def _random_draw(rnd):
    if rnd.random() < RANDOM_NONE:
        return {}, 1.0
    if rnd.random() < 0.5:
        return {key: rnd.choice(RANDOM_GENTLE[key]) for key in rnd.sample(sorted(FX_STYLES), 2)}, RANDOM_SOFT
    key = rnd.choice(sorted(FX_STYLES))
    return {key: rnd.choice(RANDOM_ONE[key])}, 1.0


def random_pick(index):
    """RANDOM's choice for photo `index` of this strip: ({"leaks": style number, ...}, strength).
    Never the same effect as the photo before it (two plain photos in a row can happen)."""
    if not settings["random"]:
        return {}, 1.0
    if index not in random_rolls:
        random_rolls[index] = random.randrange(1 << 30)
    rnd = random.Random(random_rolls[index])
    before = random_pick(index - 1) if index > 0 else None
    for _ in range(8):
        pick = _random_draw(rnd)
        if pick != before or not pick[0]:
            break
    return pick


def reroll_random():
    """Tap the RANDOM setting: pick again for the next photo."""
    if settings["random"]:
        random_rolls[_preview_slot_index()] = random.randrange(1 << 30)
        _invalidate_live_preview()


def effect_opts(index):
    """[stamp, leaks, spots, lines] for photo `index` of the strip being made, and their strength."""
    if not settings["random"]:
        return [bool(settings["stamp"])] + [settings[k] for k in FX_KEYS[1:]], 1.0
    pick, soft = random_pick(index)
    return [bool(settings["stamp"])] + [pick.get(k, 0) for k in FX_KEYS[1:]], soft


def _seg_poly(x0, y0, x1, y1, t):
    """One segment as a hexagon from (x0, y0) to (x1, y1), pointed at both ends."""
    if y0 == y1:
        pts = [(x0, y0), (x0 + t / 2, y0 - t / 2), (x1 - t / 2, y0 - t / 2), (x1, y0),
               (x1 - t / 2, y0 + t / 2), (x0 + t / 2, y0 + t / 2)]
    else:
        pts = [(x0, y0), (x0 + t / 2, y0 + t / 2), (x0 + t / 2, y1 - t / 2), (x0, y1),
               (x0 - t / 2, y1 - t / 2), (x0 - t / 2, y0 + t / 2)]
    return pts


def _draw_stamp(draw, right, bottom, digit_h, text, fill):
    """Seven-segment date, right-aligned at (right, bottom), leaning like the real thing."""
    dw, t = digit_h * 0.52, digit_h * 0.13
    gap, space, g = digit_h * 0.16, digit_h * 0.34, t * 0.18
    widths = [dw if ch.isdigit() else space if ch == " " else t * 1.4 for ch in text]
    x = right - sum(widths) - gap * (len(text) - 1)
    top = bottom - digit_h
    slant = 0.12

    def lean(pts):
        return [(px + slant * (bottom - py), py) for px, py in pts]

    for ch, w in zip(text, widths):
        if ch in SEGMENTS:
            mid = top + digit_h / 2
            rows = {"a": top + t / 2, "g": mid, "d": bottom - t / 2}
            for seg in SEGMENTS[ch]:
                if seg in rows:
                    y = rows[seg]
                    pts = _seg_poly(x + g + t / 2, y, x + w - g - t / 2, y, t)
                else:
                    sx = x + t / 2 if seg in "fe" else x + w - t / 2
                    y0, y1 = (top + t / 2 + g, mid - g) if seg in "fb" else (mid + g, bottom - t / 2 - g)
                    pts = _seg_poly(sx, y0, sx, y1, t)
                draw.polygon(lean(pts), fill=fill)
        elif ch == "'":
            draw.polygon(lean([(x + t * 0.5, top), (x + t * 1.4, top), (x + t * 0.8, top + digit_h * 0.3),
                               (x + t * 0.1, top + digit_h * 0.3)]), fill=fill)
        x += w + gap


def _stamp_width(digit_h, text):
    dw, t = digit_h * 0.52, digit_h * 0.13
    gap, space = digit_h * 0.16, digit_h * 0.34
    widths = [dw if ch.isdigit() else space if ch == " " else t * 1.4 for ch in text]
    return sum(widths) + gap * (len(text) - 1)


def _render_effects(w, h, seed, opts, text, bw, corner="br", soft=1.0):
    """(screen layer RGB or None, overlay RGBA or None) for a w x h photo. `seed` is unused
    now (every style looks the same each time); it stays so saved strips keep working.
    `soft` (0-1) tones the light, dust and scratches down."""
    stamp, leaks, spots, lines = opts
    m = min(w, h)
    screen = None
    # Soft light is drawn small and blurred, then enlarged: fast, and smooth anyway.
    sw, sh = max(16, w // 6), max(16, h // 6)
    sm = min(sw, sh)

    def add(layer):
        nonlocal screen
        screen = layer if screen is None else ImageChops.screen(screen, layer)

    def tint(colour, k):
        return tuple(int(v * k * soft) for v in colour)

    def count(n):
        return max(1, round(n * soft)) if n else 0

    if leaks:
        band, blobs = LEAK_STYLES[leaks - 1][1:]
        layer = Image.new("RGB", (sw, sh), "black")
        d = ImageDraw.Draw(layer)
        for x, y, rx, ry, colour, k in blobs:
            cx, cy, ax, ay = x * sw, y * sh, rx * sm, ry * sm
            d.ellipse((cx - ax, cy - ay, cx + ax, cy + ay), fill=tint(colour, k))
        if band:
            side, size, k = band
            b = size * sm
            box = {"left": (0, 0, b, sh), "right": (sw - b, 0, sw, sh), "top": (0, 0, sw, b),
                   "bottom": (0, sh - b, sw, sh)}[side]
            d.rectangle(box, fill=tint((255, 70, 20), k))
        add(layer.filter(ImageFilter.GaussianBlur(sm * 0.14)).resize((w, h), Image.BILINEAR))

    if spots:
        # Light on film: no hard discs. Each orb is a hot, slightly pale core falling off smoothly
        # into a wide faint halo, a touch out of round; rings are soft, uneven and doubled like a
        # lens reflection. Built from smooth maths at a small size (it is all blur), then enlarged.
        items = SPOT_STYLES[spots - 1][1]
        gw, gh = max(24, w // 3), max(24, h // 3)
        gm = min(gw, gh)
        yy, xx = np.mgrid[0:gh, 0:gw].astype(np.float32)
        acc = np.zeros((gh, gw, 3), np.float32)
        rs = np.random.default_rng(500 + spots)
        for kind, x, y, r, colour, k in items:
            cx, cy, rr = x * gw, y * gh, r * gm
            squash = 1 + rs.uniform(-0.12, 0.12)   # never a perfect circle
            turn = rs.uniform(0, math.pi)
            dx, dy = xx - cx, yy - cy
            u = dx * math.cos(turn) + dy * math.sin(turn)
            v = (-dx * math.sin(turn) + dy * math.cos(turn)) * squash
            d = np.sqrt(u * u + v * v) / max(1.0, rr)
            col = np.array(colour, np.float32) / 255.0
            if kind == "orb":
                core = np.exp(-(d / 0.55) ** 2)             # the hot middle
                body = np.exp(-(d / 1.0) ** 2.4) * 0.75      # the orb itself, soft-edged
                halo = np.exp(-(d / 2.3) ** 1.6) * 0.22      # the glow around it
                pale = col + (1 - col) * 0.55                 # the middle burns towards white
                acc += (core[..., None] * pale * 0.55 + (body + halo)[..., None] * col) * k
            else:
                side = 0.72 + 0.28 * np.cos(np.arctan2(v, u) - turn)   # brighter on one side
                band = np.exp(-((d - 1.0) / 0.055) ** 2)
                glow = np.exp(-((d - 1.0) / 0.16) ** 2) * 0.35
                ghost = np.exp(-((d - 0.86) / 0.04) ** 2) * 0.3         # a fainter inner reflection
                warm = np.clip(col * np.array([1.0, 1.5, 1.2], np.float32), 0, 1)
                acc += ((band + glow)[..., None] * col + ghost[..., None] * warm) * side[..., None] * k
        acc *= soft
        layer = Image.fromarray((np.clip(acc, 0, 1) * 255).astype(np.uint8), "RGB")
        add(layer.resize((w, h), Image.BICUBIC))

    overlay = None
    if lines:
        spec = LINE_STYLES[lines - 1][1]
        rnd = random.Random(1000 + lines)  # fixed: the dust lands in the same places every time
        if spec.get("streaks"):
            # A light streak is a thin bright thread inside a wider soft glow, wandering a little
            # and fading in and out along its length; never a ruled line.
            rs = np.random.default_rng(2000 + lines)
            ys = np.arange(h, dtype=np.float32)
            xs = np.arange(w, dtype=np.float32)
            acc = np.zeros((h, w), np.float32)
            for x, width, k in spec["streaks"]:
                drift = (x * w + 0.01 * w * ys / max(1, h)
                         + m * 0.004 * np.sin(ys / h * rs.uniform(2, 5) + rs.uniform(0, 6))
                         + m * 0.0012 * np.sin(ys / h * rs.uniform(11, 19) + rs.uniform(0, 6)))
                # strength along the streak: a few slow waves, so it breathes and breaks
                along = 0.55 + 0.45 * np.sin(ys / h * rs.uniform(1.5, 3.5) + rs.uniform(0, 6))
                along *= 0.8 + 0.2 * np.sin(ys / h * rs.uniform(7, 13) + rs.uniform(0, 6))
                along = np.clip(along, 0.08, 1.0)
                core_w = max(0.6, m * width * 0.22)
                glow_w = max(1.5, m * width * 1.3)
                dist = xs[None, :] - drift[:, None]
                acc += (np.exp(-(dist / core_w) ** 2) * 0.9 + np.exp(-(dist / glow_w) ** 2) * 0.4) * along[:, None] * k
            acc = np.clip(acc * soft, 0, 1)
            warm = np.array([255, 205, 160], np.float32)
            add(Image.fromarray((acc[..., None] * warm).astype(np.uint8), "RGB"))
        # Dust, hairs and scratches are drawn three times the size and shrunk, so they come out as
        # fine as the real thing: specks are irregular and mostly tiny, hairs curl, scratches waver
        # and break up.
        q = 3 if max(w, h) <= 1400 else 2
        big_layer = Image.new("RGBA", (w * q, h * q), (0, 0, 0, 0))
        od = ImageDraw.Draw(big_layer, "RGBA")
        big = 1.6 if spec.get("big") else 1.0
        mq = m * q
        for _ in range(count(spec.get("dust", 0)) * 3):
            x, y = rnd.uniform(0, w * q), rnd.uniform(0, h * q)
            # mostly pin-pricks, now and then a bigger fleck
            r = mq * (rnd.uniform(0.0004, 0.0014) if rnd.random() < 0.82 else rnd.uniform(0.0016, 0.0034)) * big
            dark = rnd.random() < 0.6
            c = (22, 17, 13, rnd.randint(70, 170)) if dark else (255, 250, 240, rnd.randint(50, 130))
            ang = rnd.uniform(0, math.pi)
            pts = []
            for i in range(7):   # a lumpy little shape, not a circle
                a = ang + i * 2 * math.pi / 7
                rr = r * rnd.uniform(0.55, 1.25)
                pts.append((x + rr * math.cos(a) * rnd.uniform(0.7, 1.5), y + rr * math.sin(a)))
            od.polygon(pts, fill=c)
        for _ in range(count(spec.get("hairs", 0))):   # hairs and fibres: long gentle curls
            x, y = rnd.uniform(0, w * q), rnd.uniform(0, h * q)
            ang, bend = rnd.uniform(0, 2 * math.pi), rnd.uniform(-0.16, 0.16)
            length = rnd.randint(18, 34)
            step = mq * rnd.uniform(0.0035, 0.006)
            alpha = rnd.randint(70, 130)
            wid = max(1, round(mq * rnd.uniform(0.0007, 0.0012)))
            pts = [(x, y)]
            for i in range(length):
                bend += rnd.uniform(-0.035, 0.035)
                ang += bend
                x, y = x + step * math.cos(ang), y + step * math.sin(ang)
                pts.append((x, y))
            for i in range(len(pts) - 1):   # thinner and fainter towards both ends
                t = i / (len(pts) - 1)
                fade = min(1.0, 4 * t * (1 - t) + 0.25)
                od.line((pts[i], pts[i + 1]), fill=(28, 22, 17, int(alpha * fade)), width=wid)
        for _ in range(count(spec.get("scratches", 0))):   # scratches down the emulsion
            x = rnd.uniform(0, w * q)
            top, bottom = sorted((rnd.uniform(-0.2, 0.5) * h * q, rnd.uniform(0.5, 1.2) * h * q))
            lean = rnd.uniform(-0.008, 0.008) * w * q
            alpha = rnd.randint(40, 95)
            wid = max(1, round(mq * 0.0006))
            phase, wob = rnd.uniform(0, 6), mq * rnd.uniform(0.0003, 0.0009)
            y = top
            while y < bottom:
                seg = mq * rnd.uniform(0.01, 0.07)
                if rnd.random() < 0.82:   # the rest are gaps: a scratch skips
                    y2 = min(bottom, y + seg)
                    t0, t1 = (y - top) / (bottom - top), (y2 - top) / (bottom - top)
                    x0 = x + lean * t0 + wob * math.sin(phase + y / mq * 40)
                    x1 = x + lean * t1 + wob * math.sin(phase + y2 / mq * 40)
                    od.line((x0, y, x1, y2), fill=(255, 252, 244, int(alpha * rnd.uniform(0.5, 1.0))), width=wid)
                y += seg * rnd.uniform(1.0, 1.25)
        overlay = big_layer.resize((w, h), Image.LANCZOS)

    if screen is not None and bw:
        screen = screen.convert("L").convert("RGB")  # light on black and white film is grey

    if stamp:
        if overlay is None:
            overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        digit_h = max(8, h * 0.075)
        # Bottom right like a film camera, unless the frame puts something there (frame JSON "stamp").
        margin_x, margin_y = max(w, h) * 0.06, h * 0.08
        right = w - margin_x if corner[1] == "r" else margin_x + _stamp_width(digit_h, text) + digit_h * 0.12
        bottom = h - margin_y if corner[0] == "b" else margin_y + digit_h
        lit = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        _draw_stamp(ImageDraw.Draw(lit), right, bottom, digit_h, text, STAMP_COLOUR + (255,))
        glow = lit.filter(ImageFilter.GaussianBlur(max(1, digit_h * 0.18)))
        overlay.alpha_composite(glow)
        overlay.alpha_composite(glow)
        lit.putalpha(lit.getchannel("A").point(lambda v: v * 0.85))
        overlay.alpha_composite(lit)
    return screen, overlay


def current_fx():
    """The add-ons for the strip being made, saved with it so re-framing redraws the same ones.
    With RANDOM, each photo's own are in "slots" ("opts" is the first photo's, for older versions)."""
    opts, soft = effect_opts(0)
    fx = {"seed": strip_seed, "opts": opts, "soft": soft, "stamp": stamp_text(),
          "bw": COLOUR_LOOKS.get(settings["colour"], {}).get("sat", 1.0) == 0}
    if settings["random"]:
        fx["slots"] = [dict(zip(("opts", "soft"), effect_opts(i))) for i in range(current_capacity())]
    return fx


_stamp_corners = {}


def frame_stamp_corner(frame_index):
    """Where this frame wants the date stamp: "br" (bottom right, the default), "bl", "tr", "tl"."""
    if not frames:
        return "br"
    sidecar = frames[frame_index].with_suffix(".json")
    key = (sidecar, _mtime(sidecar))
    if key not in _stamp_corners:
        try:
            corner = json.loads(sidecar.read_text()).get("stamp", "br")
        except Exception:
            corner = "br"
        _stamp_corners[key] = corner if corner in ("br", "bl", "tr", "tl") else "br"
    return _stamp_corners[key]


def apply_effects(img, index, fx=None, corner=None):
    """img (a photo fitted to slot `index`) with the EFFECTS add-ons drawn on: the current
    settings, or `fx` (from current_fx) for a saved strip; the date stamp goes in `corner`
    (default: where the current frame wants it)."""
    if corner is None:
        corner = frame_stamp_corner(current_frame_index)
    if fx is None:
        if not effects_on():
            return img
        fx = current_fx()
    slot = fx["slots"][index] if index < len(fx.get("slots", ())) else fx
    opts = tuple(slot["opts"])
    if not any(opts):
        return img
    seed, text, bw, soft = fx["seed"], fx["stamp"], fx["bw"], slot.get("soft", 1.0)
    key = (img.size, seed, index, opts, text, bw, corner, soft)
    layers = _effect_cache.get(key)
    if layers is None:
        if len(_effect_cache) >= 12:
            del _effect_cache[next(iter(_effect_cache))]
        layers = _effect_cache[key] = _render_effects(*img.size, seed * 8 + index, opts, text, bw, corner,
                                                      soft)
    screen, overlay = layers
    mode = img.mode
    out = img.convert("RGB")
    if screen is not None:
        out = ImageChops.screen(out, screen)
    if overlay is not None:
        out = out.convert("RGBA")
        out.alpha_composite(overlay)
    return out.convert(mode) if out.mode != mode else out


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
    fitted = apply_effects(center_crop_to_slot(cam, sw, sh, resample=Image.BILINEAR), current_slot)

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
    if settings["theme"] == "classic":
        draw.rectangle(box, fill=(0, 0, 0, 190))
    else:
        _rrect(draw, box, radius=10, fill=MENU_BG + (225,), outline=MENU_ACCENT + (255,),
                               width=2)

    y = cy - total_h // 2
    for (w, h, bx, by), line in zip(line_sizes, lines):
        draw.text(
            (cx - w // 2 - bx, y - by),
            line,
            font=font,
            fill=MENU_TEXT + (255,),
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
            if menu_open:
                img = render_menu(_menu_last_cam)
            elif gallery_open:
                img = render_gallery()
            elif _photo_show_img is not None:
                img = _photo_show_img
            else:
                img = compose_display()

        img = img.copy()
        if overlay_text is None and auto_off_banner is not None:
            overlay_text = auto_off_banner
        on_main = not menu_open and not gallery_open and not fullscreen_view
        framed = on_main and look() != "original" and img.size == ui_size()
        if framed:
            # MODERN / CLASSIC: everything around the strip is one cached picture (looks.py).
            chrome = _look_chrome()
            img.paste(chrome, (0, 0), chrome)
        if countdown_value is not None:
            _draw_countdown(img)
        if overlay_text is not None:
            _draw_centered_banner(img, overlay_text)
        elif on_main and not framed:
            if in_review() and review_started is not None:
                _draw_review_hint(img, review_seconds_left())
            _draw_corner_buttons(img)
        if not framed:
            _draw_battery_indicator(img)
        if overlay_text is None:
            _draw_printer_status(img, badge=on_main and not framed)

        inset = ui_inset()
        if inset:
            # Shifted right: black under the bezel on the viewer's left.
            full = Image.new("RGB", full_ui_size(), "black")
            full.paste(img.convert("RGB"), (inset, 0))
            img = full

        img = img.rotate(panel_rotation(), expand=True)

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
    close_gallery(redraw=False)
    # Left streaming with nothing reading it, the camera can stall; it also saves power.
    stop_camera()


def wake_screen(camera=True, activity=True):
    """Turns the screen back on. Returns True if it was asleep."""
    global screen_asleep
    if activity:
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
    # Taps made while the message was up would all act now (PRINT tapped five times = more sheets).
    pygame.event.clear()
    update_lcd()


def save_preview():
    _invalidate_live_preview()
    preview = compose_display()

    path = BASE / "current_preview.jpg"
    preview.save(path, quality=90)

    print(f"Preview updated: {path}")

    if _photo_show_img is None:
        update_lcd(preview)


# A strip's photos (colour look applied, no frame) are kept here so its frame can be changed
# later in REVIEW. Long side capped: plenty for a slot, about 0.3 MB each.
PHOTOS_DIR = ARCHIVE_DIR / "photos"
KEPT_PHOTO_MAX = 1600


def strip_photos_dir(strip_path):
    return PHOTOS_DIR / Path(strip_path).stem


def strip_meta(slots, frame_index, fx):
    """What goes in a strip JPEG's comment: its layout, and enough to re-frame it."""
    return json.dumps({"slots": slots, "frame": frames[frame_index].name if frames else None,
                       "design": design_id(frames[frame_index]) if frames else None,
                       "fx": fx}).encode()


def save_strip_photos(strip_path, photos):
    folder = strip_photos_dir(strip_path)
    try:
        folder.mkdir(parents=True, exist_ok=True)
        for i, photo in enumerate(photos):
            if photo is None:
                continue
            small = photo.copy()
            small.thumbnail((KEPT_PHOTO_MAX, KEPT_PHOTO_MAX), Image.BILINEAR)
            write_file_durably(folder / f"photo{i}.jpg",
                               lambda f, im=small: im.save(f, format="JPEG", quality=92))
    except OSError as e:
        # The strip still saves; it just can't be re-framed later.
        print(f"Could not keep the photos of {Path(strip_path).name}: {e}")
        shutil.rmtree(folder, ignore_errors=True)


def save_finished_strip():
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    jpg_archive_path = ARCHIVE_DIR / f"strip_{timestamp}.jpg"

    strip = compose_single_strip(live_photos)
    save_strip_photos(jpg_archive_path, live_photos)
    meta = strip_meta(current_frame_slots()[:len(live_photos)], current_frame_index, current_fx())
    # Durable before returning: the raw captures are deleted right after this.
    write_file_durably(jpg_archive_path, lambda f: strip.convert("RGB").save(
        f, format="JPEG", quality=95, comment=meta))

    print("")
    print("FINISHED STRIP SAVED")
    print(f"JPG archive: {jpg_archive_path}")
    print("")

    return jpg_archive_path


def delete_live_captures():
    for path in live_capture_paths:
        delete_capture_file(path)


def clear_live_strip():
    global live_photos, live_capture_paths, current_slot, strip_seed

    capacity = current_capacity()
    live_photos = [None] * capacity
    live_capture_paths = [None] * capacity
    current_slot = 0
    strip_seed = random.randrange(1 << 30)
    random_rolls.clear()
    _clear_photo_cache()


def start_fresh_strip():
    clear_live_strip()
    print("Started a fresh strip.")
    save_preview()


def save_and_advance():
    try:
        save_finished_strip()
    except OSError as e:
        # Keep the photos and captures so the strip can be saved once there's room.
        print(f"Could not save strip: {e}")
        flash_message("COULD NOT SAVE STRIP\nStorage full?\nDelete old strips in REVIEW", seconds=2.5)
        return
    # The strip JPG is the keeper; raw captures are only needed until it's built.
    delete_live_captures()
    start_fresh_strip()
    flash_message("STRIP SAVED", seconds=0.8)
    free = storage_free_bytes()
    if free is not None and free < STORAGE_LOW_BYTES:
        flash_message("STORAGE LOW\nDelete old strips\nin REVIEW", seconds=2.0)


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
    draw.rectangle((0, img.height - bar_h, img.width, img.height),
                   fill=(0, 0, 0, 190) if settings["theme"] == "classic" else MENU_BG + (215,))
    y = img.height - bar_h + 5
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        w = bbox[2] - bbox[0]
        draw.text(((img.width - w) // 2 - bbox[0], y - bbox[1]), line,
                  font=font, fill=MENU_TEXT + (255,))
        y += line_h


countdown_value = None


def _draw_countdown(img):
    # Big number over the photo being taken, see-through enough to still pose.
    box = _fullscreen_box if fullscreen_view else _live_preview_slot_box
    if box is None:
        box = (0, 0, img.width, img.height)
    if look() != "original" and fullscreen_view:
        overlay = _look_countdown(img.size)
        img.paste(overlay, (0, 0), overlay)
        return
    x, y, w, h = box
    size = max(40, int(min(w, h) * 0.75))
    draw = ImageDraw.Draw(img, "RGBA")
    draw.text((x + w // 2, y + h // 2), str(countdown_value), font=menu_font(size, True),
              fill=(255, 255, 255, 215), stroke_width=max(2, size // 25),
              stroke_fill=(0, 0, 0, 200), anchor="mm")


# Taking a photo fills the screen: the live camera during the countdown, then the photo itself
# for a few seconds, both cropped to the shape of the strip's photo slot.
PHOTO_SHOW_SECONDS = 3
fullscreen_view = False
_fullscreen_box = None  # where the photo sits on screen while full screen
_photo_show_img = None
_photo_show_until = 0.0


def _slot_aspect(index):
    slots = current_frame_slots()
    if 0 <= index < len(slots):
        _, _, w, h = slots[index]
        return (w + 2 * SLOT_BLEED) / (h + 2 * SLOT_BLEED)
    return CAPTURE_W / CAPTURE_H


def _fit_to_screen(img, aspect, effects_index=None):
    """img cropped to aspect, as large as the screen allows, centred on black; with
    effects_index, the EFFECTS add-ons that photo slot gets are drawn on too."""
    ui_w, ui_h = ui_size()
    w, h = ui_w, int(ui_w / aspect)
    if h > ui_h:
        w, h = int(ui_h * aspect), ui_h
    x, y = (ui_w - w) // 2, (ui_h - h) // 2
    canvas = Image.new("RGB", (ui_w, ui_h), MAIN_BG)
    fitted = center_crop_to_slot(img, w, h, resample=Image.BILINEAR)
    if effects_index is not None:
        fitted = apply_effects(fitted, effects_index)
    canvas.paste(fitted, (x, y))
    return canvas, (x, y, w, h)


def _show_fullscreen_camera():
    global _fullscreen_box
    try:
        cam = capture_preview_image()
    except TimeoutError:
        camera_failed("countdown preview")
    except Exception as e:
        print(f"Countdown preview capture failed: {e}")
        return
    canvas, _fullscreen_box = _fit_to_screen(cam, _slot_aspect(current_slot), current_slot)
    update_lcd(canvas, fast=True)


def start_photo_show(photo, index):
    global _photo_show_img, _photo_show_until, fullscreen_view, _fullscreen_box
    _photo_show_img, _fullscreen_box = _fit_to_screen(photo, _slot_aspect(index), index)
    _photo_show_until = time.monotonic() + PHOTO_SHOW_SECONDS
    fullscreen_view = True
    update_lcd()


def end_photo_show():
    global _photo_show_img, fullscreen_view
    if _photo_show_img is None:
        return
    _photo_show_img = None
    fullscreen_view = False
    _invalidate_live_preview()
    update_lcd()


def tick_photo_show():
    if _photo_show_img is not None and time.monotonic() >= _photo_show_until:
        end_photo_show()


def run_countdown():
    global countdown_value, fullscreen_view
    seconds = settings["countdown"]
    if not seconds or not should_show_live_preview():
        return
    end = time.monotonic() + seconds
    fullscreen_view = True
    try:
        while (left := end - time.monotonic()) > 0:
            countdown_value = math.ceil(left)
            _show_fullscreen_camera()
            watchdog_ping()
            time.sleep(1.0 / LIVE_PREVIEW_FPS)
    finally:
        countdown_value = None
        fullscreen_view = False
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

    free = storage_free_bytes()
    if free is not None and free < STORAGE_FULL_BYTES:
        print(f"Storage full ({free} bytes free); not taking a photo.")
        flash_message("STORAGE FULL\nDelete old strips\nin REVIEW", seconds=2.5)
        return

    run_countdown()

    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    capture_path = CAPTURE_DIR / f"capture_{timestamp}.jpg"

    print(f"Capturing photo {current_slot + 1}/{capacity}...")
    try:
        picam2.capture_file(str(capture_path), wait=CAMERA_TIMEOUT_SECONDS * 2)
    except TimeoutError:
        camera_failed("photo capture")
    except OSError as e:
        print(f"Could not save photo: {e}")
        delete_capture_file(capture_path)
        flash_message("COULD NOT SAVE PHOTO\nStorage full?", seconds=2.0)
        return

    img = Image.open(capture_path).convert("RGB")
    if img.width > CAPTURE_W or img.height > CAPTURE_H:
        img.thumbnail((CAPTURE_W, CAPTURE_H), Image.BILINEAR)
    img = apply_colour_look(img)
    live_photos[current_slot] = img
    live_capture_paths[current_slot] = capture_path

    start_photo_show(img, current_slot)
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


def next_frame_same_capacity(step=1):
    global current_frame_index

    if not frames:
        print("No frame PNGs found in ~/photobooth/frames")
        return

    capacity = current_capacity()
    # Before the first photo every design of this kind is on offer; after it, only the ones
    # with room for exactly as many photos.
    started = any(p is not None for p in live_photos)
    group = indices_for_capacity(capacity) if started else indices_for_kind()
    if not group:
        print(f"No frames with {capacity} slots.")
        return

    try:
        pos = group.index(current_frame_index)
        current_frame_index = group[(pos + step) % len(group)]
    except ValueError:
        current_frame_index = group[0]
    if current_capacity() != capacity:
        resize_live_photos(current_capacity())
        _clear_photo_cache()

    print(
        f"Changed frame to: {frames[current_frame_index].name} "
        f"(slots={current_capacity()})"
    )
    save_preview()


_last_frame_of_kind = {}  # the design last used in each layout, to come back to
_designs_next_scan = 0.0


def refresh_designs():
    """Picks up designs added, changed or gone since the app started (an update, a new gift, the
    owner's own), keeping the one in use if it's still there. True if anything changed."""
    global frames, _frame_kinds, current_frame_index, _last_frame_of_kind, _designs_stale
    if gallery_reframe is not None:
        return False  # CHANGE FRAME holds design numbers: look again once it's closed
    _designs_stale = False
    found, kinds = _find_designs()
    if found == frames:
        return False
    old = frames
    in_use = old[current_frame_index] if old else None
    kind = _frame_kinds.get(in_use, "strip")
    last_used = {k: old[i] for k, i in _last_frame_of_kind.items() if i < len(old)}
    frames, _frame_kinds = found, kinds
    _frame_img_cache.clear()
    _frame_cfg_cache.clear()
    _last_frame_of_kind = {k: found.index(p) for k, p in last_used.items() if p in found}
    if in_use in found:
        current_frame_index = found.index(in_use)
    else:
        # Gone: another of the same layout, with room for the photos already taken.
        taken = sum(p is not None for p in live_photos)
        group = indices_for_kind(kind) or list(range(len(found)))
        same = [i for i in group if frame_slot_count(i) == len(live_photos)]
        fits = [i for i in group if frame_slot_count(i) >= taken]
        current_frame_index = (same or fits or group or [0])[0]
    if current_capacity() != len(live_photos):
        resize_live_photos(current_capacity())
    _clear_photo_cache()
    print(f"Designs changed: {len(set(found) - set(old))} new, {len(set(old) - set(found))} gone, "
          f"{len(found)} now; using {design_id(frames[current_frame_index]) if frames else 'none'}")
    return True


def tick_designs():
    """Right away if a design went missing or broke; otherwise every so often while idle."""
    global _designs_next_scan
    now = time.monotonic()
    if not _designs_stale and (now < _designs_next_scan or not _booth_idle()):
        return
    _designs_next_scan = now + DESIGN_RESCAN_SECONDS
    if refresh_designs() and mode == "creation" and not menu_open and not gallery_open:
        save_preview()


def toggle_layout():
    """PHOTO STRIPS -> BIG SHEET landscape -> BIG SHEET portrait -> back. Photos already taken
    stay, as many as the new design has room for."""
    global current_frame_index
    kind = current_kind()
    _last_frame_of_kind[kind] = current_frame_index
    order = [k for k in LAYOUTS if indices_for_kind(k)]
    if len(order) < 2:
        flash_message("NO OTHER LAYOUTS", seconds=1.0)
        return
    target = order[(order.index(kind) + 1) % len(order)] if kind in order else order[0]
    group = indices_for_kind(target)
    last = _last_frame_of_kind.get(target)
    taken = sum(p is not None for p in live_photos)
    same = [i for i in group if frame_slot_count(i) == taken] if strip_is_full() else []
    if same:
        # All photos taken: a design for exactly that many, so it stays finished.
        current_frame_index = last if last in same else same[0]
    elif target == "strip":
        # Strips always come back as four photos.
        fours = [i for i in group if frame_slot_count(i) == 4] or group
        current_frame_index = last if last in fours else fours[0]
    else:
        fits = [i for i in group if frame_slot_count(i) >= taken] or group
        current_frame_index = last if last in fits else fits[0]
    resize_live_photos(current_capacity())
    _clear_photo_cache()
    print(f"Layout: {target} ({frames[current_frame_index].name})")
    save_preview()
    flash_message(LAYOUT_NAMES[target], seconds=0.8)


def toggle_strip_capacity():
    global current_frame_index, current_slot

    if not frames:
        print("No frame PNGs found in ~/photobooth/frames")
        return

    capacity = current_capacity()
    counts = sorted({frame_slot_count(i) for i in indices_for_kind()})
    if len(counts) < 2:
        flash_message("NO OTHER PHOTO COUNTS", seconds=1.0)
        return
    target = counts[(counts.index(capacity) + 1) % len(counts)] if capacity in counts else counts[0]
    group = indices_for_capacity(target)

    current_frame_index = group[0]
    resize_live_photos(target)  # photos past the new count are dropped
    _clear_photo_cache()

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


def is_sheet_file(path):
    try:
        with Image.open(path) as img:
            return is_sheet_size(img.size)
    except Exception:
        return False


def make_sheet_print(sheet_img):
    """A sheet filling the 4x6 print by itself (a landscape one turned upright)."""
    img = sheet_img.convert("RGB")
    if image_kind(img.size) == "sheet":
        img = img.rotate(90, expand=True)
    return img.resize((PRINT_W, PRINT_H), Image.LANCZOS)


def make_pair_print(left_img, right_img):
    """Two 2x6 strips side by side fill one 4x6 sheet (Canon SELPHY CP1500 postcard)."""
    print_img = Image.new("RGB", (PRINT_W, PRINT_H), "white")
    print_img.paste(left_img, (0, 0))
    print_img.paste(right_img, (STRIP_W, 0))
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

    names = [parts[1] for parts in (line.split() for line in result.stdout.splitlines())
             if len(parts) >= 2 and parts[0] == "printer"]
    if PRINTER_QUEUE in names:
        return PRINTER_QUEUE  # the one the app set up and watches (the dot on screen)
    for name in names:
        low = name.lower()
        if "selphy" in low or "cp1500" in low or "canon" in low:
            return name

    return None


def print_corners(size):
    """Where the design's corners go on a print of `size` (px; top-left, top-right, bottom-right,
    bottom-left): on the paper's measured edges (PRINT_TRIM_MM, PRINT_SLANT), PRINT_BLEED_MM
    beyond them."""
    w, h = size
    px_mm = w / (4 * 25.4)  # the print is 4 inches across
    W, H, b = w / px_mm, h / px_mm, PRINT_BLEED_MM
    t, s = PRINT_TRIM_MM, PRINT_SLANT
    # Each edge as a straight line, in mm: top/bottom y = p + q*x, left/right x = p + q*y.
    top = (t["top"] - b - s["top"] * W / 2, s["top"])
    bottom = (H - t["bottom"] + b + s["bottom"] * W / 2, -s["bottom"])
    left = (t["left"] - b - s["left"] * H / 2, s["left"])
    right = (W - t["right"] + b + s["right"] * H / 2, -s["right"])

    def meet(across, down):  # y = p1 + q1*x and x = p2 + q2*y
        (p1, q1), (p2, q2) = across, down
        y = (p1 + q1 * p2) / (1 - q1 * q2)
        return ((p2 + q2 * y) * px_mm, y * px_mm)

    return [meet(top, left), meet(top, right), meet(bottom, right), meet(bottom, left)]


def _perspective(src, dst):
    """Coefficients for Image.transform(PERSPECTIVE): maps each dst point (output) to src."""
    rows, rhs = [], []
    for (x, y), (u, v) in zip(dst, src):
        rows.append([x, y, 1, 0, 0, 0, -u * x, -u * y]); rhs.append(u)
        rows.append([0, 0, 0, x, y, 1, -v * x, -v * y]); rhs.append(v)
    return np.linalg.solve(np.array(rows, float), np.array(rhs, float)).tolist()


def fit_print(img):
    """The print, its corners moved to print_corners, so the design fills exactly the part of the
    paper that survives. Past the long sides (off the paper), the design's own edge pixels carry
    on, so a print that lands slightly off never shows white there. Past the two perforations
    it's left white: only the bleed crosses onto the tear-off tabs, not a band of colour."""
    img = img.convert("RGB")
    w, h = img.size
    pad = round(w / (4 * 25.4) * 12)  # more than any cut-off: what shows outside the design
    wide = np.pad(np.asarray(img), ((0, 0), (pad, pad), (0, 0)), mode="edge")
    padded = Image.fromarray(np.pad(wide, ((pad, pad), (0, 0), (0, 0)), constant_values=255))
    src = [(pad, pad), (pad + w, pad), (pad + w, pad + h), (pad, pad + h)]
    coeffs = _perspective(src, print_corners((w, h)))
    return padded.transform((w, h), Image.PERSPECTIVE, coeffs, Image.BICUBIC)


def _prepare_print_image(path):
    tmp_path = None
    try:
        canvas = fit_print(Image.open(path))
        fd, tmp_path = tempfile.mkstemp(prefix="print_", suffix=".jpg")
        os.close(fd)
        canvas.save(tmp_path, quality=95)
        return tmp_path, tmp_path
    except Exception as e:
        print(f"Could not prepare print image {path}: {e}")
        if tmp_path is not None:
            Path(tmp_path).unlink(missing_ok=True)
        return str(path), None


def send_to_printer(path):
    """Hands the print to CUPS. Returns its job id ("SELPHY-12"), or None if that failed.
    Whether it then really prints is watched by _printer_watch."""
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
        return None
    except Exception as e:
        print(f"Print failed: {e}")
        return None
    finally:
        if temp_path is not None:
            try:
                Path(temp_path).unlink()
            except OSError:
                pass

    if result.returncode != 0:
        print(f"Print failed (rc={result.returncode}): {result.stderr.strip()}")
        return None

    print(f"Print submitted: {result.stdout.strip()}")
    found = re.search(r"request id is (\S+)", result.stdout)
    return found.group(1) if found else "?"


_print_busy = threading.Event()  # building a print and handing it to CUPS (a few seconds)


def _build_and_send_print(paths):
    if is_sheet_file(paths[0]):
        try:
            sheet = make_sheet_print(Image.open(paths[0]))  # a sheet prints on its own
        except Exception as e:
            print(f"Could not open saved sheet: {e}")
            return None
        build = sheet
    else:
        if is_sheet_file(paths[1]):
            print("A sheet can't share a print with a strip.")
            return None
        strips = [load_strip_image(p) for p in paths]
        if any(strip is None for strip in strips):
            return None
        build = make_pair_print(*strips)

    fd, tmp = tempfile.mkstemp(prefix="print_", suffix=".jpg")
    os.close(fd)
    tmp_path = Path(tmp)
    try:
        build.save(tmp_path, quality=95)
        print(f"Built print: {' + '.join(Path(p).name for p in paths)} -> {tmp_path}")
        return send_to_printer(tmp_path)
    finally:
        try:
            tmp_path.unlink()
        except OSError:
            pass


def _print_worker(paths):
    # Runs off the UI thread; reports back via action_queue, never touches pygame.
    job = None
    try:
        job = _build_and_send_print(paths)
    except Exception as e:
        print(f"Print failed: {e}")
    finally:
        _print_busy.clear()
        action_queue.put(("print_done", (job, _print_key(*paths))))


# ---------------------------------------------------------------------------
# Printer over the booth's own WiFi (system/setup-printer.sh): the SELPHY joins the booth's network
# (uap0). A background thread spots it, adds it to CUPS by itself (AirPrint, no driver), follows
# each print until it has really come out, and tells the screen what's going on.
# ---------------------------------------------------------------------------

PRINTER_WIFI_IFACE = "uap0"
PRINTER_QUEUE = "SELPHY"
PRINTER_POLL_SECONDS = 5
PRINTER_GONE_POLLS = 2  # missed checks in a row before it counts as disconnected
PRINTER_TOAST_SECONDS = 3
PRINT_QUEUE_MAX = 3  # prints waiting at once
PRINT_STUCK_SECONDS = 300  # a print at the front this long, with no word from the printer: failed
HOTSPOT_STATUS_FILE = Path("/run/snapbox/hotspot-status")  # why there's no printer WiFi, if known

printer_connected = None  # True / False; None: not known yet, or this booth has no printer WiFi
printer_reason = None  # why not: "wifi_off", "5ghz", "hotspot_down", "queue", or None (printer off)
printer_alert = None  # what the printer says is wrong: "OUT OF PAPER", ...
printer_toast = None  # (text, ok, until): "PRINTER CONNECTED" etc. along the bottom
print_jobs = {}  # CUPS job id -> (which print, when sent): sent and not out of the printer yet

PRINTER_ALERTS = [  # (in the printer's own status words, what the screen says)
    ("media-empty", "OUT OF PAPER"), ("media-needed", "OUT OF PAPER"), ("input-tray", "CHECK THE PAPER TRAY"),
    ("media-jam", "PAPER JAM"), ("marker-supply-empty", "OUT OF INK"), ("marker-supply", "CHECK THE INK"),
    ("toner", "CHECK THE INK"), ("cover-open", "PRINTER COVER IS OPEN"), ("door-open", "PRINTER COVER IS OPEN"),
    ("media-", "CHECK THE PAPER"), ("other-error", "PRINTER NEEDS ATTENTION"),
]
PRINTER_REASON_TEXT = {
    "wifi_off": "WIFI IS OFF\nTurn WiFi on to print\n(settings > WIFI)",
    "5ghz": "CAN'T PRINT ON THIS WIFI\nIt is 5 GHz only: the printer\ncan't share it. Use another WiFi",
    "hotspot_down": "PRINTER WIFI IS DOWN\nSwitch the booth off and on",
    "queue": "PRINTER SETUP FAILED\nSwitch the booth off and on",
    None: "PRINTER NOT CONNECTED\nTurn the printer on and\nwait for the green dot",
}


def _run_quiet(cmd, timeout=10):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except Exception:
        return None


def _printer_wifi_stations():
    """MAC addresses of the devices on the printer WiFi; None if it isn't running."""
    result = _run_quiet(["iw", "dev", PRINTER_WIFI_IFACE, "station", "dump"], 5)
    if result is None or result.returncode != 0:
        return None
    return [line.split()[1] for line in result.stdout.splitlines() if line.startswith("Station ")]


def _no_printer_wifi_reason():
    """Why the printer network isn't up, on a booth that has one."""
    try:
        if HOTSPOT_STATUS_FILE.read_text().strip() == "5ghz":
            return "5ghz"
    except OSError:
        pass
    radio = _run_quiet(["nmcli", "radio", "wifi"], 5)
    if radio is not None and "disabled" in radio.stdout:
        return "wifi_off"
    return "hotspot_down"


def _find_selphy():
    """(address, resource) of a SELPHY offering AirPrint on the printer WiFi, or None."""
    result = _run_quiet(["avahi-browse", "-rptk", "_ipp._tcp"], 15)
    if result is None:
        return None
    for line in result.stdout.splitlines():
        # =;interface;protocol;name;type;domain;host;address;port;txt
        f = line.split(";")
        if len(f) < 10 or f[0] != "=" or f[1] != PRINTER_WIFI_IFACE or f[2] != "IPv4":
            continue
        if not re.search(r"selphy|cp1500|canon", f[3] + f[9], re.I):
            continue
        rp = re.search(r'"rp=([^"]*)"', f[9])
        return f[7], rp.group(1) if rp else "ipp/print"
    return None


def _printer_answers(address):
    try:
        with socket.create_connection((address, 631), timeout=2):
            return True
    except OSError:
        return False


def _ensure_printer_queue(address, resource):
    """Adds (or re-points) the SELPHY print queue; needs the lpadmin group, no sudo."""
    uri = f"ipp://{address}:631/{resource}"
    try:
        have = subprocess.run(["lpstat", "-v", PRINTER_QUEUE], capture_output=True, text=True,
                              timeout=10)
        if have.returncode != 0 or uri not in have.stdout:
            # "everywhere" asks the printer what it can do: no driver needed.
            result = subprocess.run(
                ["lpadmin", "-p", PRINTER_QUEUE, "-E", "-v", uri, "-m", "everywhere",
                 "-D", "Canon SELPHY CP1500", "-L", "Booth printer WiFi"],
                capture_output=True, text=True, timeout=90)
            if result.returncode != 0:
                print(f"Could not add the printer ({uri}): {result.stderr.strip()}")
                return False
            print(f"Printer added: {PRINTER_QUEUE} at {uri}")
        # A print that hits a problem waits and is tried again (paper added: it prints); the app
        # cancels it if that takes too long. CUPS's own default would stop the whole queue.
        subprocess.run(["lpadmin", "-p", PRINTER_QUEUE, "-o", "printer-error-policy=retry-current-job"],
                       capture_output=True, timeout=30)
        subprocess.run(["cupsenable", PRINTER_QUEUE], capture_output=True, timeout=10)
        subprocess.run(["cupsaccept", PRINTER_QUEUE], capture_output=True, timeout=10)
        return True
    except Exception as e:
        print(f"Could not add the printer: {e}")
        return False


def _queued_jobs():
    """Ids of the prints CUPS still holds for the printer, oldest first."""
    result = _run_quiet(["lpstat", "-o", PRINTER_QUEUE])
    if result is None or result.returncode != 0:
        return []
    ids = [line.split()[0] for line in result.stdout.splitlines() if line.strip()]
    return sorted(ids, key=lambda j: int(j.rsplit("-", 1)[-1]) if j.rsplit("-", 1)[-1].isdigit() else 0)


def _printer_alert_text():
    """What the printer says is wrong (paper, ink...), or None."""
    result = _run_quiet(["lpstat", "-l", "-p", PRINTER_QUEUE])
    if result is None:
        return None
    found = re.search(r"^\s*Alerts:\s*(.*)$", result.stdout, re.M)
    words = found.group(1).lower() if found else ""
    for key, text in PRINTER_ALERTS:
        if key in words:
            return text
    return None


def _cancel_prints(job=None):
    _run_quiet(["cancel", job] if job else ["cancel", "-a", PRINTER_QUEUE])


def _printer_watch():
    # Runs off the UI thread; reports changes via action_queue, never touches pygame.
    found = None  # (address, resource)
    queued = None  # the `found` the print queue was last set up for
    next_queue_try = 0.0
    reported = None
    missed = 0
    jobs_reported = None
    front, front_since = None, 0.0
    has_wifi = PRINTER_WIFI is not None
    # Prints left over from before (the booth was switched off mid-print, the printer went away)
    # must not come out by surprise later.
    for old in Path(tempfile.gettempdir()).glob("print_*.jpg"):
        old.unlink(missing_ok=True)
    if _queued_jobs():
        print("Cancelling prints left over from last time.")
        _cancel_prints()
    while True:
        try:
            stations = _printer_wifi_stations()
            reason = None
            if stations is None:
                # No printer network. On a booth that has one, that's a fault to show.
                now = False if has_wifi else None
                reason = _no_printer_wifi_reason() if has_wifi else None
            elif not stations:
                now = False
                if has_wifi and _no_printer_wifi_reason() == "5ghz":
                    reason = "5ghz"
            else:
                if found is None or not _printer_answers(found[0]):
                    found = _find_selphy()
                now = found is not None and _printer_answers(found[0])
                if now and queued != found:
                    if time.monotonic() >= next_queue_try and _ensure_printer_queue(*found):
                        queued = found
                    elif queued != found:
                        # Connected but can't be printed to: not a green dot.
                        next_queue_try = max(next_queue_try, time.monotonic() + 60)
                        now, reason = False, "queue"
            if now is False and reported and reported[0]:
                missed += 1
                if missed < PRINTER_GONE_POLLS:
                    now = True  # a missed check or two isn't a disconnect
            else:
                missed = 0
            if (now, reason) != reported:
                print("Printer: " + ("connected" if now else "no printer WiFi on this booth"
                                     if now is None else f"not connected ({reason or 'printer off'})"))
                reported = (now, reason)
                action_queue.put(("printer", reported))

            jobs = _queued_jobs() if now is not None else []
            alert = _printer_alert_text() if now else None
            if jobs and not now:
                # The printer is gone: a print that waits would come out at some random later time.
                print(f"Printer gone with {len(jobs)} print(s) waiting: cancelled.")
                _cancel_prints()
                action_queue.put(("print_cancelled", "PRINT CANCELLED\nThe printer disconnected"))
                jobs = []
            if jobs and jobs[0] != front:
                front, front_since = jobs[0], time.monotonic()
            elif not jobs:
                front = None
            if front and not alert and time.monotonic() - front_since > PRINT_STUCK_SECONDS:
                print(f"Print {front} never came out: cancelled.")
                _cancel_prints(front)
                action_queue.put(("print_cancelled", "PRINT FAILED\nCheck the printer"))
                jobs, front = jobs[1:], None
            if (jobs, alert) != jobs_reported:
                jobs_reported = (list(jobs), alert)
                action_queue.put(("printer_jobs", (list(jobs), alert)))
        except Exception as e:
            print(f"Printer check failed: {e}")
        time.sleep(PRINTER_POLL_SECONDS)


def _printer_toast(text, ok, seconds=PRINTER_TOAST_SECONDS):
    global printer_toast
    printer_toast = (text, ok, time.monotonic() + seconds)
    wake_screen(activity=False)
    if not should_show_live_preview():
        update_lcd()


def note_printer(state):
    """Main thread: the printer connected or went away."""
    global printer_connected, printer_reason, printer_toast, printer_alert
    connected, reason = state
    before = printer_connected
    printer_connected, printer_reason = connected, reason
    if not connected:
        printer_alert = None
    # At startup, only announce a printer that's there.
    if connected is None or (before is None and not connected) or before == connected:
        if not should_show_live_preview():
            update_lcd()
        return
    _printer_toast("PRINTER CONNECTED" if connected else "PRINTER DISCONNECTED", connected)


def note_print_jobs(state):
    """Main thread: which prints CUPS still holds, and what the printer says is wrong."""
    global printer_alert
    jobs, alert = state
    finished = [j for j, (_, sent) in print_jobs.items()
                if j not in jobs and time.monotonic() - sent > 8]  # not just too new to be listed
    for j in finished:
        del print_jobs[j]
    changed = alert != printer_alert
    printer_alert = alert
    if finished and not alert:
        left = len(print_jobs)
        _printer_toast("PRINT FINISHED" + (f"  \u00b7  {left} MORE TO GO" if left else ""), True)
    elif changed or finished:
        if alert:
            wake_screen(activity=False)
        if not should_show_live_preview():
            update_lcd()


def note_print_cancelled(text):
    print_jobs.clear()
    wake_screen()
    flash_message(text, seconds=2.5)


def note_print_sent(result):
    job, key = result
    if job is None:
        flash_message("PRINT FAILED", seconds=1.0)
        return
    print_jobs[job] = (key, time.monotonic())
    waiting = len(print_jobs)
    flash_message("PRINT SENT" if waiting <= 1 else f"PRINT SENT\n{waiting} PRINTS WAITING", seconds=1.0)


def tick_printer():
    global printer_toast
    if printer_toast is not None and time.monotonic() >= printer_toast[2]:
        printer_toast = None
        if not should_show_live_preview():
            update_lcd()


def _draw_printer_icon(draw, x, y, k, color):
    """A printer, 28k x 24k, top-left at (x, y)."""
    w = max(2, round(2 * k))
    draw.rectangle((x + 7 * k, y, x + 21 * k, y + 9 * k), outline=color, width=w)  # paper in
    _rrect(draw, (x, y + 7 * k, x + 28 * k, y + 19 * k), radius=3 * k, fill=color)
    draw.rectangle((x + 7 * k, y + 15 * k, x + 21 * k, y + 24 * k), fill=(0, 0, 0, 255),
                   outline=color, width=w)


def _draw_pill(draw, img, text, colour):
    font = _fit_font(draw, text, img.width - 80, 26)
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    pad, dot_d = 14, 18
    box_w = tw + dot_d + 3 * pad
    box_h = max(th, dot_d) + 2 * pad
    x0 = (img.width - box_w) // 2
    y0 = img.height - box_h - 14
    _rrect(draw, (x0, y0, x0 + box_w, y0 + box_h), radius=box_h // 2,
                           fill=(0, 0, 0, 210))
    cy = y0 + box_h // 2
    draw.ellipse((x0 + pad, cy - dot_d // 2, x0 + pad + dot_d, cy + dot_d // 2), fill=colour)
    draw.text((x0 + 2 * pad + dot_d - bbox[0], cy - th // 2 - bbox[1]), text, font=font,
              fill=(255, 255, 255, 255))


def _draw_printer_status(img, badge):
    """Top right (under the battery): the printer, with a dot: green ready, amber printing (with
    how many are waiting), red not connected or needing paper/ink. Along the bottom: what the
    printer needs for as long as it needs it, or a few seconds of news (PRINTER CONNECTED,
    PRINT FINISHED...)."""
    if printer_connected is None:
        return
    draw = ImageDraw.Draw(img, "RGBA")
    green, amber, red = (60, 210, 90, 255), (255, 180, 40, 255), (235, 60, 60, 255)
    printing = len(print_jobs) + (1 if _print_busy.is_set() else 0)
    if badge:
        k = 1.6
        w, h = round(40 * k), round(34 * k)
        right = img.width - 8
        top = 8 if battery_percent is None else 34
        _rrect(draw, (right - w, top, right, top + h), radius=round(8 * k),
                               fill=(0, 0, 0, 150))
        icon = (255, 255, 255, 235) if printer_connected else (150, 150, 150, 235)
        _draw_printer_icon(draw, right - w + 4 * k, top + 5 * k, k, icon)
        dot = red if not printer_connected or printer_alert else amber if printing else green
        d = round(14 * k)
        box = (right - d - 3, top + h - d - 3, right - 3, top + h - 3)
        draw.ellipse(box, fill=dot, outline=(0, 0, 0, 255), width=3)
        if printing and printer_connected and not printer_alert:
            draw.text(((box[0] + box[2]) / 2, (box[1] + box[3]) / 2), str(printing),
                      font=menu_font(14, True), fill=(0, 0, 0, 255), anchor="mm")
    if printer_alert:
        _draw_pill(draw, img, printer_alert, red)
    elif printer_toast is not None:
        _draw_pill(draw, img, printer_toast[0], green if printer_toast[1] else red)


def print_current_browsed_item():
    if browse_strips:
        start_print(browse_strips[browse_index])


def _print_key(path, other):
    return (str(path), str(other))


def start_print(path, other=None):
    """Prints one 4x6 sheet: the strip twice, or with `other` beside it. True if it's on its way."""
    if _print_busy.is_set():
        print("Print already in progress; ignoring.")
        flash_message("ALREADY PRINTING", seconds=0.8)
        return False

    if printer_connected is False:
        flash_message(PRINTER_REASON_TEXT.get(printer_reason, PRINTER_REASON_TEXT[None]), seconds=2.5)
        return False

    if printer_alert:
        flash_message(f"{printer_alert}\nFix that first, then print", seconds=2.0)
        return False

    # A sheet takes about a minute: the same one again before it's out is an impatient tap.
    key = _print_key(path, other or path)
    if any(k == key for k, _ in print_jobs.values()):
        flash_message("ALREADY PRINTING THIS ONE\nIt takes about a minute", seconds=1.5)
        return False
    if len(print_jobs) >= PRINT_QUEUE_MAX:
        flash_message(f"{len(print_jobs)} PRINTS WAITING\nLet the printer catch up", seconds=1.5)
        return False

    _print_busy.set()
    threading.Thread(target=_print_worker, args=((path, other or path),), daemon=True).start()
    flash_message("PRINTING...", seconds=0.6)
    return True


# ---------------------------------------------------------------------------
# Photos from a phone. A phone on the booth's own WiFi (the printer network) opens
# http://10.42.0.1:8080, picks a design, drops its photos into the openings (drag and pinch to
# line them up) and sends them. The booth builds the strip or sheet exactly like one it took
# itself: saved with the others (REVIEW shows it, CHANGE FRAME works) and printed through the same
# fitting. Only reachable from the booth's own network, which has a password.
# The page is web/index.html. Web threads only read designs and queue work; the main loop builds
# and saves (web_make_strip), like everything else.
# ---------------------------------------------------------------------------

WEB_DIR = BASE / "web"
WEB_MAX_BYTES = 48 * 1024 * 1024
WEB_NEUTRAL_FX = {"seed": 0, "opts": [], "stamp": "", "bw": False}  # phone photos: as they are
_web_images = {}  # (design id, mtime, size) -> image bytes


def _web_designs():
    out = []
    kinds = dict(_frame_kinds)
    for path in list(frames):
        kind = kinds.get(path, "strip")
        slots, _ = read_design_slots(path, kind)
        if not slots:
            continue
        w, h = {"sheet": (SHEET_W, SHEET_H), "psheet": (PSHEET_W, PSHEET_H)}.get(kind, (STRIP_W, STRIP_H))
        out.append({"id": design_id(path), "name": path.stem, "kind": kind, "w": w, "h": h,
                    "slots": slots})
    return out


def _web_design_image(ident, size):
    """The design as a PNG, see-through where the photos go, at most `size` px on its long side."""
    path = next((f for f in list(frames) if design_id(f) == ident), None)
    if path is None:
        return None
    key = (ident, _mtime(path), size)
    if key not in _web_images:
        if len(_web_images) > 400:
            _web_images.clear()
        with Image.open(path) as img:
            img = img.convert("RGBA")
            img.thumbnail((size, size), Image.BILINEAR)
            buf = io.BytesIO()
            img.save(buf, format="PNG", optimize=False)
        _web_images[key] = buf.getvalue()
    return _web_images[key]


def web_make_strip(job):
    """Main thread: builds and saves what a phone sent; prints it if asked. Fills job["result"]."""
    try:
        index = next((i for i, f in enumerate(frames) if design_id(f) == job["design"]), None)
        if index is None:
            raise ValueError("That design isn't on the booth any more. Pick another.")
        photos = (job["photos"] + [None] * 8)[:frame_slot_count(index)]
        if not any(p is not None for p in photos):
            raise ValueError("No photos arrived.")
        stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        path = ARCHIVE_DIR / f"strip_{stamp}.jpg"
        n = 1
        while path.exists():
            n += 1
            path = ARCHIVE_DIR / f"strip_{stamp}_{n}.jpg"
        strip = compose_single_strip(photos, index, fx=WEB_NEUTRAL_FX)
        _forget_slot_cache(photos)
        save_strip_photos(path, photos)
        meta = strip_meta(frame_slots(index)[:len(photos)], index, WEB_NEUTRAL_FX)
        write_file_durably(path, lambda f: strip.convert("RGB").save(
            f, format="JPEG", quality=95, comment=meta))
        print(f"Saved a strip sent from a phone: {path.name} ({frames[index].name})")
        note_activity()
        message = "Saved on the booth. Find it in REVIEW."
        if job.get("print"):
            if start_print(path):
                message = "Saved, and printing now (about a minute)."
            elif printer_connected is False:
                message = "Saved on the booth, but the printer isn't connected. Print it from REVIEW later."
            else:
                message = "Saved on the booth, but it couldn't print right now. Print it from REVIEW."
        else:
            flash_message("PHOTOS FROM A PHONE\nSAVED", seconds=1.0)
        job["result"] = {"ok": True, "message": message}
    except OSError as e:
        print(f"Could not save the phone's strip: {e}")
        job["result"] = {"ok": False, "message": "The booth couldn't save it (storage full?)."}
    except Exception as e:
        print(f"Could not build the phone's strip: {e}")
        job["result"] = {"ok": False, "message": str(e) if isinstance(e, ValueError)
                         else "The booth couldn't build that one."}
    finally:
        job["done"].set()


class _WebHandler(http.server.BaseHTTPRequestHandler):
    server_version = "snapbox"
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):
        pass  # the journal is on the SD card

    def _send(self, code, body, ctype, cache=False):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "max-age=600" if cache else "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code, data):
        self._send(code, json.dumps(data).encode(), "application/json")

    def do_GET(self):
        url = urllib.parse.urlparse(self.path)
        query = urllib.parse.parse_qs(url.query)
        try:
            if url.path in ("/", "/index.html"):
                self._send(200, (WEB_DIR / "index.html").read_bytes(), "text/html; charset=utf-8")
            elif url.path == "/api/designs":
                self._json(200, {"designs": _web_designs(), "layouts": LAYOUT_NAMES})
            elif url.path == "/api/status":
                self._json(200, {"printer": bool(printer_connected), "alert": printer_alert,
                                 "waiting": len(print_jobs)})
            elif url.path == "/design.png":
                size = 900 if query.get("big") else 260
                body = _web_design_image((query.get("id") or [""])[0], size)
                if body is None:
                    self._send(404, b"gone", "text/plain")
                else:
                    self._send(200, body, "image/png", cache=True)
            else:
                # Phones probe for internet on a new WiFi; anything else gets the page.
                self.send_response(302)
                self.send_header("Location", "/")
                self.send_header("Content-Length", "0")
                self.end_headers()
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as e:
            print(f"Phone page error ({url.path}): {e}")
            try:
                self._send(500, b"error", "text/plain")
            except OSError:
                pass

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length") or 0)
            if self.path != "/api/make" or not 0 < length <= WEB_MAX_BYTES:
                self._json(400, {"ok": False, "message": "Too big, or not understood."})
                return
            data = json.loads(self.rfile.read(length))
            photos = []
            for item in data.get("photos", [])[:8]:
                if not item:
                    photos.append(None)
                    continue
                raw = base64.b64decode(item.split(",", 1)[-1])
                img = Image.open(io.BytesIO(raw))
                img = ImageOps.exif_transpose(img).convert("RGB")
                img.thumbnail((2400, 2400), Image.LANCZOS)
                photos.append(img)
            job = {"design": str(data.get("design", "")), "photos": photos,
                   "print": bool(data.get("print")), "done": threading.Event(), "result": None}
            action_queue.put(("web_strip", job))
            if not job["done"].wait(60):
                self._json(503, {"ok": False, "message": "The booth is busy. Try again in a moment."})
                return
            self._json(200 if job["result"]["ok"] else 400, job["result"])
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as e:
            print(f"Phone upload failed: {e}")
            try:
                self._json(400, {"ok": False, "message": "The booth couldn't read those photos."})
            except OSError:
                pass


class _WebServer(http.server.ThreadingHTTPServer):
    daemon_threads = True

    def handle_error(self, request, client_address):
        # A phone dropping its connection is normal; don't fill the journal with tracebacks.
        if not isinstance(sys.exc_info()[1], (ConnectionError, TimeoutError)):
            print(f"Phone page error from {client_address[0]}: {sys.exc_info()[1]}")


def _web_serve(addr=None):
    """Serves the phone page on the booth's own network, whenever that network is up."""
    while True:
        try:
            server = _WebServer((addr or WEB_ADDR, WEB_PORT), _WebHandler)
            print(f"Phone page: http://{addr or WEB_ADDR}:{WEB_PORT}")
            server.serve_forever()
        except OSError:
            pass  # the printer network isn't up (yet)
        except Exception as e:
            print(f"Phone page stopped: {e}")
        time.sleep(15)


def shutdown_pi(message="Shutting down..."):
    print("Shutting down Pi safely...")
    wake_screen(camera=False)

    if lcd is not None:
        try:
            screen_w, screen_h = lcd.get_size()

            img = Image.new("RGB", ui_size(), "black")
            _draw_centered_banner(img, message)
            img = img.rotate(panel_rotation(), expand=True)

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

    try:
        result = subprocess.run(["sudo", "-n", "shutdown", "now"], capture_output=True, text=True,
                                timeout=30)
        failed = result.returncode != 0 and (result.stderr.strip() or f"rc={result.returncode}")
    except Exception as e:
        failed = str(e)
    if failed:
        print(f"Shutdown failed: {failed}")
        flash_message("COULDN'T SHUT DOWN", seconds=2.0)


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


AUTO_OFF_WARNING_SECONDS = 60
auto_off_banner = None  # shown over every screen during the last minute


def tick_auto_off():
    """Shuts down after the chosen idle time (BOOTH tab), with a minute's warning on screen."""
    global auto_off_banner
    limit = settings["auto_off"]
    if _print_busy.is_set() or print_jobs or update_state == "installing" or wifi_connecting:
        note_activity()  # busy isn't idle
    idle = time.monotonic() - last_activity
    if limit is None or idle < limit - AUTO_OFF_WARNING_SECONDS:
        if auto_off_banner is not None:
            auto_off_banner = None
            update_lcd()
        return
    if idle >= limit:
        print(f"Idle for {limit // 60} min: shutting down automatically.")
        auto_off_banner = None
        save_partial_strip_before_shutdown()
        # If the shutdown doesn't happen, try again after another full idle period.
        note_activity()
        shutdown_pi("Idle for a while:\nshutting down...")
        return
    text = f"SHUTTING DOWN IN {math.ceil(limit - idle)}s\nTap or press to keep it on"
    if screen_asleep:
        wake_screen(activity=False)
    if text != auto_off_banner:
        auto_off_banner = text
        if not should_show_live_preview():
            update_lcd()


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

SHUTDOWN_CONFIRM_SECONDS = 4

_fonts = {}


def menu_font(size, bold=False, plain=False):
    """`plain`: the original font whatever the look (it has the arrow shapes the others lack)."""
    lk = settings.get("look", "original")
    if plain or looks is None or lk not in looks.LOOKS:
        lk = "original"
    key = (size, bold, lk)
    if key not in _fonts:
        try:
            if lk != "original":
                name, weight, factor = looks.menu_font_file(lk, bold)
                font = ImageFont.truetype(str(looks.FONT_DIR / name), max(8, round(size * factor)))
                if weight:
                    font.set_variation_by_axes([weight])
                _fonts[key] = font
            else:
                name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
                _fonts[key] = ImageFont.truetype(f"/usr/share/fonts/truetype/dejavu/{name}", size)
        except Exception:
            _fonts[key] = ImageFont.load_default(size=size)
    return _fonts[key]


def _draw_text_centered(draw, box, text, font, fill):
    x0, y0, x1, y1 = box
    bbox = draw.textbbox((0, 0), text, font=font)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text((x0 + (x1 - x0 - w) // 2 - bbox[0], y0 + (y1 - y0 - h) // 2 - bbox[1]),
              text, font=font, fill=fill)


def _fit_font(draw, text, max_w, size, bold=True):
    plain = any(ch in text for ch in "\u25c0\u25b6\u25b2\u25bc")
    while size > 10:
        font = menu_font(size, bold, plain)
        bbox = draw.textbbox((0, 0), text, font=font)
        if bbox[2] - bbox[0] <= max_w:
            return font
        size -= 1
    return menu_font(size, bold, plain)


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


# Round buttons down the left of the main screen, big enough to hit on a small panel. In
# portrait they sit in the black margin beside the strip.
ICON_SIZE = 92
ICON_GAP = 30
ICON_MARGIN = 7


def corner_buttons():
    """[(kind, (x0, y0, x1, y1))] in UI coordinates: settings, review, then quick effects (or in
    browse mode the camera)."""
    kinds = ["menu", "gallery"] + (["camera"] if mode == "browse" else ["fx", "layout"])
    if look() != "original":
        rail = looks.geometry(look(), *ui_size())["rail"]
        return [(kind, tuple(round(v) for v in rail[i])) for i, kind in enumerate(kinds)]
    buttons = []
    for i, kind in enumerate(kinds):
        top = ICON_MARGIN + i * (ICON_SIZE + ICON_GAP)
        buttons.append((kind, (ICON_MARGIN, top, ICON_MARGIN + ICON_SIZE, top + ICON_SIZE)))
    return buttons


def _draw_photos_icon(draw, cx, cy, k, color):
    # Two stacked photos, the front one with a mountain and a sun (k: scale from a 44 px button).
    w = max(2, round(2 * k))
    _rrect(draw, (cx - 9 * k, cy - 12 * k, cx + 13 * k, cy + 6 * k), radius=2 * k,
                           outline=color, width=w)
    _rrect(draw, (cx - 13 * k, cy - 7 * k, cx + 9 * k, cy + 11 * k), radius=2 * k,
                           fill=(0, 0, 0, 255), outline=color, width=w)
    draw.polygon([(cx - 10 * k, cy + 9 * k), (cx - 4 * k, cy + 1 * k), (cx + 1 * k, cy + 6 * k),
                  (cx + 3 * k, cy + 4 * k), (cx + 7 * k, cy + 9 * k)], fill=color)
    draw.ellipse((cx + 1 * k, cy - 4 * k, cx + 5 * k, cy), fill=color)


def _draw_camera_icon(draw, cx, cy, k, color):
    _rrect(draw, (cx - 6 * k, cy - 13 * k, cx + 6 * k, cy - 6 * k), radius=2 * k,
                           fill=color)
    _rrect(draw, (cx - 15 * k, cy - 9 * k, cx + 15 * k, cy + 12 * k), radius=4 * k,
                           fill=color)
    draw.ellipse((cx - 8 * k, cy - 6 * k, cx + 8 * k, cy + 10 * k), fill=(0, 0, 0, 255))
    draw.ellipse((cx - 5 * k, cy - 3 * k, cx + 5 * k, cy + 7 * k), fill=color)


def _draw_sparkle_icon(draw, cx, cy, k, color):
    # A big four-point sparkle and a small one: the quick EFFECTS button.
    def star(x, y, r):
        t = r * 0.28
        draw.polygon([(x, y - r), (x + t, y - t), (x + r, y), (x + t, y + t), (x, y + r),
                      (x - t, y + t), (x - r, y), (x - t, y - t)], fill=color)
    star(cx - 3 * k, cy + 2 * k, 13 * k)
    star(cx + 10 * k, cy - 10 * k, 6 * k)


def _draw_layout_icon(draw, cx, cy, k, color, kind):
    # A skinny strip, a wide sheet and a tall sheet; the one in use is filled.
    boxes = {"strip": (cx - 18 * k, cy - 13 * k, cx - 12 * k, cy + 13 * k),
             "sheet": (cx - 8 * k, cy - 6 * k, cx + 8 * k, cy + 5 * k),
             "psheet": (cx + 12 * k, cy - 10 * k, cx + 19 * k, cy + 10 * k)}
    w = max(2, round(1.6 * k))
    for name, box in boxes.items():
        draw.rectangle(box, fill=color if name == kind else None, outline=color, width=w)


_look_cache = {}  # "chrome": (key, picture); "count": (key, picture)
_look_slow = {"t": 0.0, "saved": 0, "wifi": False}


def _look_state():
    """What the MODERN / CLASSIC main screen shows right now, as plain values (looks.py draws it)."""
    now = time.monotonic()
    if now - _look_slow["t"] > 10:  # things that change rarely and cost a little to look up
        _look_slow["t"] = now
        try:
            _look_slow["saved"] = sum(1 for _ in ARCHIVE_DIR.glob("*.jpg"))
        except OSError:
            pass
        try:
            _look_slow["wifi"] = Path(f"/sys/class/net/{WIFI_IFACE}/operstate").read_text().strip() == "up"
        except OSError:
            _look_slow["wifi"] = False
    kind = current_kind()
    cap = max(1, current_capacity())
    group = indices_for_kind(kind)
    pos = group.index(current_frame_index) + 1 if current_frame_index in group else 1
    browsing = mode == "browse" and bool(browse_strips)
    reviewing = in_review() and review_started is not None
    st = {"kinds": [k for k, _ in corner_buttons()], "effects_on": effects_on(),
          "saved": _look_slow["saved"], "wifi": _look_slow["wifi"],
          "battery": None if battery_percent is None else round(battery_percent),
          "design": pos, "designs": len(group), "layout": "strip" if kind == "strip" else "sheet",
          "phone": bool(PRINTER_WIFI), "strip_rects": list(_main_layout_rects),
          "date": tuple(datetime.now().strftime("%m %d %y").split())}
    if browsing:
        when = datetime.fromtimestamp(browse_strips[browse_index].stat().st_mtime)
        st.update(title=when.strftime("%b %-d · %-I:%M %p"), chip="saved print",
                  switch_text=f"{browse_index + 1} of {len(browse_strips)} · swipe",
                  design=browse_index + 1, designs=len(browse_strips),
                  count_label="SAVED", count=browse_index + 1, count_of=len(browse_strips),
                  count_side="", segments=[], cta=["1 press older · 2 newer", "3 presses print it"],
                  cta_narrow=["1 older", "2 newer", "3 print"],
                  tape="1 OLDER · 2 NEWER · 3 PRINT", tape_narrow="3 = PRINT",
                  plate_text=f"SAVED · {browse_index + 1} OF {len(browse_strips)}")
    else:
        taken = sum(p is not None for p in live_photos)
        n = min(current_slot + 1, cap)
        name = re.sub(r"(?<=[A-Za-z])(?=\d)", " ", frames[current_frame_index].stem).title() if frames else "No designs"
        shape = {"strip": "2x6 strip", "sheet": "6x4 sheet", "psheet": "4x6 sheet"}[kind]
        st.update(title=name, chip=f"{shape} · {cap} photo{'s' if cap != 1 else ''}",
                  switch_text=f"{pos} of {len(group)} · swipe to change",
                  count_label="PHOTO", count=n, count_of=cap,
                  count_side="all taken" if taken >= cap else f"{cap - taken} left",
                  segments=["done" if i < current_slot else "now" if i == current_slot else "todo"
                            for i in range(cap)],
                  plate_text=f"No. {pos} · {'STRIP' if kind == 'strip' else 'SHEET'} OF {cap}")
        if reviewing:
            left = review_seconds_left()
            st.update(cta=["1 press keeps it", "2 retake · 3 new frame"], cta_seconds=left,
                      cta_narrow=["1 keep", "2 retake", "3 frame"],
                      cta_frac=left / max(1, settings["review"]),
                      tape=f"1 KEEP · 2 RETAKE · {left}s", tape_narrow=f"KEEP? {left}s")
        else:
            st.update(cta=["Press the big button", f"for photo {n}"],
                      cta_narrow=["Press", "the big", "button"], tape="", tape_narrow="")
    if printer_connected is None:
        st["printer"] = None
    elif printer_alert:
        st.update(printer="alert", printer_title=printer_alert.capitalize(), printer_sub="Fix it to print")
    elif not printer_connected:
        st.update(printer="off", printer_title="Printer off", printer_sub="Tap for help")
    elif print_jobs or _print_busy.is_set():
        n = len(print_jobs)
        st.update(printer="printing", printer_title="Printing",
                  printer_sub="1 on its way" if n <= 1 else f"{n} waiting")
    else:
        st.update(printer="ready", printer_title="Printer ready", printer_sub="Nothing waiting")
    return st


def _look_chrome():
    """The picture of everything around the strip, redrawn only when something on it changes."""
    st = _look_state()
    key = (look(), ui_size(), json.dumps(st, sort_keys=True, default=str))
    if _look_cache.get("chrome", (None,))[0] != key:
        picture, geo = looks.render_main(look(), *ui_size(), st)
        _look_cache["chrome"] = (key, picture)
        _look_cache["status"] = geo.get("status")
    return _look_cache["chrome"][1]


def _look_countdown(size):
    cap = max(1, current_capacity())
    total = max(1, settings["countdown"] or 1)
    key = (look(), size, countdown_value, current_slot, cap, total)
    if _look_cache.get("count", (None,))[0] != key:
        _look_cache["count"] = (key, looks.render_countdown(
            look(), size[0], size[1], countdown_value, min(current_slot + 1, cap), cap,
            countdown_value / total))
    return _look_cache["count"][1]


def _draw_corner_buttons(img):
    if lcd is None:
        return
    draw = ImageDraw.Draw(img, "RGBA")
    white = (255, 255, 255, 230)
    for kind, (x0, y0, x1, y1) in corner_buttons():
        # The camera (back to taking photos) stands out in green.
        if kind == "camera":
            fill = MENU_DONE + (230,)
        else:  # CLASSIC keeps its see-through black; the others use the theme's own colour
            fill = (0, 0, 0, 150) if settings["theme"] == "classic" else MENU_DISC + (235,)
        draw.ellipse((x0, y0, x1, y1), fill=fill)
        cx, cy, k = (x0 + x1) / 2, (y0 + y1) / 2, ICON_SIZE / 44
        if kind == "menu":
            _draw_gear(draw, cx, cy, ICON_SIZE * 0.36, white, (0, 0, 0, 255))
        elif kind == "gallery":
            _draw_photos_icon(draw, cx, cy, k, white)
        elif kind == "layout":
            _draw_layout_icon(draw, cx, cy, k, white, current_kind())
        elif kind == "fx":
            # Gold while any effect is on, so you can see at a glance.
            _draw_sparkle_icon(draw, cx, cy, k, ((255, 200, 60, 255) if settings["theme"] == "classic" else (255, 240, 120, 255))
                               if effects_on() else white)
        else:
            _draw_camera_icon(draw, cx, cy, k, white)


menu_open = False
menu_tab = "camera"
PREVIEW_TABS = {"camera": CAMERA_SETTINGS, "effects": EFFECT_SETTINGS}
menu_fullscreen = False  # CAMERA / EFFECTS: live preview as big as possible, one setting below
menu_quick = False  # opened from the main screen's sparkle button: DONE goes straight back
menu_focus = {"camera": "brightness", "effects": "stamp"}  # setting shown under the big preview
menu_buttons = []  # [((x0, y0, x1, y1) in UI coords, callback)]
_menu_last_cam = None
_menu_last_ts = 0.0
_shutdown_confirm_until = 0.0
_lcd_xform = None  # (x, y, scale) of the last frame drawn on the panel


def open_menu():
    global menu_open, menu_tab, _menu_last_cam, menu_fullscreen, menu_quick
    print("Settings menu opened.")
    menu_open = True
    menu_tab = "camera"
    menu_fullscreen = False
    menu_quick = False
    _menu_last_cam = None
    update_menu(force=True)


def open_quick_effects():
    """Sparkle button: the effects over a big live preview, one tap from taking photos."""
    global menu_open, menu_tab, _menu_last_cam, menu_fullscreen, menu_quick
    print("Quick effects opened.")
    menu_open, menu_tab, menu_fullscreen, menu_quick = True, "effects", True, True
    _menu_last_cam = None
    update_menu(force=True)


def close_menu(redraw=True):
    global menu_open, menu_fullscreen, date_entry
    if not menu_open:
        return
    print("Settings menu closed.")
    menu_open = False
    menu_fullscreen = False
    date_entry = None
    _invalidate_live_preview()
    if redraw:
        update_lcd()


def set_menu_tab(tab):
    global menu_tab, wifi_view, menu_fullscreen, date_entry
    date_entry = None
    if tab == "wifi" and menu_tab != "wifi":
        wifi_view = "list"
        wifi_scan()
    menu_tab = tab
    menu_fullscreen = False


def set_menu_fullscreen(on):
    global menu_fullscreen
    menu_fullscreen = on


def set_menu_focus(key):
    menu_focus[menu_tab] = key


def menu_focus_step(step):
    """Swipe on the full-screen preview: the next or previous setting."""
    keys = [k for k, _, _, _ in PREVIEW_TABS[menu_tab]]
    i = keys.index(menu_focus[menu_tab]) if menu_focus[menu_tab] in keys else 0
    menu_focus[menu_tab] = keys[(i + step) % len(keys)]


def step_setting(key, step):
    for tab, defs in PREVIEW_TABS.items():
        if key in {k for k, _, _, _ in defs}:
            menu_focus[tab] = key  # the full-screen preview opens on the last one changed
    if key in FX_STYLES and settings["random"]:
        set_setting("random", 0)  # choosing a style by hand turns RANDOM off
    # Round and round: right from the last choice goes back to the first (usually OFF).
    choices = [v for v, _ in SETTING_DEFS[key][1]]
    i = (choices.index(settings[key]) + step) % len(choices)
    if key == "stamp" and choices[i] == "custom":
        open_date_keypad()  # MY DATE is switched on by SAVE, once there is a date
    else:
        set_setting(key, choices[i])


def _long_date(day):
    return day.strftime("%b %d %Y").upper()  # OCT 25 2026


def setting_text(key):
    """What a setting row shows: its choice, or for some, what that choice means right now."""
    label = SETTING_DEFS[key][1][[v for v, _ in SETTING_DEFS[key][1]].index(settings[key])][1]
    if key == "stamp" and settings["stamp"]:
        return f"{'MY DATE' if settings['stamp'] == 'custom' else 'TODAY'}: {_long_date(stamp_date())}"
    if key in FX_STYLES and settings["random"]:
        pick = random_pick(_preview_slot_index())[0]
        return FX_STYLES[key][pick[key] - 1][0] if key in pick else "NONE THIS PHOTO"
    return label


def setting_title(key):
    """A setting row's name, with a hint when tapping the row does something."""
    title = SETTING_DEFS[key][0]
    if key == "stamp" and settings["stamp"]:
        return f"{title}  \u00b7  TAP TO SET DATE"
    if key == "random" and settings["random"]:
        return "RANDOM  \u00b7  TAP TO SHUFFLE"
    if key in FX_STYLES and settings["random"]:
        pick, soft = random_pick(_preview_slot_index())
        return f"{title}  \u00b7  RANDOM{', SUBTLE' if key in pick and soft < 1 else ''}"
    return title


# Tapping the middle of these setting rows (between the arrows) does something extra.
ROW_TAPS = {"stamp": lambda: open_date_keypad(), "random": lambda: reroll_random()}


# ---------------------------------------------------------------------------
# Number pad for the date stamp's MY DATE: type MM DD YY.
# ---------------------------------------------------------------------------

date_entry = None  # digits typed so far, or None when the number pad is closed


def open_date_keypad():
    global date_entry
    date_entry = ""


def date_keypad_type(ch):
    global date_entry
    if date_entry is not None and len(date_entry) < 6:
        date_entry += ch


def date_keypad_backspace():
    global date_entry
    if date_entry:
        date_entry = date_entry[:-1]


def date_keypad_clear():
    global date_entry
    if date_entry is not None:
        date_entry = ""


def date_keypad_cancel():
    global date_entry
    date_entry = None


def _typed_date():
    """The typed MM DD YY as a datetime, or None if incomplete or not a real day."""
    if date_entry is None or len(date_entry) != 6:
        return None
    try:
        return datetime(2000 + int(date_entry[4:]), int(date_entry[:2]), int(date_entry[2:4]))
    except ValueError:
        return None


def date_keypad_save():
    global date_entry
    day = _typed_date()
    if day is None:
        return
    settings["stamp_date"] = day.strftime("%Y-%m-%d")
    date_entry = None
    set_setting("stamp", "custom")  # saves stamp_date too


def _render_date_keypad(draw, area, buttons):
    """Full screen: CANCEL, the date being typed, SAVE; then a big 0-9 pad."""
    x0, y0, x1, y1 = area
    w = x1 - x0
    gap = 6

    top_h = 40
    hint = f"TYPE THE DATE: MONTH, DAY, YEAR  \u00b7  THE CLOCK SAYS {_long_date(datetime.now())}"
    _draw_text_centered(draw, (x0, y0, x1, y0 + top_h), hint, _fit_font(draw, hint, w, 17, False), MENU_DIM)
    y = y0 + top_h + gap

    row_h = 72
    cancel = (x0, y, x0 + int(w * 0.22), y + row_h)
    save = (x1 - int(w * 0.22), y, x1, y + row_h)
    field = (cancel[2] + gap, y, save[0] - gap, y + row_h)
    _draw_key(draw, cancel, "CANCEL", buttons, date_keypad_cancel, fill=MENU_KEY, size=20)
    day = _typed_date()
    full = len(date_entry) == 6
    _draw_key(draw, save, "SAVE" if day else "NOT A DATE" if full else "SAVE", buttons,
              date_keypad_save if day else (lambda: None),
              fill=MENU_DONE if day else (90, 40, 40) if full else (50, 50, 58),
              text_fill=MENU_TEXT if day or full else (110, 110, 118), size=22 if day or not full else 15)
    _rrect(draw, field, radius=8, fill=MENU_FIELD)
    draw.rounded_rectangle(field, radius=8, outline=MENU_ACCENT, width=2)
    digits = date_entry.ljust(6, "_")
    shown = f"{digits[:2]} / {digits[2:4]} / {digits[4:]}"
    _draw_text_centered(draw, field, shown, _fit_font(draw, "MM / DD / YY", field[2] - field[0] - 16, 34),
                        MENU_TEXT if day or not full else MENU_BAD)
    y += row_h + gap

    key_h = (y1 - y - 3 * gap) // 4
    key_w = (w - 2 * gap) / 3
    keys = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "CLEAR", "0", "\u232b"]
    for n, label in enumerate(keys):
        col, row = n % 3, n // 3
        left = x0 + col * (key_w + gap)
        box = (int(left), y + row * (key_h + gap), int(left + key_w), y + row * (key_h + gap) + key_h)
        if label == "CLEAR":
            _draw_key(draw, box, label, buttons, date_keypad_clear, fill=MENU_KEY, size=20)
        elif label == "\u232b":
            _draw_key(draw, box, label, buttons, date_keypad_backspace, fill=MENU_KEY, size=32)
        else:
            _draw_key(draw, box, label, buttons, lambda ch=label: date_keypad_type(ch), size=34)


def press_shutdown():
    global _shutdown_confirm_until
    if time.monotonic() < _shutdown_confirm_until:
        close_menu(redraw=False)
        shutdown_pi()
    else:
        _shutdown_confirm_until = time.monotonic() + SHUTDOWN_CONFIRM_SECONDS


def _draw_setting_row(draw, box, key, buttons):
    x0, y0, x1, y1 = box
    text = setting_text(key)
    h = y1 - y0
    arrow_w = min(72, h + 12, (x1 - x0) // 5)

    _rrect(draw, box, radius=10, fill=MENU_ROW)
    for direction, ax0 in ((-1, x0), (1, x1 - arrow_w)):
        abox = (ax0, y0, ax0 + arrow_w, y1)
        color = MENU_ACCENT
        cx, cy, t = (abox[0] + abox[2]) / 2, (y0 + y1) / 2, min(14, h * 0.25)
        if direction < 0:
            pts = [(cx + t * 0.7, cy - t), (cx + t * 0.7, cy + t), (cx - t * 0.9, cy)]
        else:
            pts = [(cx - t * 0.7, cy - t), (cx - t * 0.7, cy + t), (cx + t * 0.9, cy)]
        draw.polygon(pts, fill=color)
        buttons.append((abox, lambda k=key, d=direction: step_setting(k, d)))

    mid = (x0 + arrow_w, y0, x1 - arrow_w, y1)
    if key in ROW_TAPS:
        buttons.append((mid, ROW_TAPS[key]))
    max_w = mid[2] - mid[0] - 8
    label = setting_title(key)
    label_font = _fit_font(draw, label, max_w, 13 if h < 64 else 15, bold=False)
    value_font = _fit_font(draw, text, max_w, 20 if h < 64 else 22)
    split = y0 + int(h * 0.42)
    _draw_text_centered(draw, (mid[0], y0 + 2, mid[2], split), label, label_font, MENU_DIM)
    _draw_text_centered(draw, (mid[0], split, mid[2], y1 - 4), text, value_font, MENU_TEXT)


MIN_ROW_H = 76  # ~7 mm on the 2.8" panel: easy to hit with a finger
menu_pages = {}  # page shown per list of rows, e.g. {"camera": 1}


def menu_page_step(page_id, step, pages):
    menu_pages[page_id] = max(0, min(pages - 1, menu_pages.get(page_id, 0) + step))


def _draw_pager(draw, box, page, pages, on_step, buttons):
    """PREV / page x of y / NEXT along the bottom of a list."""
    x0, y0, x1, y1 = box
    gap = 6
    half = (x1 - x0 - gap) * 2 // 5
    dim = MENU_INSET
    _draw_key(draw, (x0, y0, x0 + half, y1), "\u25c0 PREV", buttons, lambda: on_step(-1),
              fill=MENU_ROW if page > 0 else dim,
              text_fill=MENU_TEXT if page > 0 else (90, 90, 98), size=20)
    _draw_key(draw, (x1 - half, y0, x1, y1), "NEXT \u25b6", buttons, lambda: on_step(1),
              fill=MENU_ROW if page < pages - 1 else dim,
              text_fill=MENU_TEXT if page < pages - 1 else (90, 90, 98), size=20)
    _draw_text_centered(draw, (x0 + half, y0, x1 - half, y1), f"{page + 1}/{pages}",
                        menu_font(16, True), MENU_DIM)


def _draw_setting_rows(draw, area, keys, buttons, page_id):
    """Rows at least MIN_ROW_H tall; split into pages when they don't all fit."""
    x0, y0, x1, y1 = area
    # Closer together when that saves going to a second page.
    gap = 6 if len(keys) * (MIN_ROW_H + 6) - 6 <= y1 - y0 else 4
    if len(keys) * (MIN_ROW_H + gap) - gap <= y1 - y0:
        per_page, pages, page, rows_bottom = len(keys), 1, 0, y1
    else:
        pager_h = MIN_ROW_H - 12
        rows_bottom = y1 - pager_h - gap
        per_page = max(1, (rows_bottom - y0 + gap) // (MIN_ROW_H + gap))
        pages = -(-len(keys) // per_page)
        page = max(0, min(pages - 1, menu_pages.get(page_id, 0)))
        _draw_pager(draw, (x0, y1 - pager_h, x1, y1), page, pages,
                    lambda d: menu_page_step(page_id, d, pages), buttons)
    row_h = min(96, (rows_bottom - y0 + gap) // per_page - gap)
    shown = keys[page * per_page:(page + 1) * per_page]
    for n, key in enumerate(shown):
        top = y0 + n * (row_h + gap)
        _draw_setting_row(draw, (x0, top, x1, top + row_h), key, buttons)
    return y0 + len(shown) * (row_h + gap)


# ---------------------------------------------------------------------------
# WiFi tab: scan with NetworkManager (nmcli) and join a network from the touchscreen.
# Needs system/photobooth-wifi.rules (installed by system/install.sh).
# ---------------------------------------------------------------------------

WIFI_IFACE = "wlan0"
# The booth's own network for the printer and phones (system/setup-printer.sh), if it has one.
PRINTER_WIFI_CONF = Path("/etc/snapbox/printer-wifi")
PRINTER_WIFI_PROFILE = "SnapBox printer WiFi"
WEB_ADDR, WEB_PORT = "10.42.0.1", 8080  # phone prints: http://10.42.0.1:8080 on that network


def _read_printer_wifi():
    """(name, password) of the printer network, or None on a booth without one."""
    try:
        conf = dict(line.split("=", 1) for line in PRINTER_WIFI_CONF.read_text().splitlines()
                    if "=" in line)
        return (conf["SSID"], conf["PASSWORD"]) if conf.get("SSID") else None
    except (OSError, KeyError):
        return None


PRINTER_WIFI = _read_printer_wifi()
WIFI_CONNECT_SECONDS = 45
WIFI_PROFILE_PRIORITY = 10  # networks joined from the booth win over older saved ones

wifi_view = "list"  # "list" or "keyboard"
wifi_networks = []  # [{"ssid", "signal", "security", "in_use"}], one per name, strongest AP
wifi_scanning = False
wifi_connecting = False
wifi_message = None  # (text, ok) result of the last scan or connect
wifi_current = (None, None)  # (SSID, IP) of the connected network
wifi_page = 0
wifi_target = None  # network being joined
wifi_saved_uuid = None  # saved profile for wifi_target, if the Pi already knows it
wifi_password = ""
wifi_kb_page = "lower"
wifi_show_password = True
wifi_radio = None  # True/False: WiFi switched on or off (NetworkManager remembers it across reboots)
wifi_radio_busy = False
_wifi_off_confirm_until = 0.0
WIFI_OFF_CONFIRM_SECONDS = 4


def _nmcli(args, timeout=20):
    return subprocess.run(["nmcli"] + args, capture_output=True, text=True, timeout=timeout)


def _nmcli_fields(line):
    # `nmcli -t` separates fields with ":" and escapes ":" and "\" inside values.
    fields, cur, escaped = [], [], False
    for ch in line:
        if escaped:
            cur.append(ch)
            escaped = False
        elif ch == "\\":
            escaped = True
        elif ch == ":":
            fields.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    fields.append("".join(cur))
    return fields


def wifi_supported(net):
    # Enterprise (802.1X) needs a username too, and WEP is obsolete; only open and WPA work here.
    return "802.1X" not in net["security"] and "WEP" not in net["security"]


def _scan_wifi():
    result = _nmcli(["-t", "-f", "IN-USE,SSID,SIGNAL,SECURITY",
                     "device", "wifi", "list", "ifname", WIFI_IFACE, "--rescan", "yes"], timeout=40)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "scan failed")
    best = {}
    for line in result.stdout.splitlines():
        fields = _nmcli_fields(line)
        if len(fields) < 4 or not fields[1]:
            continue  # hidden network: no name to show
        if PRINTER_WIFI and fields[1] == PRINTER_WIFI[0]:
            continue  # the booth's own printer network
        in_use, ssid, security = fields[0] == "*", fields[1], fields[3].strip()
        try:
            signal = int(fields[2])
        except ValueError:
            signal = 0
        # One entry per network name, even when several access points broadcast it.
        net = best.setdefault(ssid, {"ssid": ssid, "signal": signal,
                                     "security": security, "in_use": False})
        if signal > net["signal"]:
            net["signal"], net["security"] = signal, security
        net["in_use"] |= in_use
    return sorted(best.values(), key=lambda n: (not n["in_use"], -n["signal"], n["ssid"].lower()))


def _wifi_status():
    ssid = ip = None
    result = _nmcli(["-t", "-f", "ACTIVE,SSID", "device", "wifi", "list", "ifname", WIFI_IFACE,
                     "--rescan", "no"])
    for line in result.stdout.splitlines():
        fields = _nmcli_fields(line)
        if len(fields) >= 2 and fields[0] == "yes" and fields[1]:
            ssid = fields[1]
            break
    result = _nmcli(["-t", "-f", "IP4.ADDRESS", "device", "show", WIFI_IFACE])
    for line in result.stdout.splitlines():
        value = line.partition(":")[2]
        if value:
            ip = value.split("/")[0]
            break
    return ssid, ip


def _wifi_profiles(ssid=None, active=False):
    """UUIDs of saved WiFi profiles, optionally only for one network or only active ones."""
    args = ["-t", "-f", "UUID,TYPE,NAME", "connection", "show"] + (["--active"] if active else [])
    uuids = []
    for line in _nmcli(args).stdout.splitlines():
        uuid, ctype, name = (_nmcli_fields(line) + ["", "", ""])[:3]
        if ctype != "802-11-wireless" or name == PRINTER_WIFI_PROFILE:
            continue  # never the printer network: re-joining it would drop the printer
        if ssid is not None:
            got = _nmcli(["-g", "802-11-wireless.ssid", "connection", "show", uuid])
            if got.returncode != 0 or "".join(_nmcli_fields(got.stdout.strip())) != ssid:
                continue
        uuids.append(uuid)
    return uuids


def _wifi_error(result):
    err = (result.stderr or result.stdout).strip()
    print(f"nmcli failed (rc={result.returncode}): {err}")
    low = err.lower()
    if "secrets were required" in low or "802-1x" in low or "psk" in low:
        return "WRONG PASSWORD?"
    if "no network with ssid" in low:
        return "NETWORK NOT FOUND"
    if "timeout" in low or "timed out" in low:
        return "TIMED OUT"
    return "COULD NOT CONNECT"


def _wifi_connect(net, password, saved_uuid):
    """Returns (ok, message). The previous network stays saved until the new one works."""
    ssid = net["ssid"]
    up_timeout = WIFI_CONNECT_SECONDS + 15

    if password is None and saved_uuid:
        result = _nmcli(["--wait", str(WIFI_CONNECT_SECONDS), "connection", "up", saved_uuid],
                        timeout=up_timeout)
        return (True, None) if result.returncode == 0 else (False, _wifi_error(result))

    previous = _wifi_profiles(active=True)
    others = _wifi_profiles(ssid)
    sec = net["security"]
    args = ["connection", "add", "type", "wifi", "ifname", WIFI_IFACE,
            "con-name", ssid, "ssid", ssid,
            "connection.autoconnect-priority", str(WIFI_PROFILE_PRIORITY)]
    if sec:
        # WPA3-only networks use SAE; anything offering WPA/WPA2 works with WPA-PSK.
        key_mgmt = "sae" if "WPA3" in sec and "WPA2" not in sec and "WPA1" not in sec else "wpa-psk"
        args += ["wifi-sec.key-mgmt", key_mgmt, "wifi-sec.psk", password]
    result = _nmcli(args)
    if result.returncode != 0:
        return False, _wifi_error(result)
    new_uuid = None
    for word in result.stdout.replace("(", " ").replace(")", " ").split():
        if word.count("-") == 4 and len(word) == 36:
            new_uuid = word
    if new_uuid is None:
        return False, "COULD NOT CONNECT"

    result = _nmcli(["--wait", str(WIFI_CONNECT_SECONDS), "connection", "up", new_uuid],
                    timeout=up_timeout)
    if result.returncode == 0:
        for uuid in others:
            _nmcli(["connection", "delete", uuid])
        return True, None

    message = _wifi_error(result)
    _nmcli(["connection", "delete", new_uuid])
    for uuid in previous:
        _nmcli(["--wait", str(WIFI_CONNECT_SECONDS), "connection", "up", uuid], timeout=up_timeout)
    return False, message


def _wifi_radio_on():
    result = _nmcli(["radio", "wifi"])
    return result.stdout.strip() != "disabled"


def _wifi_scan_worker():
    global wifi_networks, wifi_scanning, wifi_message, wifi_current, wifi_page, wifi_radio
    try:
        wifi_radio = _wifi_radio_on()
    except Exception as e:
        print(f"WiFi radio check failed: {e}")
    if wifi_radio is False:
        wifi_networks, wifi_current, wifi_scanning = [], (None, None), False
        return
    try:
        wifi_networks = _scan_wifi()
        wifi_page = 0
        wifi_message = None if wifi_networks else ("NO NETWORKS FOUND", False)
    except Exception as e:
        print(f"WiFi scan failed: {e}")
        wifi_message = ("SCAN FAILED", False)
    try:
        wifi_current = _wifi_status()
    except Exception as e:
        print(f"WiFi status failed: {e}")
    wifi_scanning = False


def _wifi_connect_worker(net, password, saved_uuid):
    global wifi_connecting, wifi_message, wifi_current
    try:
        ok, message = _wifi_connect(net, password, saved_uuid)
    except Exception as e:
        print(f"WiFi connect failed: {e}")
        ok, message = False, "COULD NOT CONNECT"
    try:
        wifi_current = _wifi_status()
    except Exception as e:
        print(f"WiFi status failed: {e}")
    if ok:
        print(f"WiFi connected to {net['ssid']} ({wifi_current[1]})")
        wifi_message = (f"CONNECTED TO {net['ssid']}", True)
    else:
        wifi_message = (f"{message} ({net['ssid']})", False)
    wifi_connecting = False
    _wifi_scan_start()


def _wifi_scan_start():
    global wifi_scanning
    if wifi_scanning:
        return
    wifi_scanning = True
    threading.Thread(target=_wifi_scan_worker, daemon=True).start()


def wifi_scan():
    if wifi_connecting:
        return
    _wifi_scan_start()


def _wifi_radio_worker(on):
    global wifi_radio, wifi_radio_busy, wifi_message
    try:
        result = _nmcli(["radio", "wifi", "on" if on else "off"])
        if result.returncode == 0:
            wifi_radio = on
            wifi_message = ("WIFI IS ON", True) if on else None
            print(f"WiFi switched {'on' if on else 'off'}.")
        else:
            err = (result.stderr or result.stdout).strip()
            print(f"WiFi switch failed: {err}")
            # Needs system/photobooth-wifi.rules from this version (installed by install.sh).
            wifi_message = ("NOT ALLOWED: RUN SYSTEM/INSTALL.SH" if "authoriz" in err.lower() or
                            "not allowed" in err.lower() else "COULDN'T SWITCH WIFI", False)
    except Exception as e:
        print(f"WiFi switch failed: {e}")
        wifi_message = ("COULDN'T SWITCH WIFI", False)
    wifi_radio_busy = False
    if on and wifi_radio:
        time.sleep(4)  # give it a moment to come up and rejoin a saved network
        _wifi_scan_start()


def wifi_toggle_radio():
    """WiFi off takes a second tap: it also stops SSH and updates."""
    global wifi_radio_busy, _wifi_off_confirm_until
    if wifi_radio_busy or wifi_connecting:
        return
    turn_on = wifi_radio is False
    if not turn_on and time.monotonic() >= _wifi_off_confirm_until:
        _wifi_off_confirm_until = time.monotonic() + WIFI_OFF_CONFIRM_SECONDS
        return
    _wifi_off_confirm_until = 0.0
    wifi_radio_busy = True
    threading.Thread(target=_wifi_radio_worker, args=(turn_on,), daemon=True).start()


def wifi_choose(net):
    global wifi_view, wifi_target, wifi_password, wifi_kb_page, wifi_saved_uuid, wifi_message
    if wifi_connecting:
        return
    if not wifi_supported(net):
        wifi_message = ("THAT NETWORK TYPE ISN'T SUPPORTED", False)
        return
    if not net["security"]:
        wifi_start_connect(net, "")
        return
    wifi_target = net
    wifi_password = ""
    wifi_kb_page = "lower"
    wifi_message = None
    wifi_saved_uuid = None
    wifi_view = "keyboard"
    threading.Thread(target=_wifi_find_saved, args=(net,), daemon=True).start()


def _wifi_find_saved(net):
    global wifi_saved_uuid
    try:
        uuids = _wifi_profiles(net["ssid"])
    except Exception as e:
        print(f"WiFi profile lookup failed: {e}")
        return
    if uuids and wifi_target is net:
        wifi_saved_uuid = uuids[0]


def wifi_start_connect(net, password, saved_uuid=None):
    global wifi_connecting, wifi_view, wifi_message
    if wifi_connecting:
        return
    print(f"WiFi: connecting to {net['ssid']}...")
    wifi_connecting = True
    wifi_message = None
    wifi_view = "list"
    threading.Thread(target=_wifi_connect_worker, args=(net, password, saved_uuid),
                     daemon=True).start()


def wifi_cancel_keyboard():
    global wifi_view, wifi_password
    wifi_view = "list"
    wifi_password = ""


WIFI_KB_ROWS = {
    "lower": ["qwertyuiop", "asdfghjkl", "zxcvbnm"],
    "upper": ["QWERTYUIOP", "ASDFGHJKL", "ZXCVBNM"],
    "sym1": ["1234567890", "-/:;()$&@\"", ".,?!'"],
    "sym2": ["[]{}#%^*+=", "_\\|~<>`", ".,?!'"],
}
# Left key on the third row switches page: shift on letters, more symbols on symbols.
WIFI_KB_SWITCH = {"lower": ("SHIFT", "upper"), "upper": ("SHIFT", "lower"),
                  "sym1": ("#+=", "sym2"), "sym2": ("123", "sym1")}
WIFI_PASSWORD_MAX = 63  # WPA passphrases are 8-63 characters


def wifi_type(ch):
    global wifi_password
    if len(wifi_password) < WIFI_PASSWORD_MAX:
        wifi_password += ch


def wifi_backspace():
    global wifi_password
    wifi_password = wifi_password[:-1]


def wifi_set_kb_page(page):
    global wifi_kb_page
    wifi_kb_page = page


def wifi_toggle_show():
    global wifi_show_password
    wifi_show_password = not wifi_show_password


def wifi_page_step(step):
    global wifi_page
    wifi_page = max(0, wifi_page + step)


def _skinned():
    """The look whose buttons and backgrounds the menus use, or None for the original's flat ones."""
    lk = settings.get("look", "original")
    return lk if looks is not None and lk in looks.LOOKS else None


def _rrect(draw, box, radius=0, fill=None, outline=None, width=1):
    """A rounded box. In the MODERN and CLASSIC looks, boxes in the menu colours are drawn as that
    look's buttons and panels (looks.plate): chrome, enamel, soft cards."""
    lk = _skinned()
    if lk and fill is not None and outline is None and hasattr(draw, "_image"):
        rgb = tuple(fill[:3])
        name = {MENU_ROW: "row", MENU_KEY: "key", MENU_ACCENT: "accent", MENU_DONE: "done",
                MENU_DANGER: "danger", MENU_OFF: "off", MENU_BUSY: "busy", MENU_FIELD: "field",
                MENU_INSET: "inset"}.get(rgb)
        x0, y0, x1, y1 = (round(v) for v in box)
        if name and x1 - x0 >= 12 and y1 - y0 >= 12:
            im = looks.plate(lk, x1 - x0, y1 - y0, name, radius)
            draw._image.paste(im, (x0, y0), im)
            return
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def _menu_canvas(w, h, fill):
    lk = _skinned()
    if lk:
        return looks.menu_ground(lk, w, h).copy()
    return Image.new("RGB", (w, h), fill)


def _draw_key(draw, box, label, buttons, action, fill=None, text_fill=None, size=22):
    fill = MENU_ROW if fill is None else fill  # looked up now: the theme can change
    text_fill = MENU_TEXT if text_fill is None else text_fill
    _rrect(draw, box, radius=8, fill=fill)
    # Anchor on the font's middle so q, g and y line up with the other keys.
    font = _fit_font(draw, max(label.split("\n"), key=len), box[2] - box[0] - 6, size, bold=True)
    draw.multiline_text(((box[0] + box[2]) / 2, (box[1] + box[3]) / 2), label, font=font,
                        fill=text_fill, anchor="mm", align="center", spacing=2)
    buttons.append((box, action))


def _draw_signal_bars(draw, x, y, h, signal, color):
    bars = 4
    lit = max(1, min(bars, (signal + 12) // 25))
    bw = 5
    for i in range(bars):
        bh = int(h * (i + 1) / bars)
        draw.rectangle((x + i * (bw + 2), y + h - bh, x + i * (bw + 2) + bw, y + h),
                       fill=color if i < lit else MENU_BUSY)


def _draw_lock(draw, x, y, color):
    draw.arc((x + 2, y, x + 12, y + 12), 180, 360, fill=color, width=2)
    draw.rectangle((x, y + 6, x + 14, y + 16), fill=color)


def _draw_network_row(draw, box, net, buttons):
    x0, top, x1, bottom = box
    row_h = bottom - top
    supported = wifi_supported(net)
    _rrect(draw, box, radius=10, fill=(40, 90, 55) if net["in_use"] else MENU_ROW)
    text_color = MENU_TEXT if supported else MENU_DIM
    _draw_signal_bars(draw, x0 + 12, top + (row_h - 26) // 2, 26, net["signal"], text_color)
    name_x = x0 + 54
    right = x1 - 12
    if net["security"]:
        _draw_lock(draw, right - 14, top + (row_h - 16) // 2, text_color)
        right -= 24
    label = net["ssid"] if supported else f"{net['ssid']} (NOT SUPPORTED)"
    font = _fit_font(draw, label, right - name_x, 22, bold=net["in_use"])
    bbox = draw.textbbox((0, 0), label, font=font)
    draw.text((name_x - bbox[0], top + (row_h - (bbox[3] - bbox[1])) // 2 - bbox[1]),
              label, font=font, fill=text_color)
    buttons.append((box, lambda net=net: wifi_choose(net)))


def _render_wifi_list(draw, area, buttons):
    x0, y0, x1, y1 = area
    gap = 6
    ssid, ip = wifi_current
    if wifi_radio is False:
        status, name, color = "WIFI IS OFF", None, MENU_DIM
    elif wifi_connecting:
        status, name, color = "CONNECTING...", None, MENU_ACCENT
    elif ssid:
        status, name, color = "CONNECTED TO", ssid, MENU_GOOD
    elif wifi_scanning:
        status, name, color = "CHECKING...", None, MENU_DIM
    else:
        status, name, color = "NOT CONNECTED", None, MENU_DIM

    # Landscape: status on the left, networks on the right. Portrait: stacked.
    landscape = x1 - x0 > y1 - y0
    if landscape:
        sx1 = x0 + (x1 - x0) * 2 // 5
        info, lst = (x0, y0, sx1, y1), (sx1 + 10, y0, x1, y1)
    else:
        info, lst = (x0, y0, x1, y1), None

    ix0, iy0, ix1, iy1 = info
    iw = ix1 - ix0
    y = iy0
    if landscape or not name:
        _draw_text_centered(draw, (ix0, y, ix1, y + 26), status, _fit_font(draw, status, iw, 18), color)
        y += 28
        if name:
            _draw_text_centered(draw, (ix0, y, ix1, y + 30), name, _fit_font(draw, name, iw, 24), color)
            y += 34
    else:
        line = f"{status} {name}"
        _draw_text_centered(draw, (ix0, y, ix1, y + 30), line, _fit_font(draw, line, iw, 20), color)
        y += 34
    if ip and not wifi_connecting:
        # What to type on a computer on the same WiFi; the IP changes with the network.
        ssh_box = (ix0, y, ix1, y + 56)
        _rrect(draw, ssh_box, radius=10, fill=MENU_INSET)
        cmd = f"ssh admin@{ip}"
        alt = f"or ssh admin@{socket.gethostname()}.local"
        _draw_text_centered(draw, (ix0, y + 4, ix1, y + 32), cmd,
                            _fit_font(draw, cmd, iw - 14, 20),
                            MENU_ACCENT if sum(MENU_BG) < 380 else MENU_TEXT)
        _draw_text_centered(draw, (ix0, y + 32, ix1, y + 52), alt,
                            _fit_font(draw, alt, iw - 14, 14, bold=False), MENU_DIM)
        y += 62
    if PRINTER_WIFI and not wifi_connecting and y + 58 + 32 < iy1 - 60 - 70 - 2 * gap:
        _draw_key(draw, (ix0, y, ix1, y + 52), "PRINT FROM A PHONE: HOW?", buttons,
                  lambda: set_menu_tab("phone"), size=18)
        y += 58
    if wifi_message:
        text, ok = wifi_message
        _draw_text_centered(draw, (ix0, y, ix1, y + 28), text, _fit_font(draw, text, iw, 18),
                            MENU_GOOD if ok else MENU_BAD)
        y += 32

    scan_h, radio_h = 70, 60
    radio_top = iy1 - radio_h
    if wifi_radio is False:
        _draw_key(draw, (ix0, radio_top, ix1, iy1), "TURNING ON..." if wifi_radio_busy else "TURN WIFI ON",
                  buttons, wifi_toggle_radio, fill=MENU_DONE, size=20)
        lx0, ly0, lx1, ly1 = lst if lst is not None else (x0, y, x1, radio_top - gap)
        off = ("NO WIFI: PRINTING, SSH AND UPDATES ARE OFF TOO" if PRINTER_WIFI
               else "NO WIFI: SSH AND UPDATES ARE OFF TOO")
        _draw_text_centered(draw, (lx0, ly0, lx1, ly0 + 40), off,
                            _fit_font(draw, off, lx1 - lx0, 16, False), MENU_DIM)
        return
    confirming = time.monotonic() < _wifi_off_confirm_until
    _draw_key(draw, (ix0, radio_top, ix1, iy1),
              "TURNING OFF..." if wifi_radio_busy else
              ("TAP AGAIN: WIFI OFF\n(NO PRINTING, SSH, UPDATES)" if PRINTER_WIFI else
               "TAP AGAIN: WIFI OFF\n(NO SSH OR UPDATES)") if confirming else "TURN WIFI OFF",
              buttons, wifi_toggle_radio, fill=MENU_DANGER if confirming else MENU_KEY, size=18)
    scan_top = radio_top - gap - scan_h
    busy = wifi_scanning or wifi_connecting
    _draw_key(draw, (ix0, scan_top, ix1, radio_top - gap), "SCANNING..." if wifi_scanning else "SCAN AGAIN"
              if wifi_networks else "SCAN FOR WIFI", buttons, wifi_scan,
              fill=MENU_BUSY if busy else MENU_ACCENT,
              text_fill=MENU_TEXT if busy else (0, 0, 0), size=22)

    if lst is None:
        lst = (x0, y, x1, scan_top - gap)
    lx0, ly0, lx1, ly1 = lst
    row_h = MIN_ROW_H - 6
    nets = wifi_networks
    per_page = max(1, (ly1 - ly0 + gap) // (row_h + gap))
    pages, page = 1, 0
    if len(nets) > per_page:
        pager_h = row_h - 6
        per_page = max(1, (ly1 - ly0 - pager_h) // (row_h + gap))
        pages = -(-len(nets) // per_page)
        page = max(0, min(pages - 1, wifi_page))
        _draw_pager(draw, (lx0, ly1 - pager_h, lx1, ly1), page, pages, wifi_page_step, buttons)
    if not nets and not wifi_scanning:
        _draw_text_centered(draw, (lx0, ly0, lx1, ly0 + 40), "NO NETWORKS YET",
                            menu_font(18), MENU_DIM)
    for n, net in enumerate(nets[page * per_page:(page + 1) * per_page]):
        top = ly0 + n * (row_h + gap)
        _draw_network_row(draw, (lx0, top, lx1, top + row_h), net, buttons)


def _render_wifi_keyboard(draw, area, buttons):
    """Full screen: which network (+ saved password), the password row, then four key rows."""
    x0, y0, x1, y1 = area
    w = x1 - x0
    gap = 5

    top_h = 52
    title = f"WIFI PASSWORD: {wifi_target['ssid']}"
    title_x1 = x1
    if wifi_saved_uuid:
        sw = min(240, w // 2)
        _draw_key(draw, (x1 - sw, y0, x1, y0 + top_h), "USE SAVED PASSWORD", buttons,
                  lambda: wifi_start_connect(wifi_target, None, wifi_saved_uuid),
                  fill=(40, 90, 55), size=16)
        title_x1 = x1 - sw - gap
    _draw_text_centered(draw, (x0, y0, title_x1, y0 + top_h), title,
                        _fit_font(draw, title, title_x1 - x0, 18), MENU_DIM)
    y = y0 + top_h + gap

    row_h = 62
    cancel = (x0, y, x0 + int(w * 0.17), y + row_h)
    connect = (x1 - int(w * 0.22), y, x1, y + row_h)
    show = (connect[0] - gap - int(w * 0.14), y, connect[0] - gap, y + row_h)
    field = (cancel[2] + gap, y, show[0] - gap, y + row_h)
    _draw_key(draw, cancel, "CANCEL", buttons, wifi_cancel_keyboard, fill=MENU_KEY, size=18)
    ready = len(wifi_password) >= 8
    _draw_key(draw, connect, "CONNECT" if ready else "8+ CHARS", buttons,
              (lambda: wifi_start_connect(wifi_target, wifi_password)) if ready else (lambda: None),
              fill=MENU_DONE if ready else (50, 50, 58), size=20 if ready else 15)
    _draw_key(draw, show, "HIDE" if wifi_show_password else "SHOW", buttons, wifi_toggle_show,
              size=16)
    _rrect(draw, field, radius=8, fill=MENU_FIELD)
    draw.rounded_rectangle(field, radius=8, outline=MENU_ACCENT, width=2)
    shown = wifi_password if wifi_show_password else "\u2022" * len(wifi_password)
    font = menu_font(24)
    max_w = field[2] - field[0] - 20
    while shown and draw.textlength(shown + "|", font=font) > max_w:
        shown = shown[1:]  # keep the end (where you're typing) visible
    bbox = draw.textbbox((0, 0), shown + "|", font=font)
    draw.text((field[0] + 10 - bbox[0], y + (row_h - (bbox[3] - bbox[1])) // 2 - bbox[1]),
              shown + "|", font=font, fill=MENU_TEXT)
    y += row_h + gap

    key_h = min(140, (y1 - y - 3 * gap) // 4)
    key_w = (w - 9 * gap) / 10
    rows = WIFI_KB_ROWS[wifi_kb_page]

    def key_box(col, row, span=1.0, offset=0.0):
        left = x0 + (col + offset) * (key_w + gap)
        top = y + row * (key_h + gap)
        return (int(left), top, int(left + span * key_w + (span - 1) * gap), top + key_h)

    for r in range(2):
        chars = rows[r]
        offset = (10 - len(chars)) / 2
        for c, ch in enumerate(chars):
            _draw_key(draw, key_box(c, r, offset=offset), ch, buttons,
                      lambda ch=ch: wifi_type(ch), size=26)

    label, target = WIFI_KB_SWITCH[wifi_kb_page]
    active = wifi_kb_page == "upper"
    _draw_key(draw, key_box(0, 2, span=1.5), label, buttons, lambda t=target: wifi_set_kb_page(t),
              fill=MENU_ACCENT if active else MENU_KEY,
              text_fill=(0, 0, 0) if active else MENU_TEXT, size=16)
    chars = rows[2]
    offset = 1.5 + (7 - len(chars)) / 2
    for c, ch in enumerate(chars):
        _draw_key(draw, key_box(c, 2, offset=offset), ch, buttons, lambda ch=ch: wifi_type(ch),
                  size=26)
    _draw_key(draw, key_box(8.5, 2, span=1.5), "\u232b", buttons, wifi_backspace,
              fill=MENU_KEY, size=28)

    letters = wifi_kb_page in ("lower", "upper")
    _draw_key(draw, key_box(0, 3, span=2), "123" if letters else "ABC", buttons,
              lambda: wifi_set_kb_page("sym1" if letters else "lower"), fill=MENU_KEY, size=20)
    _draw_key(draw, key_box(2, 3, span=8), "SPACE", buttons, lambda: wifi_type(" "), size=18)


def render_wifi_tab(draw, area, buttons):
    if wifi_view == "keyboard" and wifi_target is not None:
        _render_wifi_keyboard(draw, area, buttons)
    else:
        _render_wifi_list(draw, area, buttons)


# ---------------------------------------------------------------------------
# Review screen: swipe through saved strips to print or delete them
# (opened with the photo button under the gear). Called "gallery" in the code
# because "review" already means the end-of-strip KEEP / RETAKE screen.
# ---------------------------------------------------------------------------

GALLERY_IDLE_SECONDS = 60  # back to the camera after this long untouched
DELETE_CONFIRM_SECONDS = 4
SWIPE_MIN_PX = 50
STORAGE_LOW_BYTES = 1024 ** 3
STORAGE_FULL_BYTES = 200 * 1024 ** 2

gallery_open = False
gallery_paths = []
gallery_index = 0
gallery_buttons = []
_gallery_delete_until = 0.0
gallery_pair_first = None  # MIX 2 STRIPS: the strip chosen for the left half of the sheet
gallery_reframe = None  # CHANGE FRAME: {"path", "photos", "fx", "choices", "pos", "views"}
_gallery_drawn = None
_gallery_thumbs = {}
_gesture_down = None


def storage_free_bytes():
    try:
        return shutil.disk_usage(BASE).free
    except OSError:
        return None


def storage_status():
    """Returns (text, level) with level "ok", "low" or "full"."""
    free = storage_free_bytes()
    if free is None:
        return "STORAGE UNKNOWN", "ok"
    # A strip's kept photos (for CHANGE FRAME) count too.
    sizes = [(_size(p) or 0) + sum(_size(f) or 0 for f in strip_photos_dir(p).glob("*.jpg"))
             for p in gallery_paths[:20]]
    sizes = [s for s in sizes if s]
    per_strip = sum(sizes) / len(sizes) if sizes else 1_000_000
    usable = max(0, free - STORAGE_FULL_BYTES)
    text = f"{free / 1024 ** 3:.1f} GB FREE · ABOUT {int(usable / per_strip):,} MORE STRIPS"
    if free < STORAGE_FULL_BYTES:
        return text, "full"
    if free < STORAGE_LOW_BYTES:
        return text, "low"
    return text, "ok"


def _size(path):
    try:
        return path.stat().st_size
    except OSError:
        return None


def open_gallery():
    global gallery_open, gallery_paths, gallery_index, _gallery_delete_until, _gallery_drawn
    global gallery_pair_first
    close_menu(redraw=False)
    print("Review screen opened.")
    gallery_open = True
    gallery_paths = browsable_paths()
    gallery_index = 0
    _gallery_delete_until = 0.0
    gallery_pair_first = None
    _end_reframe()
    _gallery_drawn = None
    stop_camera()  # nothing reads it here; a camera left streaming unread can stall
    update_gallery(force=True)


def close_gallery(redraw=True):
    global gallery_open, _gesture_down
    if not gallery_open:
        return
    print("Review screen closed.")
    gallery_open = False
    _end_reframe()
    _gesture_down = None
    _gallery_thumbs.clear()
    if mode == "browse":
        _refresh_browse_list()  # a strip shown in browse mode may have been deleted
    if not screen_asleep:
        start_camera()
    _invalidate_live_preview()
    if redraw:
        update_lcd()


def gallery_step(step):
    global gallery_index, _gallery_delete_until
    new = gallery_index + step
    if 0 <= new < len(gallery_paths):
        gallery_index = new
        _gallery_delete_until = 0.0


def gallery_print():
    if gallery_paths:
        start_print(gallery_paths[gallery_index])


def can_reframe(path):
    return (strip_photos_dir(path) / "photo0.jpg").exists()


def _forget_slot_cache(photos):
    ids = {id(p) for p in photos if p is not None}
    for key in [k for k in _slot_cache if k[0] in ids]:
        del _slot_cache[key]


def _end_reframe():
    global gallery_reframe
    if gallery_reframe is not None:
        _forget_slot_cache(gallery_reframe["photos"])
        gallery_reframe = None


def gallery_reframe_start():
    """CHANGE FRAME: rebuild this strip from its kept photos with any frame that fits them."""
    global gallery_reframe
    if not gallery_paths or not can_reframe(gallery_paths[gallery_index]):
        return
    path = gallery_paths[gallery_index]
    try:
        with Image.open(path) as saved:
            meta = json.loads(saved.info.get("comment", b"") or b"null") or {}
    except Exception as e:
        print(f"Could not read strip {path}: {e}")
        return
    count = len(meta.get("slots") or DEFAULT_SLOTS)
    try:
        with Image.open(path) as saved:
            kind = image_kind(saved.size)
    except Exception:
        kind = "strip"
    photos = []
    for i in range(count):
        try:
            photos.append(Image.open(strip_photos_dir(path) / f"photo{i}.jpg").convert("RGB"))
        except Exception:
            photos.append(None)
    # Any design with room for exactly these photos: its own layout first, then the others
    # (a 4-photo strip can become a 4-photo big sheet, and back).
    choices = [i for k in [kind] + [k for k in LAYOUTS if k != kind]
               for i in indices_for_capacity(count, k)]
    if not choices or not any(photos):
        flash_message("NO FRAMES FIT THIS STRIP", seconds=1.0)
        return
    # By path; strips saved before designs could be in gift folders only have the file name.
    ids, names = [design_id(frames[i]) for i in choices], [frames[i].name for i in choices]
    pos = (ids.index(meta["design"]) if meta.get("design") in ids
           else names.index(meta["frame"]) if meta.get("frame") in names else 0)
    fx = meta.get("fx") or {"seed": 0, "opts": [], "stamp": "", "bw": False}
    gallery_reframe = {"path": path, "photos": photos, "fx": fx, "choices": choices, "pos": pos,
                       "start": pos, "views": {}}
    print(f"Changing the frame of {path.name}")


def reframe_step(step):
    r = gallery_reframe
    r["pos"] = (r["pos"] + step) % len(r["choices"])


def _reframe_strip(frame_index):
    r = gallery_reframe
    strip = compose_single_strip(r["photos"], frame_index, fx=r["fx"]).convert("RGB")
    _forget_slot_cache(r["photos"])  # a different size per frame: don't let them pile up
    return strip


def gallery_reframe_save():
    """Rewrites the strip with the chosen frame. The kept photos stay, so it can change again."""
    r = gallery_reframe
    path, frame_index = r["path"], r["choices"][r["pos"]]
    if r["pos"] != r["start"]:
        try:
            old = path.stat()
            strip = _reframe_strip(frame_index)
            meta = strip_meta(frame_slots(frame_index)[:len(r["photos"])], frame_index, r["fx"])
            write_file_durably(path, lambda f: strip.save(f, format="JPEG", quality=95, comment=meta))
            os.utime(path, ns=(old.st_atime_ns, old.st_mtime_ns))  # keeps its place in the list
        except OSError as e:
            print(f"Could not save the new frame: {e}")
            flash_message("COULD NOT SAVE\nStorage full?", seconds=1.5)
            return
        for key in [k for k in _gallery_thumbs if k[0] == path]:
            del _gallery_thumbs[key]
        print(f"Changed the frame of {path.name} to {frames[frame_index].name}")
    _end_reframe()
    flash_message("FRAME CHANGED", seconds=0.6)


def gallery_reframe_cancel():
    _end_reframe()


def gallery_pair_start():
    """MIX 2 STRIPS: this strip goes on the left; swipe to the one for the right."""
    global gallery_pair_first
    if gallery_paths and is_sheet_file(gallery_paths[gallery_index]):
        flash_message("BIG SHEETS PRINT\nON THEIR OWN", seconds=1.0)
        return
    if gallery_paths:
        gallery_pair_first = gallery_paths[gallery_index]
        if len(gallery_paths) > 1:
            gallery_step(1 if gallery_index < len(gallery_paths) - 1 else -1)


def gallery_pair_cancel():
    global gallery_pair_first
    gallery_pair_first = None


def gallery_pair_print():
    global gallery_pair_first
    if gallery_paths and gallery_pair_first is not None:
        if is_sheet_file(gallery_paths[gallery_index]):
            flash_message("PICK A STRIP:\nBIG SHEETS PRINT ALONE", seconds=1.0)
            return
        start_print(gallery_pair_first, gallery_paths[gallery_index])
        gallery_pair_first = None


def gallery_delete():
    global gallery_paths, gallery_index, _gallery_delete_until, gallery_pair_first
    if not gallery_paths:
        return
    now = time.monotonic()
    if now >= _gallery_delete_until:
        _gallery_delete_until = now + DELETE_CONFIRM_SECONDS
        return
    _gallery_delete_until = 0.0
    path = gallery_paths[gallery_index]
    try:
        path.unlink()
        dir_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    except FileNotFoundError:
        pass
    except OSError as e:
        print(f"Could not delete strip {path}: {e}")
        flash_message("COULD NOT DELETE", seconds=1.0)
        return
    print(f"Deleted strip: {path}")
    shutil.rmtree(strip_photos_dir(path), ignore_errors=True)
    if gallery_pair_first == path:
        gallery_pair_first = None
    for key in [k for k in _gallery_thumbs if k[0] == path]:
        del _gallery_thumbs[key]
    gallery_paths = browsable_paths()
    gallery_index = min(gallery_index, max(0, len(gallery_paths) - 1))
    flash_message("DELETED", seconds=0.6)


def _strip_parts(slots):
    return strip_halves(slots) if slots else [
        (0, 0, STRIP_W, STRIP_H // 2), (0, STRIP_H // 2, STRIP_W, STRIP_H)]


def _fold_scale(slots, w, h, gap=10):
    part_h = max(b[3] - b[1] for b in _strip_parts(slots))
    return min((w - gap) / (2 * STRIP_W), h / part_h)


def _fold_strip(full, slots, w, h, gap=10):
    """A strip (any size) cut in two between its middle photos, halves side by side in w x h."""
    parts = _strip_parts(slots)
    scale = _fold_scale(slots, w, h, gap)
    part_h = max(b[3] - b[1] for b in parts)
    kx, ky = full.width / STRIP_W, full.height / STRIP_H
    pw = int(STRIP_W * scale)
    img = Image.new("RGB", (2 * pw + gap, int(part_h * scale)), MAIN_BG)
    for i, (a, b, c, d) in enumerate(parts):
        ph = max(1, int((d - b) * scale))
        piece = full.crop((int(a * kx), int(b * ky), int(c * kx), int(d * ky)))
        piece = piece.resize((pw, ph), Image.BILINEAR)
        # Folded like the main screen: left half at the top, right at the bottom.
        img.paste(piece, (i * (pw + gap), 0 if i == 0 else img.height - ph))
    return img


def _reframe_view(w, h, halves):
    """The strip with the frame being tried, scaled for the screen (cached per frame)."""
    r = gallery_reframe
    frame_index = r["choices"][r["pos"]]
    key = (frame_index, w, h, halves)
    if key not in r["views"]:
        if len(r["views"]) > 6:
            r["views"].clear()
        strip = _reframe_strip(frame_index)
        if halves and frame_kind(frame_index) == "strip":
            r["views"][key] = _fold_strip(strip, frame_slots(frame_index), w, h)
        else:
            strip.thumbnail((w, h), Image.BILINEAR)
            r["views"][key] = strip
    return r["views"][key]


def _gallery_thumb(path, w, h, halves=False):
    """The strip scaled to fit w x h; with halves, cut in two side by side like the main screen
    (top half on the left, bottom half on the right) so the photos are much bigger."""
    key = (path, _mtime(path), w, h, halves)
    thumb = _gallery_thumbs.get(key)
    if thumb is None:
        try:
            src = Image.open(path)
            halves = halves and not is_sheet_size(src.size)  # a sheet is shown whole
            slots = saved_strip_slots(src) if halves else None
            if not halves:
                src.draft("RGB", (w, h))  # JPEG decodes straight to a small size: fast
                img = src.convert("RGB")
                img.thumbnail((w, h), Image.BILINEAR)
            else:
                scale = _fold_scale(slots, w, h)
                src.draft("RGB", (int(STRIP_W * scale * 2), int(STRIP_H * scale * 2)))
                img = _fold_strip(src.convert("RGB"), slots, w, h)
        except Exception as e:
            print(f"Could not open saved strip {path}: {e}")
            img = None
        if len(_gallery_thumbs) > 12:
            _gallery_thumbs.clear()
        thumb = _gallery_thumbs[key] = img
    return thumb


def _strip_time_label(path):
    try:
        when = datetime.strptime(path.stem, "strip_%Y-%m-%d_%H%M%S")
    except ValueError:
        when = datetime.fromtimestamp((_mtime(path) or 0) / 1e9)
    return when.strftime("%b %-d, %Y  %-I:%M %p").upper()


def _draw_pair_sheet(img, draw, area, first, second, arrow_buttons=None):
    """MIX 2 STRIPS: the 4x6 sheet as it will print, the 1st pick fixed on the left and the
    strip being swiped through on the right. With arrow_buttons, small arrows under the right
    strip change it (when there's no room for the big ones)."""
    ax0, ay0, ax1, ay1 = area
    label_h, pad, gap = (46 if arrow_buttons is not None else 30), 8, 8
    strip_h = ay1 - ay0 - label_h - 2 * pad
    strip_w = strip_h * STRIP_W // STRIP_H
    if 2 * strip_w + gap + 2 * pad > ax1 - ax0:
        strip_w = (ax1 - ax0 - gap - 2 * pad) // 2
        strip_h = strip_w * STRIP_H // STRIP_W
    sheet_w = 2 * strip_w + gap + 2 * pad
    sx = (ax0 + ax1 - sheet_w) // 2
    sy = ay0 + (ay1 - ay0 - label_h - strip_h - 2 * pad) // 2
    draw.rectangle((sx, sy, sx + sheet_w, sy + strip_h + 2 * pad), fill=(255, 255, 255))  # the paper
    same = first == second
    for n, (path, label, colour) in enumerate((
            (first, "1ST (KEPT)", MENU_ACCENT),
            (second, "BIG SHEET: CAN'T MIX" if is_sheet_file(second) else
             "SAME = 2 COPIES" if same else "\u25c0 2ND: SWIPE \u25b6", (90, 200, 255)))):
        x = sx + pad + n * (strip_w + gap)
        y = sy + pad
        thumb = _gallery_thumb(path, strip_w, strip_h)
        if thumb is None:
            draw.rectangle((x, y, x + strip_w, y + strip_h), fill=(60, 60, 60))
        else:
            img.paste(thumb, (x + (strip_w - thumb.width) // 2, y + (strip_h - thumb.height) // 2))
        draw.rectangle((x - 3, y - 3, x + strip_w + 2, y + strip_h + 2), outline=colour, width=3)
        lbox = (x - gap, sy + strip_h + 2 * pad + 4, x + strip_w + gap, sy + strip_h + 2 * pad + label_h)
        if n == 1 and arrow_buttons is not None:
            mid = (lbox[0] + lbox[2]) // 2
            for step, text, kx0, kx1 in ((-1, "\u25c0", lbox[0], mid - 3), (1, "\u25b6", mid + 3, lbox[2])):
                enabled = 0 <= gallery_index + step < len(gallery_paths)
                _draw_key(draw, (kx0, lbox[1], kx1, lbox[3]), text, arrow_buttons,
                          lambda st=step: gallery_step(st), fill=MENU_ROW if enabled else MENU_OFF,
                          text_fill=colour if enabled else (90, 90, 98), size=22)
        else:
            _draw_text_centered(draw, lbox, label, _fit_font(draw, label, lbox[2] - lbox[0], 16), colour)


def render_gallery():
    global gallery_buttons
    w, h = ui_size()
    img = _menu_canvas(w, h, MAIN_BG)
    draw = ImageDraw.Draw(img, "RGBA")
    buttons = []
    pad, gap = 8, 6
    bar_h = 62
    landscape = w > h

    back = (pad, pad, pad + 120, bar_h - 4)
    _draw_key(draw, back, "\u25c0 BACK", buttons, close_gallery, fill=MENU_DONE, size=22)
    n = len(gallery_paths)
    tx0, tx1 = back[2] + pad, w - pad
    text, level = storage_status()
    color = {"ok": MENU_DIM, "low": MENU_ACCENT, "full": (255, 90, 90)}[level]
    if level != "ok":
        text = ("STORAGE FULL: " if level == "full" else "STORAGE LOW: ") + text
    if n and gallery_reframe is not None:
        r = gallery_reframe
        title = (f"{LAYOUT_NAMES[frame_kind(r['choices'][r['pos']])]}  \u00b7  "
                 f"{r['pos'] + 1} OF {len(r['choices'])}")
        text, color, level = "SWIPE OR TAP \u25c0 \u25b6 TO TRY FRAMES, THEN SAVE", MENU_ACCENT, "ok"
    elif n and gallery_pair_first is not None:
        title = "MIX 2 STRIPS: THIS IS YOUR PRINT"
        text, color, level = "SWIPE TO CHANGE THE STRIP ON THE RIGHT", MENU_ACCENT, "ok"
    elif n:
        title = f"STRIP {gallery_index + 1} OF {n}  \u00b7  {_strip_time_label(gallery_paths[gallery_index])}"
    else:
        title = "REVIEW"
    _draw_text_centered(draw, (tx0, pad, tx1, pad + 28), title,
                        _fit_font(draw, title, tx1 - tx0, 20), MENU_TEXT)
    _draw_text_centered(draw, (tx0, pad + 30, tx1, bar_h), text,
                        _fit_font(draw, text, tx1 - tx0, 15, level != "ok"), color)

    # Portrait has room for two rows of buttons under the strip.
    four_buttons = n and gallery_reframe is None and gallery_pair_first is None
    action_h = 2 * 62 + gap if four_buttons and not landscape else 70
    top, bottom = bar_h + gap, h - pad - action_h - gap
    if gallery_reframe is not None:
        can_newer = can_older = len(gallery_reframe["choices"]) > 1
    else:
        can_newer, can_older = gallery_index > 0, gallery_index < n - 1
    dim = MENU_OFF

    def arrow(box, label, step, enabled):
        _draw_key(draw, box, label, buttons,
                  lambda: (reframe_step if gallery_reframe is not None else gallery_step)(step),
                  fill=MENU_ROW if enabled else dim,
                  text_fill=MENU_TEXT if enabled else (90, 90, 98), size=30)

    pair_side = landscape and n and gallery_pair_first is not None
    if pair_side:
        # Mixing in landscape: CANCEL and PRINT down the sides, so the sheet gets the full height.
        side_w = 132
        printing = _print_busy.is_set()
        _draw_key(draw, (pad, top, pad + side_w, h - pad), "CANCEL", buttons, gallery_pair_cancel,
                  fill=MENU_KEY, size=22)
        _draw_key(draw, (w - pad - side_w, top, w - pad, h - pad),
                  "PRINTING..." if printing else "PRINT\nTHESE 2", buttons, gallery_pair_print,
                  fill=MENU_BUSY if printing else MENU_ACCENT,
                  text_fill=MENU_TEXT if printing else (0, 0, 0), size=22)
        area = (pad + side_w + gap, top, w - pad - side_w - gap, h - pad)
    elif landscape:
        # Big arrows down each side, the strip in two halves between them.
        arrow_w = 70
        arrow((pad, top, pad + arrow_w, bottom), "\u25c0", -1, can_newer)
        arrow((w - pad - arrow_w, top, w - pad, bottom), "\u25b6", 1, can_older)
        area = (pad + arrow_w + gap, top, w - pad - arrow_w - gap, bottom)
        actions = (pad, h - pad - action_h, w - pad, h - pad)
    else:
        area = (pad, top, w - pad, bottom)
        arrow_w = 70
        arrow((pad, h - pad - action_h, pad + arrow_w, h - pad), "\u25c0", -1, can_newer)
        arrow((w - pad - arrow_w, h - pad - action_h, w - pad, h - pad), "\u25b6", 1, can_older)
        actions = (pad + arrow_w + gap, h - pad - action_h, w - pad - arrow_w - gap, h - pad)

    ax0, ay0, ax1, ay1 = area
    aw, ah = ax1 - ax0, ay1 - ay0
    if not n:
        _draw_text_centered(draw, area, "NO SAVED STRIPS YET", menu_font(22, True), MENU_DIM)
    elif gallery_pair_first is not None:
        _draw_pair_sheet(img, draw, area, gallery_pair_first, gallery_paths[gallery_index],
                         buttons if pair_side else None)
    elif gallery_reframe is not None:
        cur = _reframe_view(aw, ah, landscape)
        img.paste(cur, ((ax0 + ax1 - cur.width) // 2, (ay0 + ay1 - cur.height) // 2))
    else:
        cur = _gallery_thumb(gallery_paths[gallery_index], aw, ah, halves=landscape)
        if cur is None:
            _draw_text_centered(draw, area, "COULD NOT OPEN THIS STRIP", menu_font(18), MENU_DIM)
        else:
            cx, cy = (ax0 + ax1) // 2, (ay0 + ay1) // 2
            if not landscape:
                # Neighbours peek in at the sides, dimmed, as a hint that you can swipe.
                nh = int(ah * 0.8)
                for step, side in ((-1, -1), (1, 1)):
                    i = gallery_index + step
                    if not 0 <= i < n:
                        continue
                    nb = _gallery_thumb(gallery_paths[i], aw, nh)
                    if nb is None:
                        continue
                    nx = cx + side * (cur.width // 2 + 16 + nb.width // 2) - nb.width // 2
                    ny = cy - nb.height // 2
                    img.paste(nb, (nx, ny))
                    draw.rectangle((nx, ny, nx + nb.width, ny + nb.height), fill=(0, 0, 0, 150))
            img.paste(cur, (cx - cur.width // 2, cy - cur.height // 2))

    if n and not pair_side:
        bx0, by0, bx1, by1 = actions
        printing = _print_busy.is_set()
        busy = dict(fill=MENU_BUSY, text_fill=MENU_TEXT)
        go = dict(fill=MENU_ACCENT, text_fill=(0, 0, 0))
        if gallery_reframe is not None:
            half = (bx1 - bx0 - gap) // 2
            _draw_key(draw, (bx0, by0, bx0 + half, by1), "CANCEL", buttons, gallery_reframe_cancel,
                      fill=MENU_KEY, size=22)
            _draw_key(draw, (bx1 - half, by0, bx1, by1), "SAVE\nTHIS FRAME", buttons,
                      gallery_reframe_save, fill=MENU_DONE, size=22)
        elif gallery_pair_first is not None:
            half = (bx1 - bx0 - gap) // 2
            _draw_key(draw, (bx0, by0, bx0 + half, by1), "CANCEL", buttons, gallery_pair_cancel,
                      fill=MENU_KEY, size=22)
            _draw_key(draw, (bx1 - half, by0, bx1, by1),
                      "PRINTING..." if printing else "PRINT\nTHESE 2", buttons, gallery_pair_print,
                      size=22, **(busy if printing else go))
        else:
            # Each print is one 4x6 sheet holding two strips: this one twice, or two different.
            # CHANGE FRAME needs the strip's kept photos (strips saved before this version had none).
            confirming = time.monotonic() < _gallery_delete_until
            reframable = can_reframe(gallery_paths[gallery_index])
            sheet = is_sheet_file(gallery_paths[gallery_index])
            off = dict(fill=MENU_OFF, text_fill=MENU_DIM)
            keys = [
                ("PRINTING..." if printing else "PRINT\nSHEET" if sheet else "PRINT\n2 COPIES",
                 gallery_print, busy if printing else go),
                ("MIX\n2 STRIPS", gallery_pair_start, off if sheet else dict(fill=MENU_KEY) if _skinned() else dict(fill=(40, 120, 160), text_fill=(255, 255, 255))),
                ("CHANGE\nFRAME", gallery_reframe_start,
                 (dict(fill=MENU_KEY) if _skinned() else dict(fill=(110, 70, 160), text_fill=(255, 255, 255))) if reframable
                 else dict(fill=MENU_OFF, text_fill=MENU_DIM)),
                ("DELETE?\nTAP AGAIN" if confirming else "DELETE", gallery_delete,
                 dict(fill=(235, 60, 60) if confirming else MENU_DANGER)),
            ]
            cols = 4 if landscape else 2
            rows = len(keys) // cols
            kw = (bx1 - bx0 - gap * (cols - 1)) / cols
            kh = (by1 - by0 - gap * (rows - 1)) / rows
            for k, (label, action, style) in enumerate(keys):
                x, y = bx0 + (k % cols) * (kw + gap), by0 + (k // cols) * (kh + gap)
                _draw_key(draw, (int(x), int(y), int(x + kw), int(y + kh)), label, buttons, action,
                          size=20, **style)

    gallery_buttons = buttons
    return img


def update_gallery(force=False):
    global _gallery_drawn
    state = (gallery_index, tuple(gallery_paths), time.monotonic() < _gallery_delete_until,
             _print_busy.is_set(), screen_rotation, gallery_pair_first,
             gallery_reframe and gallery_reframe["pos"])
    if force or state != _gallery_drawn:
        _gallery_drawn = state
        update_lcd()


def next_gestures(events):
    """[("tap", (x, y)) or ("swipe", dx)] in UI coordinates, each counted when the finger lifts.
    Every touch in the batch counts: none is dropped for coming soon after another."""
    global _gesture_down
    gestures = []
    for event in events:
        if event.type in (pygame.FINGERDOWN, pygame.FINGERUP):
            screen_w, screen_h = lcd.get_size()
            pos = (event.x * screen_w, event.y * screen_h)
        elif event.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP):
            if getattr(event, "touch", False):
                continue  # the same touch also arrives as a finger event
            pos = event.pos
        else:
            continue
        point = screen_to_ui(*pos)
        if point is None:
            continue
        if event.type in (pygame.FINGERDOWN, pygame.MOUSEBUTTONDOWN):
            _gesture_down = point
        elif _gesture_down is not None:
            start, _gesture_down = _gesture_down, None
            dx, dy = point[0] - start[0], point[1] - start[1]
            if abs(dx) >= SWIPE_MIN_PX and abs(dx) > abs(dy):
                gestures.append(("swipe", dx))
            else:
                gestures.append(("tap", start))
    return gestures


def handle_gallery_gesture(gesture):
    kind, value = gesture
    if kind == "swipe":
        # Finger moves left: the next (older) strip, or the next frame, slides in from the right.
        (reframe_step if gallery_reframe is not None else gallery_step)(1 if value < 0 else -1)
    else:
        x, y = value
        for (x0, y0, x1, y1), action in gallery_buttons:
            if x0 <= x <= x1 and y0 <= y <= y1:
                action()
                break
    if gallery_open:
        update_gallery(force=True)


# ---------------------------------------------------------------------------
# Software updates (BOOTH tab > UPDATES). The booth downloads the "stable" branch with its own
# read-only key (system/setup-updates.sh); system/photobooth-update.py installs it and rolls
# back if the new version doesn't run.
# ---------------------------------------------------------------------------

UPDATE_REMOTE = "updates"
UPDATE_BRANCH = "stable"
UPDATE_FIRST_CHECK_SECONDS = 90
UPDATE_CHECK_SECONDS = 6 * 3600
UPDATE_RESULT_FILE = BASE / "update-result.json"
UPDATE_ANNOUNCEMENT = "Your creator has gifted\nyou with an update!\n\nTap the gear > BOOTH > UPDATES"

update_state = "idle"  # idle, checking, up_to_date, available, installing, error
update_info = None  # the available update: {"sha", "version", "subject"}
update_error = None
update_last_result = None
_update_next_check = time.monotonic() + UPDATE_FIRST_CHECK_SECONDS
_update_next_result_poll = 0.0
_update_announced = None
_update_announce_pending = False


def _git(*args, timeout=60):
    # Never wait for a password: the updates repo is public.
    return subprocess.run(["git", "-C", str(BASE), *args], capture_output=True, text=True,
                          timeout=timeout, env={**os.environ, "GIT_TERMINAL_PROMPT": "0"})


def _booth_version():
    try:
        result = _git("log", "-1", "--format=%h %cs")
    except Exception:
        return "UNKNOWN"
    return result.stdout.strip() or "UNKNOWN"


BOOTH_VERSION = _booth_version()


def _update_check_worker(announce):
    global update_state, update_info, update_error, _update_announced, _update_announce_pending
    try:
        result = _git("fetch", "--quiet", UPDATE_REMOTE, UPDATE_BRANCH, timeout=90)
        if result.returncode != 0:
            print(f"Update check failed: {result.stderr.strip()}")
            update_error = "COULDN'T REACH GITHUB; CHECK WIFI"
            update_state = "error"
            return
        ref = f"{UPDATE_REMOTE}/{UPDATE_BRANCH}"
        # Nothing new if stable is already part of what this booth runs.
        if _git("merge-base", "--is-ancestor", ref, "HEAD").returncode == 0:
            update_info = None
            update_state = "up_to_date"
            return
        sha = _git("rev-parse", ref).stdout.strip()
        version, _, subject = _git("log", "-1", "--format=%h %cs%n%s", ref).stdout.strip().partition("\n")
        update_info = {"sha": sha, "version": version, "subject": subject}
        update_state = "available"
        print(f"Update available: {version} {subject}")
        if announce and _update_announced != sha:
            _update_announced = sha
            _update_announce_pending = True
    except Exception as e:
        print(f"Update check failed: {e}")
        update_error = "UPDATE CHECK FAILED"
        update_state = "error"


def check_for_updates(announce=False):
    global update_state
    if update_state in ("checking", "installing"):
        return
    update_state = "checking"
    threading.Thread(target=_update_check_worker, args=(announce,), daemon=True).start()


_update_install_started = 0.0


def install_update():
    global update_state, update_error, _update_install_started
    if update_state != "available":
        return
    try:
        result = subprocess.run(["systemctl", "start", "--no-block", "photobooth-update.service"],
                                capture_output=True, text=True, timeout=20)
    except Exception as e:
        result = None
        print(f"Could not start the updater: {e}")
    if result is None or result.returncode != 0:
        if result is not None:
            print(f"Could not start the updater: {result.stderr.strip()}")
        update_error = "COULDN'T START THE UPDATER"
        update_state = "error"
        return
    print("Updater started; the app will restart.")
    update_state = "installing"
    _update_install_started = time.monotonic()


def _booth_idle():
    return (not menu_open and not gallery_open and not screen_asleep and mode == "creation"
            and current_slot == 0 and countdown_value is None and not in_review())


def tick_updates():
    global _update_next_check, _update_next_result_poll, _update_announce_pending
    global update_last_result, update_state
    now = time.monotonic()
    if update_state == "installing" and now - _update_install_started > 900:
        # The updater restarts the app when it works; still here = it didn't. Without this the
        # booth would count as busy forever: no auto shut-down, no screen sleep.
        print("The updater never finished; back to normal.")
        update_state = "idle"
    if now >= _update_next_check:
        _update_next_check = now + UPDATE_CHECK_SECONDS
        check_for_updates(announce=True)

    if now >= _update_next_result_poll:
        # The updater leaves its outcome here; it finishes after this (new) app has started.
        _update_next_result_poll = now + 2
        if UPDATE_RESULT_FILE.exists():
            try:
                update_last_result = json.loads(UPDATE_RESULT_FILE.read_text())
            except (OSError, ValueError):
                update_last_result = None
            try:
                UPDATE_RESULT_FILE.unlink()
            except OSError:
                pass
            if update_state == "installing":
                update_state = "idle"  # it ended without restarting the app (e.g. no internet)
            if update_last_result:
                text = update_last_result.get("message", "")
                if update_last_result.get("version"):
                    text += f"\n{update_last_result['version']}"
                wake_screen()
                flash_message(text, seconds=3.0)

    if _update_announce_pending and _booth_idle():
        _update_announce_pending = False
        flash_message(UPDATE_ANNOUNCEMENT, seconds=6.0)


def open_phone_help():
    """From the main screen (a tap on the printer in the corner): how to print from a phone."""
    if not PRINTER_WIFI:
        return
    open_menu()
    set_menu_tab("phone")
    update_menu(force=True)


def render_phone_view(draw, area):
    """How to print photos from a phone: three big steps, one thing to do in each."""
    x0, y0, x1, y1 = area
    w = x1 - x0
    title = "PRINT PHOTOS FROM YOUR PHONE"
    _draw_text_centered(draw, (x0, y0, x1, y0 + 40), title, _fit_font(draw, title, w - 20, 28),
                        MENU_TEXT)
    ssid, password = PRINTER_WIFI
    steps = [
        ("ON YOUR PHONE, JOIN THIS WIFI", ssid, f"password:  {password}"),
        ("THEN OPEN THIS IN THE PHONE'S BROWSER", f"{WEB_ADDR}:{WEB_PORT}", None),
        ("PICK A DESIGN, ADD YOUR PHOTOS", "SAVE & PRINT", None),
    ]
    note = "If the phone says the WiFi has no internet, stay connected anyway."
    gap = 10
    top = y0 + 48
    note_h = 28
    step_h = (y1 - note_h - top - gap * (len(steps) - 1)) // len(steps)
    num_w = min(76, step_h)
    for i, (label, big, small) in enumerate(steps):
        box = (x0, top, x1, top + step_h)
        _rrect(draw, box, radius=14, fill=MENU_ROW)
        cy = (box[1] + box[3]) // 2
        r = num_w // 2 - 8
        cx = x0 + 12 + num_w // 2
        draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=MENU_ACCENT)
        draw.text((cx, cy), str(i + 1), font=menu_font(max(18, int(r * 1.2)), True), fill=(0, 0, 0),
                  anchor="mm")
        tx0, tx1 = x0 + num_w + 22, x1 - 14
        tw = tx1 - tx0
        for shrink in (1.0, 0.88, 0.78, 0.68, 0.6):
            lines = [(label, _fit_font(draw, label, tw, round(17 * shrink), bold=False), MENU_DIM),
                     (big, _fit_font(draw, big, tw, round(34 * shrink)), MENU_TEXT)]
            if small:
                lines.append((small, _fit_font(draw, small, tw, round(22 * shrink)), MENU_TEXT))
            heights = [round(f.size * 1.12) + 4 for _, f, _ in lines]
            if sum(heights) <= step_h - 2:
                break
        y = cy - sum(heights) // 2
        for (text, font, fill), lh in zip(lines, heights):
            draw.text((tx0, y + lh // 2), text, font=font, fill=fill, anchor="lm")
            y += lh
        top += step_h + gap
    _draw_text_centered(draw, (x0, y1 - note_h, x1, y1), note,
                        _fit_font(draw, note, w, 16, bold=False), MENU_DIM)


def render_update_view(draw, area, buttons):
    x0, y0, x1, y1 = area
    w = x1 - x0
    title = f"SOFTWARE UPDATE  \u00b7  THIS BOOTH: {BOOTH_VERSION}"
    _draw_text_centered(draw, (x0, y0, x1, y0 + 30), title, _fit_font(draw, title, w, 18),
                        MENU_TEXT)
    y = y0 + 38

    lines, color = [], MENU_DIM
    if update_state == "checking":
        lines = ["CHECKING..."]
    elif update_state == "up_to_date":
        lines, color = ["UP TO DATE"], MENU_GOOD
    elif update_state == "available" and update_info:
        lines, color = ["Your creator has gifted you with an update!",
                        update_info["version"], update_info["subject"]], MENU_ACCENT
    elif update_state == "installing":
        lines, color = ["INSTALLING...", "THE BOOTH WILL RESTART"], MENU_ACCENT
    elif update_state == "error":
        lines, color = [update_error or "SOMETHING WENT WRONG"], MENU_BAD
    elif update_last_result:
        lines = ["LAST UPDATE: " + update_last_result.get("message", "")]
    else:
        lines = ["TAP CHECK FOR UPDATES"]
    for n, text in enumerate(lines):
        first = n == 0
        _draw_text_centered(draw, (x0, y, x1, y + 26), text,
                            _fit_font(draw, text, w, 20 if first else 15, first),
                            color if first else MENU_DIM)
        y += 28

    button_h, gap = 64, 6
    bottom = y1 - 30
    back = (x0, bottom - button_h, x1, bottom)
    _draw_key(draw, back, "\u25c0 BACK", buttons, lambda: set_menu_tab("booth"), fill=MENU_ROW)
    busy = update_state in ("checking", "installing")
    check = (x0, back[1] - gap - button_h, x1, back[1] - gap)
    _draw_key(draw, check, "CHECKING..." if update_state == "checking" else "CHECK FOR UPDATES",
              buttons, check_for_updates, fill=MENU_BUSY if busy else MENU_ACCENT,
              text_fill=MENU_TEXT if busy else (0, 0, 0))
    if update_state == "available":
        install = (x0, check[1] - gap - button_h, x1, check[1] - gap)
        _draw_key(draw, install, "INSTALL UPDATE", buttons, install_update, fill=MENU_DONE)
    note = "THE BOOTH RESTARTS WHILE UPDATING. PHOTOS AND SETTINGS ARE KEPT."
    _draw_text_centered(draw, (x0, y1 - 24, x1, y1), note, _fit_font(draw, note, w, 13, False),
                        MENU_DIM)


def _preview_slot_index():
    return max(0, min(current_slot, current_capacity() - 1))


def _draw_menu_preview(img, draw, box, cam, buttons=None):
    """The live camera in box, cropped like the next photo and with its EFFECTS add-ons."""
    x0, y0, x1, y1 = box
    pw, ph = x1 - x0, y1 - y0
    if cam is not None:
        index = _preview_slot_index()
        img.paste(apply_effects(center_crop_to_slot(cam, pw, ph, resample=Image.BILINEAR), index),
                  (x0, y0))
    else:
        draw.rectangle(box, fill=(0, 0, 0))
        _draw_text_centered(draw, box, "CAMERA STARTING...", menu_font(18), MENU_DIM)
    if buttons is not None:
        buttons.append((box, lambda: set_menu_fullscreen(True)))


def _fit_box(area, aspect):
    """The biggest box of this aspect in area, centred across and at the top."""
    x0, y0, x1, y1 = area
    w, h = x1 - x0, int((x1 - x0) / aspect)
    if h > y1 - y0:
        w, h = int((y1 - y0) * aspect), y1 - y0
    left = x0 + (x1 - x0 - w) // 2
    return (left, y0, left + w, y0 + h)


def render_preview_tab(img, draw, top, cam, buttons):
    """CAMERA / EFFECTS: the live preview as big as fits beside (or above) the settings."""
    w, h = ui_size()
    pad, gap = 8, 6
    keys = [k for k, _, _, _ in PREVIEW_TABS[menu_tab]]
    aspect = _slot_aspect(_preview_slot_index())
    if is_landscape():
        full_h = 60
        left_w = int(w * 0.58)
        box = _fit_box((pad, top, left_w, h - pad - full_h - gap), aspect)
        _draw_menu_preview(img, draw, box, cam, buttons)
        _draw_key(draw, (box[0], box[3] + gap, box[2], box[3] + gap + full_h), "FULL SCREEN PREVIEW",
                  buttons, lambda: set_menu_fullscreen(True), size=18)
        rows = (left_w + pad, top, w - pad, h - pad)
    else:
        box = _fit_box((pad, top, w - pad, top + (h - top) // 2), aspect)
        _draw_menu_preview(img, draw, box, cam, buttons)
        rows = (pad, box[3] + gap + 2, w - pad, h - pad)
    _draw_setting_rows(draw, rows, keys, buttons, menu_tab)


def render_fullscreen_preview(img, draw, cam, buttons):
    """The preview filling the screen above one setting: tap the names to pick which one."""
    w, h = ui_size()
    pad, gap = 6, 5
    chip_h, row_h = 52, 76
    keys = [k for k, _, _, _ in PREVIEW_TABS[menu_tab]]
    focus = menu_focus[menu_tab] if menu_focus[menu_tab] in keys else keys[0]
    row_top = h - pad - row_h
    chip_top = row_top - gap - chip_h
    box = _fit_box((0, 0, w, chip_top - gap), _slot_aspect(_preview_slot_index()))
    _draw_menu_preview(img, draw, box, cam)
    labels = [("\u25c0 BACK", None)] + [(SETTING_SHORT.get(k, k.upper()), k) for k in keys]
    chip_w = (w - 2 * pad - gap * (len(labels) - 1)) / len(labels)
    for n, (label, key) in enumerate(labels):
        x = pad + n * (chip_w + gap)
        cbox = (int(x), chip_top, int(x + chip_w), chip_top + chip_h)
        if key is None:
            if menu_quick:
                _draw_key(draw, cbox, "DONE", buttons, close_menu, fill=MENU_DONE, size=16)
            else:
                _draw_key(draw, cbox, label, buttons, lambda: set_menu_fullscreen(False), fill=MENU_DONE, size=16)
        else:
            active = key == focus
            _draw_key(draw, cbox, label, buttons, lambda k=key: set_menu_focus(k),
                      fill=MENU_ACCENT if active else MENU_ROW,
                      text_fill=(0, 0, 0) if active else MENU_TEXT, size=16)
    _draw_setting_row(draw, (pad, row_top, w - pad, row_top + row_h), focus, buttons)


HELP_LINES = [
    "BUTTON: 1 press = photo   2 = next frame",
    "3 = 3 or 4 photos   hold 1 sec = browse",
    "In browse: 1 = older  2 = newer  3 = print",
    "Hold 6 sec = shut down",
]


def render_menu(cam=None):
    global menu_buttons
    w, h = ui_size()
    img = _menu_canvas(w, h, MENU_BG)
    draw = ImageDraw.Draw(img)
    buttons = []
    pad = 8
    bar_h = 70

    if date_entry is not None:
        _render_date_keypad(draw, (pad, pad, w - pad, h - pad), buttons)
        menu_buttons = buttons
        return img
    if menu_tab == "wifi" and wifi_view == "keyboard" and wifi_target is not None:
        # Typing gets the whole screen: no tab bar, the biggest keys possible.
        _render_wifi_keyboard(draw, (pad, pad, w - pad, h - pad), buttons)
        menu_buttons = buttons
        return img
    if menu_fullscreen and menu_tab in PREVIEW_TABS:
        render_fullscreen_preview(img, draw, cam, buttons)
        menu_buttons = buttons
        return img

    tabs = (("camera", "CAMERA"), ("effects", "EFFECTS"), ("booth", "BOOTH"), ("wifi", "WIFI"))
    done_w = 100 if is_landscape() else 80
    tab_w = min(170, (w - done_w - pad * (len(tabs) + 2)) // len(tabs))
    x = pad
    for tab, text in tabs:
        box = (x, pad, x + tab_w, bar_h - 4)
        active = tab == menu_tab
        _rrect(draw, box, radius=10, fill=MENU_ACCENT if active else MENU_ROW)
        _draw_text_centered(draw, box, text, _fit_font(draw, text, tab_w - 10, 22),
                            (0, 0, 0) if active else MENU_TEXT)
        buttons.append((box, lambda t=tab: set_menu_tab(t)))
        x += tab_w + pad
    done = (w - pad - done_w, pad, w - pad, bar_h - 4)
    _rrect(draw, done, radius=10, fill=MENU_DONE)
    _draw_text_centered(draw, done, "DONE", menu_font(22, True), MENU_TEXT)
    buttons.append((done, close_menu))
    top = bar_h + 4

    if menu_tab in PREVIEW_TABS:
        render_preview_tab(img, draw, top, cam, buttons)
    elif menu_tab == "wifi":
        render_wifi_tab(draw, (pad, top, w - pad, h - pad), buttons)
    elif menu_tab == "update":
        render_update_view(draw, (pad, top, w - pad, h - pad), buttons)
    elif menu_tab == "phone":
        render_phone_view(draw, (pad, top, w - pad, h - pad))
    else:
        keys = [k for k, _, _, _ in BOOTH_SETTINGS]
        action_h = 70
        action_top = h - pad - action_h
        rows = (pad, top, w - pad, action_top - 6)
        # The button reminder only when there's room left over after all the rows.
        help_h = len(HELP_LINES) * 22 + 8
        rows_need = len(keys) * (MIN_ROW_H + 6)
        show_help = rows[3] - rows[1] - rows_need >= help_h
        if show_help:
            rows = (rows[0], rows[1], rows[2], rows[3] - help_h)
        bottom = _draw_setting_rows(draw, rows, keys, buttons, "booth")
        if show_help:
            y = bottom + 4
            help_font = _fit_font(draw, max(HELP_LINES, key=len), w - 2 * pad, 16, bold=False)
            for line in HELP_LINES:
                _draw_text_centered(draw, (pad, y, w - pad, y + 20), line, help_font, MENU_DIM)
                y += 22
        confirming = time.monotonic() < _shutdown_confirm_until
        half = (w - 3 * pad) // 2
        ubox = (pad, action_top, pad + half, action_top + action_h)
        _draw_key(draw, ubox, "UPDATE READY" if update_state == "available" else "UPDATES",
                  buttons, lambda: set_menu_tab("update"),
                  fill=MENU_DONE if update_state == "available" else MENU_ROW, size=22)
        sbox = (w - pad - half, action_top, w - pad, action_top + action_h)
        _draw_key(draw, sbox, "TAP AGAIN TO\nSHUT DOWN" if confirming else "SHUT DOWN",
                  buttons, press_shutdown, fill=MENU_DANGER, size=22)

    menu_buttons = buttons
    return img


def update_menu(force=False):
    global _menu_last_cam, _menu_last_ts
    now = time.monotonic()
    if not force and now - _menu_last_ts < 1.0 / LIVE_PREVIEW_FPS:
        return
    _menu_last_ts = now
    if menu_tab in PREVIEW_TABS and camera_running:
        try:
            _menu_last_cam = capture_preview_image()
        except TimeoutError:
            camera_failed("settings preview")
        except Exception as e:
            print(f"Menu preview capture failed: {e}")
    update_lcd(fast=True)


def screen_to_ui(px, py):
    """Maps a point on the panel to UI coordinates (undoes the rotation, scaling and bezel shift)."""
    if _lcd_xform is None:
        return None
    ox, oy, scale = _lcd_xform
    rx, ry = (px - ox) / scale, (py - oy) / scale
    w, h = full_ui_size()
    rotation = panel_rotation()
    if rotation == 0:
        x, y = rx, ry
    elif rotation == 180:
        x, y = w - rx, h - ry
    elif rotation == 90:
        x, y = w - ry, rx
    else:  # -90
        x, y = ry, h - rx
    return x - ui_inset(), y


def handle_tap(point):
    x, y = point
    print(f"Tap at {x:.0f},{y:.0f}")
    if menu_open:
        for (x0, y0, x1, y1), action in menu_buttons:
            if x0 <= x <= x1 and y0 <= y <= y1:
                action()
                if menu_open:
                    update_menu(force=True)
                return
    else:
        # Forgiving: half the gap around each button counts (the looks' tap areas are whole cells).
        pad = ICON_GAP // 2 if look() == "original" else 0
        for kind, (x0, y0, x1, y1) in corner_buttons():
            if x0 - pad <= x <= x1 + pad and y0 - pad <= y <= y1 + pad:
                {"menu": open_menu, "gallery": open_gallery, "camera": enter_creation_mode,
                 "fx": open_quick_effects, "layout": toggle_layout}[kind]()
                return
        if look() != "original":
            # The status piece under the strip (what to do next, the printer): printing from a phone.
            x0, y0, x1, y1 = _look_cache.get("status") or (0, 0, -1, -1)
            if PRINTER_WIFI and x0 <= x <= x1 and y0 <= y <= y1:
                open_phone_help()
            return
        # The printer in the top right corner: how to print from a phone.
        if PRINTER_WIFI and x >= ui_size()[0] - 110 and y <= 110:
            open_phone_help()


def handle_swipe(dx):
    """Finger moves left: the next one slides in from the right."""
    step = 1 if dx < 0 else -1
    print(f"Swipe {'left' if step > 0 else 'right'}")
    if menu_open:
        if menu_fullscreen and menu_tab in PREVIEW_TABS and date_entry is None:
            menu_focus_step(step)
            update_menu(force=True)
    elif mode == "browse":
        browse_step(step)
    else:
        next_frame_same_capacity(step)


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
threading.Thread(target=_printer_watch, daemon=True).start()
if PRINTER_WIFI:
    threading.Thread(target=_web_serve, daemon=True).start()

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

    if review_started is None or menu_open or gallery_open or _photo_show_img is not None:
        # The countdown waits while the settings menu or the review screen is open.
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


# Fully started: photobooth.service is Type=notify, and the updater waits for this.
sd_notify(b"READY=1")

_loop_errors = []
try:
    while True:
        try:
            if lcd is not None:
                # Touches act when the finger lifts, so a swipe isn't also a tap.
                for kind, value in next_gestures(pygame.event.get()):
                    if gallery_open:
                        wake_screen(camera=False)
                        handle_gallery_gesture((kind, value))
                        continue
                    end_photo_show()  # a touch skips the photo on show
                    if wake_screen():
                        continue  # a touch on a sleeping screen only wakes it
                    if kind == "tap":
                        handle_tap(value)
                    else:
                        handle_swipe(value)

            while not action_queue.empty():
                action, payload = action_queue.get()

                if action in ("short", "toggle_mode"):
                    end_photo_show()  # so does a press
                    # The press that wakes the screen only wakes it; one in the menu closes it.
                    if wake_screen() or menu_open or gallery_open:
                        close_menu()
                        close_gallery()
                        pending_short_time = None
                        short_press_count = 0
                        continue

                if action == "printer":
                    note_printer(payload)
                    continue
                if action == "printer_jobs":
                    note_print_jobs(payload)
                    continue
                if action == "print_cancelled":
                    note_print_cancelled(payload)
                    continue
                if action == "web_strip":
                    web_make_strip(payload)
                    continue
                if action == "print_done":
                    note_print_sent(payload)
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

            tick_photo_show()
            tick_printer()
            tick_review()
            tick_updates()
            tick_designs()
            tick_auto_off()

            if (
                settings["sleep"] is not None
                and not screen_asleep
                and auto_off_banner is None
                and not _print_busy.is_set()
                and not in_review()
                and time.monotonic() - last_activity > settings["sleep"]
            ):
                sleep_screen()

            if gallery_open and time.monotonic() - last_activity > GALLERY_IDLE_SECONDS:
                close_gallery()

            if menu_open:
                update_menu()
            elif gallery_open:
                update_gallery()
            else:
                update_live_slot_preview()
            watchdog_ping()
            time.sleep(0.03)
        except Exception:
            # One bad moment shouldn't end the event: log it and carry on. If errors keep
            # coming, exit so the service starts a fresh app.
            traceback.print_exc()
            now = time.monotonic()
            _loop_errors = [t for t in _loop_errors if now - t < 60] + [now]
            if len(_loop_errors) >= 5:
                print("Repeated errors; exiting so the service restarts the app.", flush=True)
                raise
            time.sleep(0.5)
except KeyboardInterrupt:
    # A normal stop (reboot, shutdown, update, Ctrl+C): keep a half-finished strip.
    save_partial_strip_before_shutdown()
    print("Exiting! Bye!")

finally:
    restore_backlight_if_dark()
    try:
        stop_camera()
    except Exception as e:
        print(f"Camera stop failed: {e}")
    pygame.quit()
