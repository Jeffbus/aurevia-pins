"""
Aurevia Pin Maker v8
- 44 layouts total
- Mobile-first text control
- Auto layout selection by image type + content_type + hook length
- Reads CSV columns:
  piece_number, filename, content_type, hook, body_text, cta, template, drive_url

Run:
uvicorn main:app --reload
"""

from fastapi import FastAPI, UploadFile, File
from fastapi.responses import HTMLResponse, StreamingResponse
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import csv, io, zipfile, numpy as np, requests, os, textwrap
from typing import List, Callable, Dict, Tuple

app = FastAPI(title="Aurevia Pin Maker v8")

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────────────────────

W, H = 1000, 1500

FONT_CANDIDATES_BOLD = [
    "/usr/share/fonts/truetype/google-fonts/Poppins-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
]
FONT_CANDIDATES_REG = [
    "/usr/share/fonts/truetype/google-fonts/Poppins-Regular.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
]

def first_font(candidates):
    for p in candidates:
        if os.path.exists(p):
            return p
    return None

FB = first_font(FONT_CANDIDATES_BOLD)
FR = first_font(FONT_CANDIDATES_REG)

CORAL    = (232, 80, 28)
WHITE    = (255, 255, 255)
DARK     = (26, 26, 26)
CREAM    = (255, 248, 240)
LIGHT_BG = (250, 247, 243)
GRAY     = (96, 96, 96)
TERRA    = (180, 90, 50)
COCOA    = (62, 42, 32)
SAND     = (232, 212, 190)
BLUSH    = (252, 230, 220)
CHARCOAL = (28, 25, 22)
GOLD     = (196, 146, 72)
OLIVE    = (118, 126, 84)

# ─────────────────────────────────────────────────────────────────────────────
# UTILITIES
# ─────────────────────────────────────────────────────────────────────────────

def font(path, size):
    if path:
        return ImageFont.truetype(path, size)
    return ImageFont.load_default()

def load_from_url(url):
    if "drive.google.com" in url:
        if "/file/d/" in url:
            fid = url.split("/file/d/")[1].split("/")[0]
            url = f"https://drive.google.com/uc?export=download&id={fid}"
        elif "id=" in url:
            fid = url.split("id=")[1].split("&")[0]
            url = f"https://drive.google.com/uc?export=download&id={fid}"
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    return Image.open(io.BytesIO(r.content)).convert("RGB")

def load_from_bytes(data):
    return Image.open(io.BytesIO(data)).convert("RGB")

def crop(img, w=W, h=H):
    rw, rh = w / img.width, h / img.height
    ratio = max(rw, rh)
    nw, nh = int(img.width * ratio), int(img.height * ratio)
    img = img.resize((nw, nh), Image.LANCZOS)
    l, t = (nw - w) // 2, (nh - h) // 2
    return img.crop((l, t, l + w, t + h))

def wrap(text, fnt, max_w, max_lines=None):
    text = " ".join(str(text or "").replace("\n", " ").split())
    if not text:
        return []
    dummy = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    words, lines, cur = text.split(), [], ""
    for word in words:
        test = (cur + " " + word).strip()
        if dummy.textbbox((0, 0), test, font=fnt)[2] <= max_w:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = word
            if max_lines and len(lines) >= max_lines:
                break
    if cur and (not max_lines or len(lines) < max_lines):
        lines.append(cur)
    return lines

def text_h(draw, lines, fnt, lh=10):
    total = 0
    for line in lines:
        bb = draw.textbbox((0, 0), line, font=fnt)
        total += (bb[3] - bb[1]) + lh
    return total

def draw_lines(draw, lines, fnt, y, color, cx=W//2, shadow=False, lh=10, align="center"):
    for line in lines:
        bb = draw.textbbox((0, 0), line, font=fnt)
        tw = bb[2] - bb[0]
        if align == "center":
            x = cx - tw // 2
        elif align == "left":
            x = cx
        else:
            x = cx - tw
        if shadow:
            draw.text((x + 3, y + 3), line, font=fnt, fill=(0, 0, 0))
        draw.text((x, y), line, font=fnt, fill=color)
        y += (bb[3] - bb[1]) + lh
    return y

def overlay(img, fill=(0, 0, 0, 120), box=None, radius=0):
    ov = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    if box is None:
        box = [0, 0, W, H]
    if radius:
        d.rounded_rectangle(box, radius=radius, fill=fill)
    else:
        d.rectangle(box, fill=fill)
    return Image.alpha_composite(img.convert("RGBA"), ov).convert("RGB")

def grad(img, y0, y1, a0, a1, color=(0,0,0)):
    ov = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    span = max(y1 - y0, 1)
    for i in range(span):
        a = int(a0 + (a1 - a0) * i / span)
        d.rectangle([0, y0 + i, W, y0 + i + 1], fill=(*color, a))
    return Image.alpha_composite(img.convert("RGBA"), ov).convert("RGB")

def pill(draw, text, fnt, cx, y, bg, fg, px=48, py=16, r=32):
    text = str(text or "").upper()
    bb = draw.textbbox((0, 0), text, font=fnt)
    tw, th = bb[2]-bb[0], bb[3]-bb[1]
    bw, bh = tw + px*2, th + py*2
    x0 = cx - bw//2
    draw.rounded_rectangle([x0, y, x0+bw, y+bh], radius=r, fill=bg)
    draw.text((x0+px, y+py), text, font=fnt, fill=fg)
    return bh

def add_noise_texture(img, opacity=18):
    arr = np.random.normal(128, 30, (H, W)).clip(0, 255).astype(np.uint8)
    noise = Image.fromarray(arr, "L").convert("RGBA")
    noise.putalpha(opacity)
    return Image.alpha_composite(img.convert("RGBA"), noise).convert("RGB")

def analyze(img):
    img = crop(img)
    arr = np.array(img.convert("L"))
    third = H // 3
    zones = {
        "top": arr[:third, :],
        "middle": arr[third:2*third, :],
        "bottom": arr[2*third:, :]
    }
    scores = {}
    for name, zone in zones.items():
        gy = np.abs(np.diff(zone.astype(float), axis=0)).mean()
        gx = np.abs(np.diff(zone.astype(float), axis=1)).mean()
        scores[name] = 100 - (gy + gx) / 2

    best_zone = max(scores, key=scores.get)
    brightness = arr.mean()
    variance = arr.var()
    edges = (np.abs(np.diff(arr.astype(float), axis=0)).mean() +
             np.abs(np.diff(arr.astype(float), axis=1)).mean()) / 2

    if variance < 700:
        img_type = "minimal"
    elif brightness > 185:
        img_type = "bright"
    elif brightness < 85:
        img_type = "dark"
    elif edges > 23:
        img_type = "busy"
    else:
        img_type = "lifestyle"

    return best_zone, img_type, brightness, variance, edges

def smart_hook(hook, content_type="informative"):
    hook = " ".join(str(hook or "").replace("\n", " ").split())
    if not hook:
        return ""

    # Replace long blog-style phrases with sharper Pinterest-style wording.
    replacements = {
        "How To Make Exercise Feel Doable After 40": "Exercise After 40 Made Simple",
        "Short Workouts Vs Long Workouts After 40": "Short Workouts After 40",
        "Fitness After 40 Does Not Need To Be Extreme": "Fitness After 40 Made Simple",
        "Before You Buy 7 Minute Ageless Body Secret": "Before You Buy This",
        "The Workout Routine For Women Who Hate Long Workouts": "Hate Long Workouts?",
        "Don’t Start Another Workout Plan Before Reading This": "Read This Before Starting",
        "7 Minute Ageless Body Secret: What Comes Inside": "What Comes Inside?",
        "A Beginner-Friendly Workout Program To Compare": "Beginner-Friendly Routine",
        "Try A Short Fitness Routine Designed For Women Over 40": "Short Routine After 40",
    }
    if hook in replacements:
        hook = replacements[hook]

    max_words = 7
    if content_type == "retention":
        max_words = 6
    if content_type == "money_post":
        max_words = 7

    words = hook.split()
    if len(words) > max_words:
        hook = " ".join(words[:max_words])
    return hook

def smart_body(body, hook, layout_name=None):
    body = " ".join(str(body or "").replace("\n", " ").split())
    if not body:
        return ""

    # Body text is often the reason pins look cluttered.
    # Keep only one short line.
    max_words = 11
    if len(hook.split()) >= 6:
        max_words = 8
    if layout_name in {"layout_10", "layout_13", "layout_23", "layout_25", "layout_32", "layout_35", "layout_40"}:
        max_words = 0

    if max_words == 0:
        return ""

    words = body.split()
    if len(words) > max_words:
        body = " ".join(words[:max_words])
    return body

def text_mode(hook):
    n = len((hook or "").split())
    if n <= 4:
        return "huge"
    if n <= 7:
        return "medium"
    return "compact"

def safe_cta(cta):
    cta = " ".join(str(cta or "Learn More").split())
    cta_map = {
        "Read Before Buying": "Read First",
        "Check Availability": "See Details",
        "Compare It Here": "Compare",
        "View The Program": "View Program",
        "Get The Details": "Details",
    }
    return cta_map.get(cta, cta)

# ─────────────────────────────────────────────────────────────────────────────
# LAYOUT HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def full_bleed(img):
    return crop(img)

def split_top(img, split=0.62, bottom_color=WHITE):
    s = int(H * split)
    c = Image.new("RGB", (W, H), bottom_color)
    c.paste(crop(img, W, s), (0, 0))
    return c, s

def center_box(c, hook, body, cta, bg=(255,255,255,230), fg=DARK, accent=CORAL):
    d = ImageDraw.Draw(c)
    hf = font(FB, 92)
    bf = font(FR, 38)
    cf = font(FB, 36)
    hl = wrap(hook.upper(), hf, W-150, max_lines=3)
    bl = wrap(body, bf, W-180, max_lines=2)
    total = text_h(d, hl, hf, 8) + (text_h(d, bl, bf, 6) if bl else 0) + 100
    y0 = H//2 - total//2
    c = overlay(c, bg, [60, y0, W-60, y0+total], radius=28)
    d = ImageDraw.Draw(c)
    y = y0 + 34
    y = draw_lines(d, hl, hf, y, fg, lh=8)
    if bl:
        y += 12
        y = draw_lines(d, bl, bf, y, GRAY, lh=6)
    pill(d, cta, cf, W//2, y + 20, accent, WHITE, px=42, py=14, r=24)
    return c

# ─────────────────────────────────────────────────────────────────────────────
# LAYOUTS 1-24 UPDATED
# ─────────────────────────────────────────────────────────────────────────────

def layout_1(img, hook, body, cta):
    c = Image.new("RGB", (W,H), LIGHT_BG); d = ImageDraw.Draw(c)
    hf = font(FB, 98); bf = font(FR, 36)
    hl = wrap(hook.upper(), hf, W-90, 3)
    y = 58; y = draw_lines(d, hl, hf, y, DARK, lh=6)
    ih = 560; iy = min(y+35, 470); iw = W-100
    ph = crop(img, iw, ih)
    c.paste(Image.new("RGB",(iw+14,ih+14),(215,200,188)),(43,iy-7))
    c.paste(ph,(50,iy))
    d = ImageDraw.Draw(c)
    bl = wrap(body, bf, W-120, 2)
    y = iy + ih + 45
    if bl: y = draw_lines(d, bl, bf, y, GRAY, lh=6)
    pill(d, cta, font(FB,38), W//2, min(y+20,H-100), CORAL, WHITE)
    return c

def layout_2(img, hook, body, cta):
    c, s = split_top(img, .54, CORAL); d = ImageDraw.Draw(c)
    hf = font(FB, 100); bf = font(FR, 34)
    pill(d, cta, font(FB,32), W//2, s+28, CREAM, CORAL, px=36, py=12, r=20)
    hl = wrap(hook.upper(), hf, W-80, 3)
    y = s + 100
    y = draw_lines(d, hl, hf, y, WHITE, lh=4)
    bl = wrap(body, bf, W-100, 1)
    if bl: draw_lines(d, bl, bf, y+14, (255,225,210), lh=6)
    return c

def layout_3(img, hook, body, cta):
    c = full_bleed(img)
    c = grad(c, 0, 500, 40, 165)
    d = ImageDraw.Draw(c)
    hf = font(FB, 88); bf = font(FR, 38)
    hl = wrap(hook.upper(), hf, W-100, 3)
    y = 70
    y = draw_lines(d, hl, hf, y, WHITE, shadow=True, lh=8)
    bl = wrap(body, bf, W-100, 1)
    if bl: draw_lines(d, bl, bf, y+20, CREAM, shadow=True)
    pill(d, cta, font(FB,34), W//2, H-135, WHITE, DARK, px=42, py=14)
    return c

def layout_4(img, hook, body, cta):
    c, s = split_top(img, .64, WHITE); d = ImageDraw.Draw(c)
    d.rectangle([0,s,W,s+10], fill=CORAL)
    hf = font(FB, 82); bf = font(FR, 34)
    hl = wrap(hook.upper(), hf, W-90, 3)
    y = s+45
    y = draw_lines(d, hl, hf, y, DARK, lh=6)
    bl = wrap(body, bf, W-110, 1)
    if bl: draw_lines(d, bl, bf, y+10, GRAY)
    draw_lines(d, [cta.upper()], font(FB,34), H-85, CORAL)
    return c

def layout_5(img, hook, body, cta):
    c = full_bleed(img)
    c = grad(c, 0, 450, 15, 185)
    c = grad(c, H-260, H, 0, 190)
    d = ImageDraw.Draw(c)
    d.rectangle([40,40,W-40,H-40], outline=WHITE, width=4)
    hf = font(FB, 92)
    y = 70
    y = draw_lines(d, wrap(hook.upper(), hf, W-100, 3), hf, y, WHITE, shadow=True, lh=8)
    pill(d, cta, font(FB,34), W//2, H-125, (255,255,255), DARK, px=42, py=14)
    return c

def layout_6(img, hook, body, cta):
    c = full_bleed(img)
    zone, _, _, _, _ = analyze(c)
    y0 = 70 if zone != "top" else int(H*.58)
    d = ImageDraw.Draw(c)
    hf = font(FB, 88)
    hl = wrap(hook.upper(), hf, W-120, 3)
    box_h = text_h(d, hl, hf, 6) + 58
    c = overlay(c, (*CORAL,235), [45, y0, W-45, y0+box_h], radius=18)
    d = ImageDraw.Draw(c)
    draw_lines(d, hl, hf, y0+24, WHITE, lh=6)
    pill(d, cta, font(FB,34), W//2, H-128, WHITE, CORAL, px=44, py=14)
    return c

def layout_7(img, hook, body, cta):
    c = full_bleed(img)
    c = overlay(c, (0,0,0,70))
    return center_box(c, hook, body, cta, bg=(255,255,255,232), fg=DARK, accent=CORAL)

def layout_8(img, hook, body, cta):
    c = full_bleed(img); d = ImageDraw.Draw(c)
    zone, _, _, _, _ = analyze(c)
    top_y = 80 if zone != "top" else int(H*.55)
    pill(d, cta, font(FB,32), W//2, top_y, WHITE, DARK, px=45, py=12)
    hf = font(FB, 88)
    hl = wrap(hook.upper(), hf, W-100, 3)
    hook_y = top_y + 74
    hook_h = text_h(d, hl, hf, 6) + 48
    c = overlay(c, (*CORAL,238), [45, hook_y, W-45, hook_y+hook_h], radius=12)
    d = ImageDraw.Draw(c)
    draw_lines(d, hl, hf, hook_y+20, WHITE, lh=6)
    return c

def layout_9(img, hook, body, cta):
    c = Image.new("RGB",(W,H),LIGHT_BG); d = ImageDraw.Draw(c)
    d.ellipse([60,330,760,1030], fill=(232,80,28,45))
    ph = crop(img, 650, 720)
    mask = Image.new("L",(650,720),0)
    ImageDraw.Draw(mask).rounded_rectangle([0,0,650,720], radius=42, fill=255)
    c.paste(ph, (50,330), mask)
    hf = font(FB, 88)
    y = 65
    for line in wrap(hook.upper(), hf, 460, 3):
        bb = d.textbbox((0,0), line, font=hf)
        d.text((W-45-(bb[2]-bb[0]), y), line, font=hf, fill=CORAL)
        y += bb[3]-bb[1]+6
    pill(d, cta, font(FB,34), W-220, H-130, CORAL, WHITE, px=38, py=14, r=14)
    return c

def layout_10(img, hook, body, cta):
    c = full_bleed(img)
    c = overlay(c, (0,0,0,95))
    d = ImageDraw.Draw(c)
    hf = font(FB, 128)
    hl = wrap(hook.upper(), hf, W-60, 4)
    total = text_h(d, hl, hf, 6)
    y = H//2 - total//2 - 40
    draw_lines(d, hl, hf, y, CREAM, shadow=True, lh=6)
    pill(d, cta, font(FB,32), 260, H-130, WHITE, CORAL, px=38, py=14, r=8)
    return c

def layout_11(img, hook, body, cta):
    c, s = split_top(img, .48, LIGHT_BG); d = ImageDraw.Draw(c)
    hf = font(FB, 92)
    y = s + 45
    y = draw_lines(d, wrap(hook.upper(), hf, W-80, 3), hf, y, CORAL, lh=6)
    pill(d, cta + " >", font(FB,34), W//2, min(y+25,H-120), WHITE, CORAL, px=42, py=14)
    return c

def layout_12(img, hook, body, cta):
    c = Image.new("RGB",(W,H),BLUSH); d = ImageDraw.Draw(c)
    ph = crop(img, 760, 520)
    mask = Image.new("L",(760,520),0)
    ImageDraw.Draw(mask).ellipse([0,0,760,520], fill=255)
    c.paste(ph, (120,90), mask)
    hf = font(FB, 88)
    y = 680
    y = draw_lines(d, wrap(hook.upper(), hf, W-90, 3), hf, y, DARK, lh=6)
    pill(d, cta, font(FB,32), W//2, min(y+25,H-120), DARK, WHITE, px=42, py=14)
    return c

def layout_13(img, hook, body, cta):
    c = full_bleed(img)
    c = grad(c,0,520,0,170)
    d = ImageDraw.Draw(c)
    draw_lines(d, [cta.upper()], font(FB,30), 55, WHITE, shadow=True)
    hf = font(FB, 94)
    draw_lines(d, wrap(hook.upper(), hf, W-100, 3), hf, 120, WHITE, shadow=True, lh=8)
    return c

def layout_14(img, hook, body, cta):
    c = full_bleed(img)
    c = grad(c, int(H*.25), H, 0, 175)
    d = ImageDraw.Draw(c)
    d.text((W//2-90, 40), "joinaurevia.com", font=font(FR,26), fill=(255,255,255))
    hf = font(FB, 90)
    hl = wrap(hook.upper(), hf, W-100, 3)
    y = H//2 - text_h(d, hl, hf)//2
    draw_lines(d, hl, hf, y, WHITE, shadow=True, lh=8)
    pill(d, cta, font(FB,32), W//2, H-125, WHITE, DARK, px=42, py=14)
    return c

def layout_15(img, hook, body, cta):
    c = full_bleed(img); d = ImageDraw.Draw(c)
    d.rectangle([25,25,W-25,H-25], outline=WHITE, width=4)
    return center_box(c, hook, body, cta, bg=(255,255,255,228), fg=DARK, accent=CORAL)

def layout_16(img, hook, body, cta):
    c = Image.new("RGB",(W,H),CHARCOAL)
    top_h = int(H*.58)
    c.paste(crop(img,W//2,top_h//2),(0,0))
    c.paste(crop(img,W//2,top_h//2),(0,top_h//2))
    c.paste(crop(img,W//2,top_h),(W//2,0))
    d = ImageDraw.Draw(c)
    d.line([(W//2,0),(W//2,top_h)], fill=CHARCOAL, width=5)
    d.line([(0,top_h//2),(W//2,top_h//2)], fill=CHARCOAL, width=5)
    hf = font(FB, 84)
    y = top_h + 70
    y = draw_lines(d, wrap(hook.upper(), hf, W-80, 3), hf, y, WHITE, lh=6)
    pill(d, cta, font(FB,32), W//2, min(y+20,H-110), CREAM, DARK, px=42, py=14)
    return c

def layout_17(img, hook, body, cta):
    bg = TERRA
    c = Image.new("RGB",(W,H),bg)
    arch_w, arch_h = W-60, int(H*.62)
    ph = crop(img, arch_w, arch_h)
    mask = Image.new("L",(arch_w,arch_h),0); md=ImageDraw.Draw(mask)
    md.rectangle([0,arch_w//2,arch_w,arch_h], fill=255)
    md.ellipse([0,0,arch_w,arch_w], fill=255)
    c.paste(ph,(30,0),mask)
    d = ImageDraw.Draw(c)
    hf = font(FB, 88)
    y = arch_h + 45
    y = draw_lines(d, wrap(hook.upper(), hf, W-90, 3), hf, y, WHITE, lh=6)
    pill(d, cta, font(FB,32), W//2, min(y+20,H-115), WHITE, bg, px=42, py=14)
    return c

def layout_18(img, hook, body, cta):
    c, s = split_top(img, .60, CORAL); d = ImageDraw.Draw(c)
    pill(d, cta, font(FB,30), 220, s+35, WHITE, CORAL, px=34, py=12)
    hf = font(FB, 88)
    y = s + 105
    y = draw_lines(d, wrap(hook.upper(), hf, W-90, 3), hf, y, WHITE, lh=4)
    bl = wrap(body, font(FR,32), W-90, 1)
    if bl: draw_lines(d, bl, font(FR,32), y+10, (255,226,210))
    return c

def layout_19(img, hook, body, cta):
    c = full_bleed(img)
    c = overlay(c, (0,0,0,55))
    c = overlay(c, (*CORAL,210), [W-88,0,W,H])
    d = ImageDraw.Draw(c)
    hf = font(FB, 88)
    y = 90
    y = draw_lines(d, wrap(hook.upper(), hf, W-160, 3), hf, y, WHITE, cx=W-120, align="right", shadow=True, lh=8)
    d.rectangle([100,y+15,W-120,y+22], fill=CORAL)
    pill(d, cta, font(FB,32), W//2, H-125, WHITE, DARK, px=42, py=14)
    return c

def layout_20(img, hook, body, cta):
    c = full_bleed(img)
    c = overlay(c, (255,248,240,110))
    return center_box(c, hook, body, cta, bg=(230,210,190,220), fg=DARK, accent=CORAL)

def layout_21(img, hook, body, cta):
    c, s = split_top(img, .68, CHARCOAL); d = ImageDraw.Draw(c)
    hf = font(FB, 82)
    y = s + 48
    y = draw_lines(d, wrap(hook.upper(), hf, W-90, 3), hf, y, WHITE, lh=6)
    pill(d, cta, font(FB,32), W//2, min(y+18,H-110), WHITE, CHARCOAL, px=42, py=14)
    return c

def layout_22(img, hook, body, cta):
    c = full_bleed(img)
    c = overlay(c, (0,0,0,70))
    d = ImageDraw.Draw(c)
    y0 = 365
    c = overlay(c, (255,255,255,235), [70,y0,W-70,y0+650], radius=18)
    d = ImageDraw.Draw(c)
    hf = font(FB, 88)
    y = y0+55
    y = draw_lines(d, wrap(hook.upper(), hf, W-170, 3), hf, y, DARK, lh=8)
    pill(d, cta, font(FB,32), W//2, y+25, CORAL, WHITE, px=42, py=14)
    return c

def layout_23(img, hook, body, cta):
    c = full_bleed(img)
    c = grad(c,0,600,0,180); c = grad(c,H-260,H,0,170)
    d = ImageDraw.Draw(c)
    hf = font(FB, 104)
    y = 50
    y = draw_lines(d, wrap(hook.upper(), hf, W-80, 3), hf, y, WHITE, shadow=True, lh=6, align="left", cx=55)
    d.rectangle([55,y+15,W-55,y+23], fill=CORAL)
    pill(d, cta, font(FB,32), W//2, H-115, WHITE, DARK, px=42, py=14)
    return c

def layout_24(img, hook, body, cta):
    c = full_bleed(img)
    c = overlay(c, (0,0,0,55))
    d = ImageDraw.Draw(c)
    hf = font(FB, 88)
    y0 = 85
    c = overlay(c, (255,255,255,235), [55,y0,W-55,y0+76], radius=8)
    d = ImageDraw.Draw(c)
    draw_lines(d, [cta.upper()], font(FB,34), y0+20, DARK)
    y1 = y0+90
    hl = wrap(hook.upper(), hf, W-120, 3)
    h = text_h(d, hl, hf, 6)+50
    c = overlay(c, (*CORAL,238), [55,y1,W-55,y1+h], radius=8)
    d = ImageDraw.Draw(c)
    draw_lines(d, hl, hf, y1+24, WHITE, lh=6)
    return c

# ─────────────────────────────────────────────────────────────────────────────
# LAYOUTS 25-44 NEW
# ─────────────────────────────────────────────────────────────────────────────

def layout_25(img, hook, body, cta):
    c = full_bleed(img); c = overlay(c, (0,0,0,115)); d=ImageDraw.Draw(c)
    hf=font(FB,142); hl=wrap(hook.upper(),hf,W-80,3)
    y=H//2-text_h(d,hl,hf)//2-40
    draw_lines(d,hl,hf,y,WHITE,shadow=True,lh=2)
    pill(d,cta,font(FB,30),W//2,H-120,CORAL,WHITE,px=38,py=13)
    return c

def layout_26(img, hook, body, cta):
    c = Image.new("RGB",(W,H),CREAM); d=ImageDraw.Draw(c)
    ph=crop(img,W-120,760)
    c.paste(ph,(60,70))
    d.rectangle([60,70,W-60,830], outline=GOLD, width=5)
    hf=font(FB,88); y=900
    y=draw_lines(d,wrap(hook.upper(),hf,W-100,3),hf,y,COCOA,lh=6)
    pill(d,cta,font(FB,30),W//2,min(y+20,H-110),COCOA,WHITE,px=38,py=13)
    return c

def layout_27(img, hook, body, cta):
    c=full_bleed(img); c=grad(c,0,H,60,110,color=(80,40,20)); d=ImageDraw.Draw(c)
    c=overlay(c,(255,248,240,230),[0,930,W,1500])
    d=ImageDraw.Draw(c)
    hf=font(FB,86); y=970
    y=draw_lines(d,wrap(hook.upper(),hf,W-90,3),hf,y,DARK,lh=6)
    pill(d,cta,font(FB,30),W//2,y+16,CORAL,WHITE,px=38,py=13)
    return c

def layout_28(img, hook, body, cta):
    c=Image.new("RGB",(W,H),CHARCOAL)
    ph=crop(img,820,1080)
    c.paste(ph,(90,80))
    c=overlay(c,(0,0,0,35),[90,80,910,1160])
    d=ImageDraw.Draw(c)
    d.rectangle([70,60,930,1180],outline=GOLD,width=4)
    hf=font(FB,82); y=1200
    y=draw_lines(d,wrap(hook.upper(),hf,W-100,3),hf,y,WHITE,lh=6)
    pill(d,cta,font(FB,30),W//2,min(y+18,H-115),CREAM,DARK,px=38,py=13)
    return c

def layout_29(img, hook, body, cta):
    c=full_bleed(img); c=overlay(c,(255,255,255,80)); d=ImageDraw.Draw(c)
    x0=0; y0=0; x1=420; y1=H
    c=overlay(c,(*CORAL,232),[x0,y0,x1,y1])
    d=ImageDraw.Draw(c)
    hf=font(FB,74)
    y=110
    draw_lines(d,wrap(hook.upper(),hf,360,5),hf,y,WHITE,lh=8,align="left",cx=45)
    d.text((45,H-130),cta.upper(),font=font(FB,30),fill=WHITE)
    return c

def layout_30(img, hook, body, cta):
    c=Image.new("RGB",(W,H),BLUSH); d=ImageDraw.Draw(c)
    ph=crop(img,760,1000)
    mask=Image.new("L",(760,1000),0); ImageDraw.Draw(mask).rounded_rectangle([0,0,760,1000],radius=360,fill=255)
    c.paste(ph,(120,80),mask)
    c=overlay(c,(255,255,255,225),[60,1010,W-60,1360],radius=26)
    d=ImageDraw.Draw(c)
    hf=font(FB,72)
    y=1040
    y=draw_lines(d,wrap(hook.upper(),hf,W-120,3),hf,y,DARK,lh=6)
    draw_lines(d,[cta.upper()],font(FB,30),y+18,CORAL)
    return c

def layout_31(img, hook, body, cta):
    c=full_bleed(img).filter(ImageFilter.GaussianBlur(2))
    c=overlay(c,(255,248,240,150))
    ph=crop(img,700,850)
    c.paste(ph,(150,260))
    d=ImageDraw.Draw(c)
    d.rectangle([130,240,870,1130],outline=WHITE,width=8)
    hf=font(FB,76)
    y=80
    draw_lines(d,wrap(hook.upper(),hf,W-120,3),hf,y,DARK,lh=6)
    pill(d,cta,font(FB,30),W//2,H-135,CORAL,WHITE,px=38,py=13)
    return c

def layout_32(img, hook, body, cta):
    c=Image.new("RGB",(W,H),DARK)
    ph=crop(img,W,H)
    c.paste(ph,(0,0))
    c=overlay(c,(0,0,0,130))
    d=ImageDraw.Draw(c)
    hf=font(FB,118)
    hl=wrap(hook.upper(),hf,W-100,4)
    y=H//2-text_h(d,hl,hf)//2
    draw_lines(d,hl,hf,y,WHITE,shadow=True,lh=5)
    return c

def layout_33(img, hook, body, cta):
    c=full_bleed(img)
    c=overlay(c,(255,255,255,210),[70,70,W-70,410],radius=20)
    d=ImageDraw.Draw(c)
    hf=font(FB,78)
    y=105
    draw_lines(d,wrap(hook.upper(),hf,W-150,3),hf,y,DARK,lh=6)
    pill(d,cta,font(FB,30),W//2,H-125,CORAL,WHITE,px=38,py=13)
    return c

def layout_34(img, hook, body, cta):
    c=full_bleed(img); c=grad(c,H-650,H,0,210)
    d=ImageDraw.Draw(c)
    hf=font(FB,88)
    y=900
    y=draw_lines(d,wrap(hook.upper(),hf,W-90,3),hf,y,WHITE,shadow=True,lh=6)
    bl=wrap(body,font(FR,32),W-100,1)
    if bl: draw_lines(d,bl,font(FR,32),y+10,CREAM,shadow=True)
    pill(d,cta,font(FB,30),W//2,H-105,WHITE,DARK,px=38,py=13)
    return c

def layout_35(img, hook, body, cta):
    c=Image.new("RGB",(W,H),CORAL); d=ImageDraw.Draw(c)
    ph=crop(img,860,1020)
    c.paste(ph,(70,70))
    c=overlay(c,(255,255,255,235),[100,930,900,1320],radius=28)
    d=ImageDraw.Draw(c)
    hf=font(FB,82)
    y=960
    draw_lines(d,wrap(hook.upper(),hf,760,3),hf,y,DARK,lh=6)
    d.text((120,1270),cta.upper(),font=font(FB,30),fill=CORAL)
    return c

def layout_36(img, hook, body, cta):
    c=full_bleed(img)
    c=overlay(c,(0,0,0,65))
    c=overlay(c,(255,248,240,230),[70,95,930,255],radius=80)
    d=ImageDraw.Draw(c)
    d.text((130,145),cta.upper(),font=font(FB,34),fill=CORAL)
    hf=font(FB,92)
    y=920
    draw_lines(d,wrap(hook.upper(),hf,W-100,3),hf,y,WHITE,shadow=True,lh=6)
    return c

def layout_37(img, hook, body, cta):
    c=Image.new("RGB",(W,H),LIGHT_BG)
    ph1=crop(img,430,620); ph2=crop(img,430,620); ph3=crop(img,860,430)
    c.paste(ph1,(55,70)); c.paste(ph2,(515,70)); c.paste(ph3,(70,730))
    d=ImageDraw.Draw(c)
    hf=font(FB,76)
    y=1190
    y=draw_lines(d,wrap(hook.upper(),hf,W-90,3),hf,y,DARK,lh=6)
    draw_lines(d,[cta.upper()],font(FB,30),min(y+10,H-80),CORAL)
    return c

def layout_38(img, hook, body, cta):
    c=full_bleed(img)
    c=overlay(c,(255,255,255,180),[0,0,W,H])
    d=ImageDraw.Draw(c)
    d.polygon([(0,0),(W,0),(0,460)], fill=CORAL)
    hf=font(FB,82)
    draw_lines(d,wrap(hook.upper(),hf,W-120,3),hf,90,WHITE,lh=6)
    pill(d,cta,font(FB,30),W//2,H-125,CORAL,WHITE,px=38,py=13)
    return c

def layout_39(img, hook, body, cta):
    c=Image.new("RGB",(W,H),COCOA)
    ph=crop(img,W-100,H-260)
    c.paste(ph,(50,50))
    d=ImageDraw.Draw(c)
    c=overlay(c,(0,0,0,110),[50,50,W-50,H-210])
    d=ImageDraw.Draw(c)
    hf=font(FB,92)
    y=180
    draw_lines(d,wrap(hook.upper(),hf,W-120,3),hf,y,WHITE,shadow=True,lh=6)
    pill(d,cta,font(FB,30),W//2,H-145,CREAM,COCOA,px=38,py=13)
    return c

def layout_40(img, hook, body, cta):
    c=full_bleed(img)
    c=overlay(c,(255,248,240,230),[0,0,W,360])
    c=overlay(c,(*CORAL,238),[0,360,W,600])
    d=ImageDraw.Draw(c)
    d.text((60,85),cta.upper(),font=font(FB,34),fill=CORAL)
    hf=font(FB,86)
    draw_lines(d,wrap(hook.upper(),hf,W-120,2),hf,390,WHITE,lh=6)
    return c

def layout_41(img, hook, body, cta):
    c=Image.new("RGB",(W,H),SAND)
    ph=crop(img,760,760)
    mask=Image.new("L",(760,760),0); ImageDraw.Draw(mask).ellipse([0,0,760,760],fill=255)
    c.paste(ph,(120,120),mask)
    d=ImageDraw.Draw(c)
    hf=font(FB,82)
    y=960
    y=draw_lines(d,wrap(hook.upper(),hf,W-80,3),hf,y,DARK,lh=6)
    pill(d,cta,font(FB,30),W//2,min(y+18,H-115),DARK,WHITE,px=38,py=13)
    return c

def layout_42(img, hook, body, cta):
    c=full_bleed(img)
    c=overlay(c,(0,0,0,90))
    d=ImageDraw.Draw(c)
    d.line([90,120,90,1100],fill=CORAL,width=10)
    hf=font(FB,88)
    y=140
    draw_lines(d,wrap(hook.upper(),hf,W-180,4),hf,y,WHITE,shadow=True,lh=6,align="left",cx=120)
    d.text((120,H-130),cta.upper(),font=font(FB,32),fill=CREAM)
    return c

def layout_43(img, hook, body, cta):
    c=Image.new("RGB",(W,H),CREAM)
    ph=crop(img,900,680)
    c.paste(ph,(50,70))
    d=ImageDraw.Draw(c)
    for y in range(830,1500,34):
        d.line([0,y,W,y],fill=(235,220,205),width=2)
    hf=font(FB,84)
    y=860
    y=draw_lines(d,wrap(hook.upper(),hf,W-90,3),hf,y,DARK,lh=6)
    bl=wrap(body,font(FR,32),W-110,1)
    if bl: draw_lines(d,bl,font(FR,32),y+10,GRAY)
    draw_lines(d,[cta.upper()],font(FB,30),H-95,CORAL)
    return c

def layout_44(img, hook, body, cta):
    c=full_bleed(img)
    c=overlay(c,(255,255,255,80))
    d=ImageDraw.Draw(c)
    c=overlay(c,(255,255,255,235),[55,55,W-55,H-55],radius=40)
    ph=crop(img,780,760)
    c.paste(ph,(110,110))
    d=ImageDraw.Draw(c)
    hf=font(FB,80)
    y=930
    y=draw_lines(d,wrap(hook.upper(),hf,W-120,3),hf,y,DARK,lh=6)
    pill(d,cta,font(FB,30),W//2,min(y+18,H-115),CORAL,WHITE,px=38,py=13)
    return c

# ─────────────────────────────────────────────────────────────────────────────
# SMART SELECTION
# ─────────────────────────────────────────────────────────────────────────────

ALL_LAYOUTS: Dict[str, Callable] = {
    **{f"layout_{i}": globals()[f"layout_{i}"] for i in range(1,45)},
    "money_post": layout_8,
    "informative": layout_6,
    "retention": layout_23,
}

# Short hooks need bold layouts. Medium hooks use boxed split layouts.
LAYOUT_POOL = {
    ("informative", "huge"):   ["layout_25","layout_23","layout_10","layout_32","layout_40"],
    ("informative", "medium"): ["layout_6","layout_18","layout_23","layout_33","layout_34","layout_40"],
    ("informative", "compact"):["layout_1","layout_4","layout_11","layout_26","layout_43"],

    ("retention", "huge"):     ["layout_25","layout_32","layout_23","layout_42","layout_36"],
    ("retention", "medium"):   ["layout_23","layout_18","layout_6","layout_35","layout_40"],
    ("retention", "compact"):  ["layout_7","layout_15","layout_22","layout_30","layout_43"],

    ("money_post", "huge"):    ["layout_10","layout_25","layout_32","layout_39","layout_23"],
    ("money_post", "medium"):  ["layout_8","layout_18","layout_21","layout_35","layout_36","layout_40"],
    ("money_post", "compact"): ["layout_4","layout_1","layout_21","layout_28","layout_44"],
}

# Image-type adjustments. The app still chooses automatically, but with better design logic.
IMAGE_BONUS = {
    "minimal":   ["layout_23","layout_25","layout_18","layout_40","layout_41","layout_44"],
    "bright":    ["layout_6","layout_8","layout_18","layout_23","layout_33","layout_34"],
    "dark":      ["layout_10","layout_21","layout_28","layout_32","layout_39","layout_42"],
    "busy":      ["layout_7","layout_22","layout_30","layout_33","layout_40","layout_44"],
    "lifestyle": ["layout_6","layout_18","layout_23","layout_27","layout_35","layout_36"],
}

_used_layouts: List[str] = []

def smart_select_layout(img, content_type, hook, piece_number):
    global _used_layouts

    content_type = (content_type or "money_post").strip()
    if content_type not in ["informative", "retention", "money_post"]:
        content_type = "money_post"

    mode = text_mode(hook)
    _, img_type, _, _, _ = analyze(img)

    base = LAYOUT_POOL.get((content_type, mode), ["layout_8","layout_6","layout_23"])
    bonus = IMAGE_BONUS.get(img_type, [])
    candidates = []

    # Prioritize intersection of content/text logic + image logic.
    for l in bonus:
        if l in base and l not in candidates:
            candidates.append(l)
    for l in base + bonus:
        if l not in candidates:
            candidates.append(l)

    # Avoid repeating recently used layouts.
    for candidate in candidates:
        if candidate not in _used_layouts[-8:]:
            _used_layouts.append(candidate)
            _used_layouts = _used_layouts[-40:]
            return candidate, ALL_LAYOUTS[candidate]

    idx = int(piece_number or 0) % len(candidates)
    chosen = candidates[idx]
    _used_layouts.append(chosen)
    _used_layouts = _used_layouts[-40:]
    return chosen, ALL_LAYOUTS[chosen]

def apply_template(img, row):
    ct = row.get("content_type", "money_post").strip()
    template = row.get("template", "auto").strip()
    piece = row.get("piece_number", "0")

    hook = smart_hook(row.get("hook",""), ct)
    cta = safe_cta(row.get("cta","Learn More"))

    if template == "auto":
        layout_name, fn = smart_select_layout(img, ct, hook, piece)
    else:
        layout_name = template
        fn = ALL_LAYOUTS.get(template, layout_8)

    body = smart_body(row.get("body_text",""), hook, layout_name)

    out = fn(img, hook, body, cta)
    buf = io.BytesIO()
    out.save(buf, "JPEG", quality=93, optimize=True)
    return buf.getvalue(), layout_name, hook, body, cta

# ─────────────────────────────────────────────────────────────────────────────
# ROUTES
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {
        "status": "ok",
        "version": "8.0",
        "layouts": 44,
        "smart_selection": True,
        "mobile_text_control": True
    }

@app.get("/", response_class=HTMLResponse)
def index():
    return """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Aurevia Pin Maker v8</title>
<style>
*{box-sizing:border-box}
body{font-family:'Segoe UI',sans-serif;background:#f3f1ee;margin:0;padding:30px 16px}
.box{max-width:760px;margin:0 auto;background:#fff;border-radius:22px;padding:40px;box-shadow:0 8px 35px rgba(0,0,0,.10)}
h1{color:#E8501C;margin-top:0}
p{color:#666;margin-top:0;line-height:1.6}
.tabs{display:flex;gap:8px;margin-bottom:22px}
.tab{flex:1;padding:12px;border:2px solid #eee;border-radius:10px;cursor:pointer;text-align:center;font-weight:700;color:#666;background:#fff;font-size:14px}
.tab.active{border-color:#E8501C;color:#E8501C;background:#fff8f5}
.panel{display:none}.panel.active{display:block}
label{display:block;font-weight:700;margin:16px 0 6px;color:#222;font-size:14px}
input[type=file]{width:100%;padding:12px;border:2px dashed #e0e0e0;border-radius:10px;font-size:13px}
button{background:#E8501C;color:#fff;border:none;padding:15px;border-radius:32px;font-size:15px;font-weight:800;cursor:pointer;margin-top:20px;width:100%}
button:hover{background:#c43d10}
.note{background:#fff8f5;border-left:4px solid #E8501C;padding:14px 16px;border-radius:8px;margin-top:20px;font-size:12px;color:#555;line-height:1.8}
code{background:#f0f0f0;padding:2px 5px;border-radius:4px;font-size:11px}
.badge{background:#E8501C;color:#fff;font-size:11px;padding:4px 10px;border-radius:12px;margin-left:6px}
</style>
</head>
<body>
<div class="box">
<h1>Aurevia Pin Maker <span class="badge">v8 · 44 layouts</span></h1>
<p>Mobile-first Pinterest generator. It automatically shortens long hooks, reduces body text, and selects layouts by image type, content type, and hook length.</p>

<div class="tabs">
  <div class="tab active" onclick="showTab('url',this)">From URL / Drive</div>
  <div class="tab" onclick="showTab('upload',this)">Upload From PC</div>
</div>

<div id="tab-url" class="panel active">
  <form action="/process" method="post" enctype="multipart/form-data">
    <label>CSV with texts and drive_url</label>
    <input type="file" name="csv_file" accept=".csv" required>
    <button type="submit">Generate Pins</button>
  </form>
</div>

<div id="tab-upload" class="panel">
  <form action="/process-upload" method="post" enctype="multipart/form-data">
    <label>Base images</label>
    <input type="file" name="images" accept="image/*" multiple required>
    <label>CSV with texts</label>
    <input type="file" name="csv_file" accept=".csv" required>
    <button type="submit">Generate Pins</button>
  </form>
</div>

<div class="note">
  <b>Required CSV columns:</b>
  <code>piece_number, filename, content_type, hook, body_text, cta, template, drive_url</code><br>
  <b>content_type:</b> <code>informative</code> | <code>retention</code> | <code>money_post</code><br>
  <b>template:</b> use <code>auto</code> for smart selection, or <code>layout_1</code> to <code>layout_44</code> manually.<br>
  <b>Output:</b> ZIP with pins + <code>generation_report.csv</code> showing which layout was used.
</div>
</div>
<script>
function showTab(name, el) {
  document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));
  document.querySelectorAll('.panel').forEach(p=>p.classList.remove('active'));
  document.getElementById('tab-'+name).classList.add('active');
  el.classList.add('active');
}
</script>
</body>
</html>
"""

@app.post("/process")
async def process_urls(csv_file: UploadFile = File(...)):
    content = (await csv_file.read()).decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(content))
    buf = io.BytesIO()
    errors = []
    report_rows = [["piece_number","filename","content_type","layout_used","final_hook","final_body","final_cta"]]

    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for i, row in enumerate(reader, 1):
            fname = row.get("filename", f"pin_{i:03d}.jpg").strip() or f"pin_{i:03d}.jpg"
            try:
                url = row.get("drive_url","").strip()
                if not url:
                    raise ValueError("drive_url vacía")
                img = load_from_url(url)
                jpg, layout_used, final_hook, final_body, final_cta = apply_template(img, row)
                out_name = fname.rsplit(".",1)[0] + "_pin.jpg"
                zf.writestr(out_name, jpg)
                report_rows.append([row.get("piece_number",i), fname, row.get("content_type",""), layout_used, final_hook, final_body, final_cta])
            except Exception as e:
                errors.append(f"{fname}: {e}")

        report = io.StringIO()
        writer = csv.writer(report)
        writer.writerows(report_rows)
        zf.writestr("generation_report.csv", report.getvalue())

        if errors:
            zf.writestr("errors.txt", "\n".join(errors))

    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=aurevia_pins_v8.zip"}
    )

@app.post("/process-upload")
async def process_upload(images: List[UploadFile] = File(...), csv_file: UploadFile = File(...)):
    image_map = {}
    for upload in images:
        data = await upload.read()
        image_map[upload.filename] = data

    content = (await csv_file.read()).decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(content))
    buf = io.BytesIO()
    errors = []
    report_rows = [["piece_number","filename","content_type","layout_used","final_hook","final_body","final_cta"]]

    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for i, row in enumerate(reader, 1):
            fname = row.get("filename", f"pin_{i:03d}.jpg").strip()
            try:
                if fname not in image_map:
                    raise ValueError(f"Imagen '{fname}' no encontrada")
                img = load_from_bytes(image_map[fname])
                jpg, layout_used, final_hook, final_body, final_cta = apply_template(img, row)
                out_name = fname.rsplit(".",1)[0] + "_pin.jpg"
                zf.writestr(out_name, jpg)
                report_rows.append([row.get("piece_number",i), fname, row.get("content_type",""), layout_used, final_hook, final_body, final_cta])
            except Exception as e:
                errors.append(f"{fname}: {e}")

        report = io.StringIO()
        writer = csv.writer(report)
        writer.writerows(report_rows)
        zf.writestr("generation_report.csv", report.getvalue())

        if errors:
            zf.writestr("errors.txt", "\n".join(errors))

    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=aurevia_pins_v8.zip"}
    )
