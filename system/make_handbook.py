#!/usr/bin/env python3
"""Makes the booth's handbook: a PDF for the people the booth is given to.

    python3 system/make_handbook.py "Nick & Maddy" ~/Booth-Guide.pdf

Plain words, no computer knowledge needed. It describes the booth as it ships: the CLASSIC CAMERA
look, the printer network, the phone page. Change the text in PAGES below when a feature changes.
Drawn with Pillow (the only drawing library on a booth), so the pages are pictures: letter size,
150 dpi.
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

REPO = Path(__file__).resolve().parent.parent
FONTS = REPO / "ui" / "fonts"
DEJAVU = Path("/usr/share/fonts/truetype/dejavu")
W, H, DPI = 1275, 1650, 150          # US letter
MARGIN = 105
INK, DIM, RED, RULE, PANEL = (24, 24, 26), (95, 97, 102), (200, 30, 37), (190, 192, 196), (243, 243, 240)


def font(name, size):
    for folder in (FONTS, DEJAVU):
        try:
            return ImageFont.truetype(str(folder / name), size)
        except OSError:
            pass
    return ImageFont.load_default(size=size)


F_BRAND = lambda s: font("Yellowtail.ttf", s)
F_HEAD = lambda s: font("BarlowCondensed-Bold.ttf", s)
F_BODY = lambda s: font("DejaVuSans.ttf", s)
F_BOLD = lambda s: font("DejaVuSans-Bold.ttf", s)

# Each page: (title, [blocks]). A block is ("p", text), ("h", text), ("list", [items]),
# ("steps", [items]), ("table", [(left, right), ...]) or ("note", text).
PAGES = [
    ("The 30-second version", [
        ("steps", [
            "Plug the booth in (or switch on its power bank). It starts by itself in about half a minute.",
            "Stand in front of it and press the big button. It counts down 3, 2, 1 and takes a photo.",
            "Press again for each photo until the strip is full. The finished strip shows on the screen.",
            "Press once to keep it. It is saved on the booth.",
            "To print: tap ROLL on the left of the screen, then PRINT 2 COPIES.",
        ]),
        ("note", "Nothing you tap can break it. If you get lost, press the big button or tap DONE or BACK: "
                 "you are back at the camera."),
        ("h", "After the last photo"),
        ("table", [
            ("1 press", "Keep the strip"),
            ("2 presses", "Take the last photo again"),
            ("3 presses", "Try the same photos in another frame"),
            ("Do nothing", "It keeps the strip by itself after a minute"),
        ]),
        ("h", "Switching it off"),
        ("p", "Hold the big button for 6 seconds, or tap MENU and then the red power key. Wait for the "
              "screen to go dark before unplugging. The booth also switches itself off after an hour "
              "untouched; a half-finished strip is saved first."),
    ]),
    ("The big button", [
        ("p", "One button does everything you need at a party."),
        ("table", [
            ("1 press", "Take a photo"),
            ("2 quick presses", "Next frame design"),
            ("3 quick presses", "Switch between 3-photo and 4-photo strips"),
            ("Hold 1 second", "Look back through saved strips (hold again to return)"),
            ("5 quick presses", "Turn the screen a quarter turn"),
            ("Hold 6 seconds", "Switch the booth off"),
        ]),
        ("h", "While looking back through strips"),
        ("table", [
            ("1 press", "Older strip"),
            ("2 presses", "Newer strip"),
            ("3 presses", "Print it (two copies on one sheet)"),
        ]),
        ("note", "If the screen is suddenly sideways, someone pressed 5 times. Press 5 times again "
                 "until it is the right way up."),
    ]),
    ("The screen", [
        ("p", "The screen is a touchscreen. The strip you are making fills most of it; four round keys "
              "sit down the left."),
        ("table", [
            ("MENU", "Settings: camera, effects, the booth itself, WiFi"),
            ("ROLL", "Every strip saved on the booth: print, re-frame, delete"),
            ("EFFECTS", "Colour looks, date stamp, light leaks and other film effects"),
            ("FORMAT", "Photo strip, wide sheet or tall sheet"),
        ]),
        ("h", "Things to tap and swipe"),
        ("list", [
            "Swipe left or right on the strip: the next frame design.",
            "Tap the strip: DESIGNS, every design as a small picture. Tap one to see it close up, "
            "drag it to see the rest, ZOOM IN for detail, then USE THIS.",
            "Tap the star on a design to keep it in FAVOURITES.",
            "Tap a photo you have already taken: the booth asks KEEP IT or YES, RETAKE. Only that one "
            "photo is taken again.",
            "Tap the printer (top right): how to print from a phone.",
        ]),
        ("h", "Three shapes of print"),
        ("list", [
            "Photo strips: 2 x 6 inches, two on each sheet of paper. Cut the sheet down the middle.",
            "Wide sheet: one 6 x 4 inch picture with your photos in it.",
            "Tall sheet: one 4 x 6 inch picture.",
        ]),
    ]),
    ("Printing", [
        ("p", "The printer is a Canon SELPHY CP1500. It talks to the booth over the booth's own little "
              "WiFi network, so it works anywhere, with or without internet. Switch the printer on "
              "near the booth and wait about a minute."),
        ("table", [
            ("Green dot", "Printer ready"),
            ("Amber dot and a number", "Printing; the number is how many prints are waiting"),
            ("Red dot", "Printer off, out of range, or out of paper or ink (the screen says which)"),
        ]),
        ("h", "From ROLL"),
        ("list", [
            "PRINT 2 COPIES: the strip on screen, twice on one sheet.",
            "MIX 2 STRIPS: this strip on the left; swipe to another strip, then PRINT THESE 2.",
            "CHANGE FRAME: the same photos in a different frame. Swipe to try frames, then SAVE THIS FRAME.",
            "DELETE: tap it twice. The strip is gone for good.",
        ]),
        ("p", "A sheet takes about a minute. PRINT SENT means it is on its way; PRINT FINISHED means it "
              "has come out. Up to 3 prints can wait at once."),
        ("h", "Paper and ink"),
        ("p", "The printer uses Canon KP-108IN packs: postcard-size paper (4 x 6 inches) with its ink "
              "cartridge. Each cartridge prints exactly the paper that came with it. Load paper shiny "
              "side up. After printing, fold and tear off the two perforated tabs, then cut strips "
              "apart down the middle."),
    ]),
    ("Photos from a phone", [
        ("p", "Anyone can make a strip or sheet from photos already on their phone and print it."),
        ("steps", [
            "On the booth, tap the printer (top right). The screen shows the name and password of the "
            "booth's WiFi network.",
            "On the phone, join that WiFi network.",
            "In the phone's web browser, go to  10.42.0.1:8080",
            "Pick a design. LOOK shows it close up first.",
            "Tap each box to add a photo. Drag to move it, pinch to zoom.",
            "Tap Save & print (or Save, to keep it on the booth without printing).",
        ]),
        ("list", [
            "Effects: the row above the buttons puts the booth's colour looks, date stamp and film "
            "effects on the photos.",
            "Mix 2 strips: on a finished strip, tap Mix, make a second strip, then Print the 2 strips. "
            "Both print side by side on one sheet.",
            "Everything made from a phone is also saved in ROLL on the booth.",
        ]),
        ("note", "The phone is on the booth's network while it does this, so it may have no internet "
                 "for a moment. Go back to your usual WiFi afterwards."),
    ]),
    ("Make your own designs", [
        ("p", "Add your own frames for a birthday or a party. An AI chat app (ChatGPT, Claude, "
              "Gemini) draws one from your description."),
        ("steps", [
            "Open the phone page (previous page) and scroll to Want to design your own?",
            "Tap Copy instructions.",
            "Back on your usual WiFi, paste it into your AI app and write your idea at the end.",
            "It gives you one picture file (a PNG). Save it to your phone.",
            "Back on the booth's WiFi and the phone page, tap Add my design and pick the picture.",
            "The booth shows where the photos will go. Type a name and tap Add to the booth.",
        ]),
        ("p", "It is then on the booth for good, under MY DESIGNS. Updates never remove it."),
        ("h", "If the booth says Not added"),
        ("p", "It tells you why. Tell the AI app what the booth said and ask it to fix that."),
        ("h", "Deleting one of your designs"),
        ("p", "On the phone page, open it and tap Delete this design; or on the booth, open it in "
              "DESIGNS and tap DELETE twice. It goes to Recently deleted, where it can be restored, "
              "until you choose Delete forever or Empty trash. Designs that came with the booth "
              "cannot be deleted."),
    ]),
    ("Settings, WiFi and updates", [
        ("p", "Tap MENU. The arrows change a setting; changes are saved by themselves. DONE closes it."),
        ("table", [
            ("CAMERA", "Brightness, focus, lighting type, zoom, mirror"),
            ("EFFECTS", "Colour look, date stamp, light leaks, red spots, dust and streaks, random mix"),
            ("BOOTH", "Countdown length, screen-off time, automatic switch-off, the look of the "
                      "screens, updates, shut down"),
            ("WIFI", "Join your home WiFi, switch WiFi off, the printer network's name and password"),
        ]),
        ("h", "Joining your home WiFi"),
        ("p", "MENU, WIFI, tap your network, type the password, CONNECT. The booth only needs this for "
              "updates and to know the date. Photos, printing and the phone page all work without it."),
        ("h", "Updates"),
        ("p", "When the booth is on your WiFi and a new version is ready, it says: Your creator has "
              "gifted you with an update! Tap MENU, BOOTH, UPDATES, INSTALL UPDATE. It restarts by "
              "itself in under a minute. Your photos, settings and designs are kept. If a new version "
              "does not start properly, the booth goes back to the old one by itself."),
        ("h", "The date stamp"),
        ("p", "The booth knows the date only while it is on WiFi. Away from WiFi, set it by hand: "
              "MENU, EFFECTS, DATE STAMP, ON: MY DATE."),
    ]),
    ("If something is not right", [
        ("table", [
            ("The printer dot is red", "Is the printer on and close by? Give it a minute. Check paper "
                                       "and ink. Still red: switch the printer off and on."),
            ("Home WiFi will not connect", "Wait a minute or two: the booth restarts its own WiFi when "
                                           "it gets stuck. Still nothing: switch the booth off and on."),
            ("CAMERA NOT FOUND", "The camera's ribbon cable has come loose. Switch off, press the "
                                 "cable back in at both ends, switch on."),
            ("STORAGE LOW or FULL", "Delete old strips in ROLL. The top of ROLL shows how much room "
                                    "is left."),
        ]),
    ]),
    ("More fixes", [
        ("table", [
            ("The screen is sideways", "Press the big button 5 times, until it is right."),
            ("The screen is black", "It went to sleep or switched itself off. Tap it or press the "
                                    "button; if nothing happens, plug it in and wait half a minute."),
            ("The phone page will not open", "The phone must be on the booth's WiFi network, and the "
                                             "address is 10.42.0.1:8080 (typed in the address bar, "
                                             "not in a search box)."),
            ("It froze", "It restarts itself within a minute. Photos already taken are kept."),
        ]),
        ("note", "Always switch off with the button (hold 6 seconds) or the red power key, and wait "
                 "for the dark screen. Pulling the plug while it is working is the one thing that can "
                 "hurt it."),
    ]),
]


def wrap(draw, text, fnt, width):
    lines, line = [], ""
    for word in text.split():
        trial = f"{line} {word}".strip()
        if draw.textlength(trial, font=fnt) <= width or not line:
            line = trial
        else:
            lines.append(line)
            line = word
    return lines + ([line] if line else [])


def draw_page(number, total, title, blocks, who):
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    # Header: the brand in script, a red rule, the page title.
    d.text((MARGIN, 70), "Snapshot", font=F_BRAND(64), fill=INK)
    d.ellipse((MARGIN + 262, 98, MARGIN + 284, 120), fill=RED)
    d.text((W - MARGIN, 104), "YOUR PHOTO BOOTH", font=F_HEAD(30), fill=DIM, anchor="ra")
    d.line((MARGIN, 168, W - MARGIN, 168), fill=RED, width=5)
    d.text((MARGIN, 196), title.upper(), font=F_HEAD(76), fill=INK)
    y = 310
    body, lead = F_BODY(29), 44
    width = W - 2 * MARGIN
    for kind, content in blocks:
        if kind == "h":
            y += 18
            d.text((MARGIN, y), content.upper(), font=F_HEAD(42), fill=RED)
            y += 62
        elif kind == "p":
            for line in wrap(d, content, body, width):
                d.text((MARGIN, y), line, font=body, fill=INK)
                y += lead
            y += 16
        elif kind in ("list", "steps"):
            for n, item in enumerate(content, 1):
                if kind == "steps":
                    d.ellipse((MARGIN, y - 2, MARGIN + 42, y + 40), fill=INK)
                    d.text((MARGIN + 21, y + 19), str(n), font=F_BOLD(24), fill="white", anchor="mm")
                else:
                    d.ellipse((MARGIN + 12, y + 14, MARGIN + 24, y + 26), fill=RED)
                for line in wrap(d, item, body, width - 66):
                    d.text((MARGIN + 66, y), line, font=body, fill=INK)
                    y += lead
                y += 12
            y += 8
        elif kind == "table":
            left_w = max(d.textlength(a, font=F_BOLD(28)) for a, _ in content) + 36
            left_w = min(left_w, width * 0.42)
            for a, b in content:
                left = wrap(d, a, F_BOLD(28), left_w - 30)
                right = wrap(d, b, body, width - left_w - 30)
                rows = max(len(left), len(right))
                d.rectangle((MARGIN, y - 8, W - MARGIN, y + rows * lead + 6), fill=PANEL)
                for i, line in enumerate(left):
                    d.text((MARGIN + 18, y + i * lead), line, font=F_BOLD(28), fill=INK)
                for i, line in enumerate(right):
                    d.text((MARGIN + left_w + 12, y + i * lead), line, font=body, fill=INK)
                y += rows * lead + 20
            y += 10
        elif kind == "note":
            lines = wrap(d, content, body, width - 70)
            box_h = len(lines) * lead + 36
            d.rectangle((MARGIN, y, W - MARGIN, y + box_h), fill=PANEL)
            d.rectangle((MARGIN, y, MARGIN + 10, y + box_h), fill=RED)
            for i, line in enumerate(lines):
                d.text((MARGIN + 40, y + 18 + i * lead), line, font=body, fill=INK)
            y += box_h + 26
    if y > H - 110:
        raise SystemExit(f"Page {number} ({title}) runs off the paper by {y - (H - 110)} px: shorten it.")
    d.line((MARGIN, H - 96, W - MARGIN, H - 96), fill=RULE, width=2)
    d.text((MARGIN, H - 80), f"Made for {who}", font=F_BODY(22), fill=DIM)
    d.text((W - MARGIN, H - 80), f"{number} of {total}", font=F_BODY(22), fill=DIM, anchor="ra")
    return img


def cover(who, total):
    img = Image.new("RGB", (W, H), (20, 20, 20))
    d = ImageDraw.Draw(img)
    d.rectangle((70, 70, W - 70, H - 70), outline=(190, 192, 192), width=4)
    d.text((W / 2, 520), "Snapshot", font=F_BRAND(230), fill=(244, 242, 234), anchor="mm")
    d.ellipse((W / 2 + 360, 420, W / 2 + 404, 464), fill=RED)
    d.line((W / 2 - 150, 690, W / 2 + 150, 690), fill=RED, width=8)
    d.text((W / 2, 790), "YOUR PHOTO BOOTH", font=F_HEAD(96), fill=(244, 242, 234), anchor="mm")
    d.text((W / 2, 890), "THE HANDBOOK", font=F_HEAD(58), fill=(190, 192, 192), anchor="mm")
    d.text((W / 2, 1180), f"Made for {who}", font=F_BODY(40), fill=(244, 242, 234), anchor="mm")
    y = 1300
    for line in ("Press the big button. Smile.", "Everything else is in here if you need it."):
        d.text((W / 2, y), line, font=F_BODY(30), fill=(170, 172, 172), anchor="mm")
        y += 48
    return img


def main(args):
    if len(args) != 2:
        raise SystemExit(__doc__)
    who, out = args[0], Path(args[1]).expanduser()
    total = len(PAGES) + 1
    pages = [cover(who, total)]
    pages += [draw_page(n, total, title, blocks, who) for n, (title, blocks) in enumerate(PAGES, 2)]
    out.parent.mkdir(parents=True, exist_ok=True)
    pages[0].save(out, "PDF", resolution=DPI, save_all=True, append_images=pages[1:],
                  title="Snapshot photo booth: the handbook", author="Snapshot")
    print(f"{out}: {len(pages)} pages")


if __name__ == "__main__":
    main(sys.argv[1:])
