"""
Aurevia Pin Maker v15
- Based on v14.
- NEW: Creative Diversity Engine.
- Keeps: 27 base layouts, block_style identities, Google Drive URL handling.
- Adds:
  1) creative_mode rotation by piece_number
  2) composition diversity: zoom, blur backdrop, side panels, top/bottom panels, sticker CTA
  3) block-specific colors
  4) CTA variations by block and content_type
  5) stronger difference between retention, informative, and money pins

Input JSON accepted:
{
  "image_url": "...",
  "direct_url": "...",
  "drive_url": "...",
  "filename": "...",
  "piece_number": "1",
  "content_type": "retention|informative|money|money_post",
  "block_style": "sleep_night_calm|gut_health_fresh|collagen_editorial|clean_supplements_minimal|fitness_energy",
  "board": "...",
  "hook": "...",
  "body_text": "...",
  "cta": "..."
}
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, HTMLResponse
from PIL import Image, ImageDraw, ImageFont, ImageEnhance, ImageFilter
import io, requests, os, base64

app = FastAPI(title="Aurevia Pin Maker v15")

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

def fnt(bold, size):
    path = FB if bold else FR
    if path and size > 0:
        return ImageFont.truetype(path, size)
    return ImageFont.load_default()

# ─────────────────────────────────────────────────────────────────────────────
# BASE LAYOUTS: position logic
# ─────────────────────────────────────────────────────────────────────────────

LAYOUTS = {
    "retention": [
        {"hook_y":6,  "body_y":52, "cta_y":80, "hook_size":102, "body_size":32, "hook_align":"center", "overlay":80, "grad_top":200, "grad_bot":230, "cta_style":"coral", "hook_box":False},
        {"hook_y":8,  "body_y":38, "cta_y":82, "hook_size":88,  "body_size":30, "hook_align":"left",   "overlay":70, "grad_top":180, "grad_bot":220, "cta_style":"coral", "hook_box":False},
        {"hook_y":7,  "body_y":0,  "cta_y":83, "hook_size":96,  "body_size":0,  "hook_align":"center", "overlay":75, "grad_top":210, "grad_bot":240, "cta_style":"coral", "hook_box":True,  "hook_box_color":"#1a1a1a", "hook_box_opacity":180},
        {"hook_y":62, "body_y":0,  "cta_y":80, "hook_size":94,  "body_size":0,  "hook_align":"center", "overlay":60, "grad_top":80,  "grad_bot":230, "cta_style":"coral", "hook_box":False},
        {"hook_y":5,  "body_y":55, "cta_y":81, "hook_size":84,  "body_size":32, "hook_align":"right",  "overlay":72, "grad_top":190, "grad_bot":215, "cta_style":"coral", "hook_box":False},
        {"hook_y":38, "body_y":0,  "cta_y":78, "hook_size":110, "body_size":0,  "hook_align":"center", "overlay":85, "grad_top":160, "grad_bot":200, "cta_style":"white", "hook_box":False},
        {"hook_y":6,  "body_y":30, "cta_y":80, "hook_size":90,  "body_size":30, "hook_align":"center", "overlay":65, "grad_top":150, "grad_bot":220, "cta_style":"coral", "hook_box":True,  "hook_box_color":"#E8501C", "hook_box_opacity":230},
        {"hook_y":7,  "body_y":68, "cta_y":82, "hook_size":98,  "body_size":28, "hook_align":"left",   "overlay":70, "grad_top":200, "grad_bot":180, "cta_style":"coral", "hook_box":False},
        {"hook_y":42, "body_y":0,  "cta_y":79, "hook_size":88,  "body_size":0,  "hook_align":"center", "overlay":80, "grad_top":120, "grad_bot":210, "cta_style":"white", "hook_box":True,  "hook_box_color":"#000000", "hook_box_opacity":160},
    ],
    "informative": [
        {"hook_y":8,  "body_y":32, "cta_y":83, "hook_size":72,  "body_size":28, "hook_align":"left",   "overlay":20, "grad_top":160, "grad_bot":140, "cta_style":"dark",  "hook_box":False},
        {"hook_y":7,  "body_y":54, "cta_y":82, "hook_size":68,  "body_size":26, "hook_align":"center", "overlay":15, "grad_top":150, "grad_bot":130, "cta_style":"dark",  "hook_box":True,  "hook_box_color":"#FFFFFF", "hook_box_opacity":220},
        {"hook_y":64, "body_y":0,  "cta_y":55, "hook_size":70,  "body_size":0,  "hook_align":"left",   "overlay":25, "grad_top":100, "grad_bot":200, "cta_style":"coral", "hook_box":True,  "hook_box_color":"#FFFFFF", "hook_box_opacity":230},
        {"hook_y":6,  "body_y":50, "cta_y":80, "hook_size":74,  "body_size":28, "hook_align":"center", "overlay":20, "grad_top":140, "grad_bot":150, "cta_style":"white", "hook_box":False},
        {"hook_y":8,  "body_y":36, "cta_y":82, "hook_size":66,  "body_size":26, "hook_align":"right",  "overlay":18, "grad_top":155, "grad_bot":135, "cta_style":"dark",  "hook_box":False},
        {"hook_y":7,  "body_y":0,  "cta_y":81, "hook_size":78,  "body_size":0,  "hook_align":"center", "overlay":22, "grad_top":165, "grad_bot":145, "cta_style":"dark",  "hook_box":False},
        {"hook_y":6,  "body_y":55, "cta_y":82, "hook_size":70,  "body_size":27, "hook_align":"left",   "overlay":15, "grad_top":130, "grad_bot":140, "cta_style":"coral", "hook_box":True,  "hook_box_color":"#FFF8F0", "hook_box_opacity":225},
        {"hook_y":40, "body_y":60, "cta_y":80, "hook_size":72,  "body_size":26, "hook_align":"left",   "overlay":20, "grad_top":80,  "grad_bot":180, "cta_style":"white", "hook_box":False},
        {"hook_y":8,  "body_y":68, "cta_y":82, "hook_size":68,  "body_size":28, "hook_align":"center", "overlay":18, "grad_top":150, "grad_bot":160, "cta_style":"dark",  "hook_box":False},
    ],
    "money_post": [
        {"hook_y":6,  "body_y":54, "cta_y":81, "hook_size":86,  "body_size":30, "hook_align":"center", "overlay":35, "grad_top":60,  "grad_bot":210, "cta_style":"white", "hook_box":True,  "hook_box_color":"#E8501C", "hook_box_opacity":240},
        {"hook_y":7,  "body_y":36, "cta_y":82, "hook_size":80,  "body_size":30, "hook_align":"left",   "overlay":30, "grad_top":80,  "grad_bot":200, "cta_style":"coral", "hook_box":False},
        {"hook_y":38, "body_y":0,  "cta_y":78, "hook_size":96,  "body_size":0,  "hook_align":"center", "overlay":45, "grad_top":100, "grad_bot":210, "cta_style":"white", "hook_box":False},
        {"hook_y":8,  "body_y":52, "cta_y":82, "hook_size":84,  "body_size":32, "hook_align":"center", "overlay":35, "grad_top":70,  "grad_bot":215, "cta_style":"coral", "hook_box":False},
        {"hook_y":65, "body_y":0,  "cta_y":56, "hook_size":88,  "body_size":0,  "hook_align":"center", "overlay":40, "grad_top":50,  "grad_bot":230, "cta_style":"white", "hook_box":True,  "hook_box_color":"#1a1a1a", "hook_box_opacity":190},
        {"hook_y":6,  "body_y":56, "cta_y":80, "hook_size":82,  "body_size":28, "hook_align":"right",  "overlay":32, "grad_top":60,  "grad_bot":205, "cta_style":"coral", "hook_box":False},
        {"hook_y":7,  "body_y":30, "cta_y":82, "hook_size":78,  "body_size":30, "hook_align":"center", "overlay":30, "grad_top":65,  "grad_bot":200, "cta_style":"coral", "hook_box":True,  "hook_box_color":"#FFF0E0", "hook_box_opacity":225},
        {"hook_y":6,  "body_y":70, "cta_y":83, "hook_size":90,  "body_size":28, "hook_align":"left",   "overlay":35, "grad_top":70,  "grad_bot":210, "cta_style":"white", "hook_box":False},
        {"hook_y":44, "body_y":0,  "cta_y":78, "hook_size":86,  "body_size":0,  "hook_align":"center", "overlay":40, "grad_top":40,  "grad_bot":220, "cta_style":"coral", "hook_box":True,  "hook_box_color":"#E8501C", "hook_box_opacity":220},
    ],
}
LAYOUTS["money"] = LAYOUTS["money_post"]

CTA_STYLES = {
    "coral": {"bg": (232,80,28),   "fg": (255,255,255), "px":52, "py":16, "r":40},
    "white": {"bg": (255,255,255), "fg": (26,26,26),    "px":50, "py":15, "r":38},
    "dark":  {"bg": (26,26,26),    "fg": (255,255,255), "px":48, "py":14, "r":36},
    "blue":  {"bg": (58,92,145),   "fg": (255,255,255), "px":50, "py":15, "r":38},
    "green": {"bg": (74,128,92),   "fg": (255,255,255), "px":50, "py":15, "r":38},
    "cream": {"bg": (255,248,240), "fg": (45,38,32),    "px":50, "py":15, "r":38},
}

BLOCK_STYLES = {
    "collagen_editorial": {
        "overlay_boost": -8, "grad_top_boost": -20, "grad_bot_boost": -10,
        "cta_style_override": "coral", "body_color": (245,232,215), "hook_color": (255,255,255),
        "gradient_color": (40,24,18), "overlay_color": (35,24,18),
        "panel_color": (255,248,240), "panel_text": (35,24,18),
        "accent": (232,80,28), "contrast": 1.03, "brightness": 1.03,
    },
    "gut_health_fresh": {
        "overlay_boost": -12, "grad_top_boost": -30, "grad_bot_boost": -16,
        "cta_style_override": "green", "body_color": (230,246,226), "hook_color": (255,255,255),
        "gradient_color": (20,74,48), "overlay_color": (16,60,38),
        "panel_color": (238,250,231), "panel_text": (18,68,42),
        "accent": (74,128,92), "contrast": 1.05, "brightness": 1.05,
    },
    "sleep_night_calm": {
        "overlay_boost": 18, "grad_top_boost": 35, "grad_bot_boost": 30,
        "cta_style_override": "blue", "body_color": (225,235,250), "hook_color": (255,255,255),
        "gradient_color": (14,28,64), "overlay_color": (8,18,45),
        "panel_color": (230,237,250), "panel_text": (18,32,66),
        "accent": (58,92,145), "contrast": 1.08, "brightness": 0.92,
    },
    "clean_supplements_minimal": {
        "overlay_boost": -25, "grad_top_boost": -45, "grad_bot_boost": -30,
        "cta_style_override": "dark", "body_color": (245,240,230), "hook_color": (255,255,255),
        "gradient_color": (45,38,32), "overlay_color": (35,30,26),
        "panel_color": (255,255,250), "panel_text": (35,32,28),
        "accent": (26,26,26), "contrast": 1.02, "brightness": 1.08,
    },
    "fitness_energy": {
        "overlay_boost": 3, "grad_top_boost": 8, "grad_bot_boost": 14,
        "cta_style_override": "coral", "body_color": (255,240,220), "hook_color": (255,255,255),
        "gradient_color": (66,42,28), "overlay_color": (45,32,22),
        "panel_color": (255,242,230), "panel_text": (45,32,22),
        "accent": (232,80,28), "contrast": 1.12, "brightness": 1.03,
    },
}

BOARD_TO_BLOCK_STYLE = {
    "collagenrefresh": "collagen_editorial",
    "options for skin and joint support": "collagen_editorial",
    "probiotic options for better digestion": "gut_health_fresh",
    "guthealthreset": "gut_health_fresh",
    "top magnesium picks for better sleep": "sleep_night_calm",
    "clean supplements that fit your routine": "clean_supplements_minimal",
    "aurevia | wellness & fitness": "clean_supplements_minimal",
    "fitness": "fitness_energy",
}

CREATIVE_MODES = [
    "standard_gradient",
    "left_editorial_panel",
    "bottom_magazine_panel",
    "center_card",
    "split_soft_panel",
    "giant_hook_minimal",
    "sticker_cta",
    "dark_poster",
    "clean_label_card",
    "top_band_editorial",
    "floating_note",
    "zoom_blur_backdrop",
]

def clamp(value, low, high):
    return max(low, min(high, value))

def infer_block_style(data):
    explicit = str(data.get("block_style", "") or "").strip()
    if explicit:
        return explicit
    board = str(data.get("board", "") or "").strip().lower()
    for key, style in BOARD_TO_BLOCK_STYLE.items():
        if key in board:
            return style
    filename = str(data.get("filename", "") or "").strip().lower()
    if "sleep" in filename or "magnesium" in filename:
        return "sleep_night_calm"
    if "probiotic" in filename or "gut" in filename or "bloat" in filename:
        return "gut_health_fresh"
    if "clean" in filename or "mitolyn" in filename:
        return "clean_supplements_minimal"
    if "fitness" in filename or "workout" in filename:
        return "fitness_energy"
    return "collagen_editorial"

def normalize_content_type(content_type):
    ct = str(content_type or "money_post").lower().strip()
    if ct == "money":
        return "money_post"
    if ct not in LAYOUTS:
        return "money_post"
    return ct

def creative_mode_for(piece_number, content_type, block_style):
    try:
        n = int(piece_number or 1)
    except Exception:
        n = 1
    ct = normalize_content_type(content_type)
    # Offset per content type and block to avoid nearby sameness.
    offset = {"retention": 0, "informative": 4, "money_post": 8}.get(ct, 0)
    block_offset = {
        "collagen_editorial": 0,
        "gut_health_fresh": 2,
        "sleep_night_calm": 5,
        "clean_supplements_minimal": 7,
        "fitness_energy": 9,
    }.get(block_style, 0)
    return CREATIVE_MODES[(n - 1 + offset + block_offset) % len(CREATIVE_MODES)]

def get_layout(content_type, piece_number):
    ct = normalize_content_type(content_type)
    variants = LAYOUTS[ct]
    try:
        idx = (int(piece_number or 1) - 1) % len(variants)
    except Exception:
        idx = 0
    return variants[idx], idx + 1

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

def crop_img(img, w=W, h=H, zoom=1.0):
    rw, rh = w/img.width, h/img.height
    ratio = max(rw, rh) * zoom
    nw, nh = int(img.width*ratio), int(img.height*ratio)
    img = img.resize((nw,nh), Image.LANCZOS)
    l, t = (nw-w)//2, (nh-h)//2
    return img.crop((l,t,l+w,t+h))

def wrap_text(text, f, max_w, max_lines=None):
    text = " ".join(str(text or "").replace("\n"," ").split())
    if not text or not f:
        return []
    dummy = ImageDraw.Draw(Image.new("RGB",(1,1)))
    words, lines, cur = text.split(), [], ""
    for word in words:
        test = (cur+" "+word).strip()
        if dummy.textbbox((0,0),test,font=f)[2] <= max_w:
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

def add_gradient(img, y0, y1, a0, a1, color=(0,0,0)):
    ov = Image.new("RGBA", img.size, (0,0,0,0))
    d = ImageDraw.Draw(ov)
    span = max(y1-y0,1)
    for i in range(span):
        a = int(a0+(a1-a0)*i/span)
        d.rectangle([0,y0+i,W,y0+i+1], fill=(*color,a))
    return Image.alpha_composite(img.convert("RGBA"),ov).convert("RGB")

def add_overlay(img, opacity, color=(0,0,0)):
    if opacity <= 0:
        return img
    ov = Image.new("RGBA", img.size, (0,0,0,0))
    ImageDraw.Draw(ov).rectangle([0,0,W,H], fill=(*color, opacity))
    return Image.alpha_composite(img.convert("RGBA"),ov).convert("RGB")

def add_box(img, color_rgba, box, radius=18):
    ov = Image.new("RGBA", img.size, (0,0,0,0))
    ImageDraw.Draw(ov).rounded_rectangle(box, radius=radius, fill=color_rgba)
    return Image.alpha_composite(img.convert("RGBA"),ov).convert("RGB")

def add_panel(img, box, color, opacity=238, radius=0):
    return add_box(img, (*color, opacity), box, radius=radius)

def text_size(draw, text, font):
    bb = draw.textbbox((0,0), text, font=font)
    return bb[2]-bb[0], bb[3]-bb[1]

def draw_text(draw, lines, f, y, color, align, left_x=65, max_w=W-120, shadow=True):
    for line in lines:
        tw, lh = text_size(draw, line, f)
        if align == "center":
            x = W//2 - tw//2
        elif align == "left":
            x = left_x
        else:
            x = W - left_x - tw
        if shadow:
            for ox,oy in [(-3,3),(3,3),(0,4),(4,0)]:
                draw.text((x+ox,y+oy), line, font=f, fill=(0,0,0))
        draw.text((x,y), line, font=f, fill=color)
        y += lh + 7
    return y

def draw_pill(draw, text, f, cx, y, bg, fg, px, py, r):
    text = str(text or "").upper()
    tw, th = text_size(draw, text, f)
    bw, bh = tw+px*2, th+py*2
    x0 = cx - bw//2
    draw.rounded_rectangle([x0,y,x0+bw,y+bh], radius=r, fill=bg)
    draw.text((x0+px,y+py), text, font=f, fill=fg)
    return bh

def draw_pill_at(draw, text, f, x, y, bg, fg, px=42, py=14, r=32):
    text = str(text or "").upper()
    tw, th = text_size(draw, text, f)
    bw, bh = tw+px*2, th+py*2
    draw.rounded_rectangle([x,y,x+bw,y+bh], radius=r, fill=bg)
    draw.text((x+px,y+py), text, font=f, fill=fg)
    return bw, bh

def adjust_image_for_block(img, style):
    c = img
    if style.get("brightness", 1.0) != 1.0:
        c = ImageEnhance.Brightness(c).enhance(style["brightness"])
    if style.get("contrast", 1.0) != 1.0:
        c = ImageEnhance.Contrast(c).enhance(style["contrast"])
    return c

def draw_standard(c, L, style, hook, body_text, cta, ct):
    d = ImageDraw.Draw(c)
    hook_y = int(H * L["hook_y"] / 100)
    hook_f = fnt(True, L["hook_size"])
    hook_lines = wrap_text(hook, hook_f, W-90, max_lines=2)

    if L.get("hook_box") and hook_lines:
        total_h = len(hook_lines) * (L["hook_size"] + 10) + 28
        box_hex = L.get("hook_box_color", "#1a1a1a").lstrip("#")
        box_color = tuple(int(box_hex[i:i+2],16) for i in (0,2,4))
        c = add_box(c, (*box_color, L.get("hook_box_opacity", 180)), [38, hook_y-14, W-38, hook_y+total_h], radius=18)
        d = ImageDraw.Draw(c)

    draw_text(d, hook_lines, hook_f, hook_y, style["hook_color"], L["hook_align"], shadow=True)

    if body_text and L["body_size"] > 0 and L["body_y"] > 0:
        body_y = int(H * L["body_y"] / 100)
        body_f = fnt(False, L["body_size"])
        body_lines = wrap_text(body_text, body_f, W-120, max_lines=2)
        draw_text(d, body_lines, body_f, body_y, style["body_color"], L["hook_align"], shadow=True)

    cta_y = int(H * L["cta_y"] / 100)
    cs = CTA_STYLES.get(style.get("cta_style_override") or L["cta_style"], CTA_STYLES["coral"])
    draw_pill(d, cta, fnt(True, 30), W//2, cta_y, cs["bg"], cs["fg"], cs["px"], cs["py"], cs["r"])
    return c

def draw_left_editorial_panel(c, style, hook, body_text, cta):
    panel_w = 410
    c = add_panel(c, [0,0,panel_w,H], style["panel_color"], opacity=242, radius=0)
    d = ImageDraw.Draw(c)
    hf = fnt(True, 68)
    bf = fnt(False, 28)
    lines = wrap_text(hook, hf, panel_w-80, max_lines=3)
    y = 130
    for line in lines:
        d.text((48,y), line, font=hf, fill=style["panel_text"])
        y += 75
    body_lines = wrap_text(body_text, bf, panel_w-80, max_lines=3)
    y += 35
    for line in body_lines:
        d.text((48,y), line, font=bf, fill=style["panel_text"])
        y += 38
    cs = CTA_STYLES.get(style["cta_style_override"], CTA_STYLES["coral"])
    draw_pill_at(d, cta, fnt(True, 28), 48, H-170, cs["bg"], cs["fg"])
    return c

def draw_bottom_magazine_panel(c, style, hook, body_text, cta):
    panel_h = 470
    c = add_panel(c, [0,H-panel_h,W,H], style["panel_color"], opacity=244, radius=0)
    d = ImageDraw.Draw(c)
    hf = fnt(True, 76)
    bf = fnt(False, 30)
    y = H-panel_h+55
    hook_lines = wrap_text(hook, hf, W-110, max_lines=2)
    for line in hook_lines:
        tw,_ = text_size(d,line,hf)
        d.text((W//2-tw//2,y), line, font=hf, fill=style["panel_text"])
        y += 82
    body_lines = wrap_text(body_text, bf, W-140, max_lines=2)
    y += 10
    for line in body_lines:
        tw,_ = text_size(d,line,bf)
        d.text((W//2-tw//2,y), line, font=bf, fill=style["panel_text"])
        y += 40
    cs = CTA_STYLES.get(style["cta_style_override"], CTA_STYLES["coral"])
    draw_pill(d, cta, fnt(True, 28), W//2, H-110, cs["bg"], cs["fg"], 46, 14, 34)
    return c

def draw_center_card(c, style, hook, body_text, cta):
    x0,y0,x1,y1 = 80, 420, W-80, 1040
    c = add_panel(c, [x0,y0,x1,y1], style["panel_color"], opacity=236, radius=34)
    d = ImageDraw.Draw(c)
    hf = fnt(True, 74)
    bf = fnt(False, 30)
    y = y0+65
    hook_lines = wrap_text(hook, hf, x1-x0-90, max_lines=3)
    for line in hook_lines:
        tw,_ = text_size(d,line,hf)
        d.text((W//2-tw//2,y), line, font=hf, fill=style["panel_text"])
        y += 80
    body_lines = wrap_text(body_text, bf, x1-x0-90, max_lines=2)
    y += 20
    for line in body_lines:
        tw,_ = text_size(d,line,bf)
        d.text((W//2-tw//2,y), line, font=bf, fill=style["panel_text"])
        y += 42
    cs = CTA_STYLES.get(style["cta_style_override"], CTA_STYLES["coral"])
    draw_pill(d, cta, fnt(True, 28), W//2, y1-110, cs["bg"], cs["fg"], 46, 14, 34)
    return c

def draw_giant_hook_minimal(c, style, hook, body_text, cta):
    c = add_overlay(c, 75, style["overlay_color"])
    d = ImageDraw.Draw(c)
    hf = fnt(True, 118)
    lines = wrap_text(hook, hf, W-100, max_lines=2)
    y = 130
    draw_text(d, lines, hf, y, style["hook_color"], "left", left_x=55, shadow=True)
    cs = CTA_STYLES.get(style["cta_style_override"], CTA_STYLES["coral"])
    draw_pill_at(d, cta, fnt(True, 28), 55, H-155, cs["bg"], cs["fg"])
    return c

def draw_split_soft_panel(c, style, hook, body_text, cta):
    # translucent text panel on right side
    x0 = 500
    c = add_panel(c, [x0,80,W-35,H-80], style["panel_color"], opacity=228, radius=30)
    d = ImageDraw.Draw(c)
    hf = fnt(True, 58)
    bf = fnt(False, 27)
    y = 170
    hook_lines = wrap_text(hook, hf, W-x0-90, max_lines=3)
    for line in hook_lines:
        d.text((x0+45,y), line, font=hf, fill=style["panel_text"])
        y += 67
    body_lines = wrap_text(body_text, bf, W-x0-90, max_lines=3)
    y += 40
    for line in body_lines:
        d.text((x0+45,y), line, font=bf, fill=style["panel_text"])
        y += 38
    cs = CTA_STYLES.get(style["cta_style_override"], CTA_STYLES["coral"])
    draw_pill_at(d, cta, fnt(True, 26), x0+45, H-190, cs["bg"], cs["fg"])
    return c

def draw_sticker_cta(c, style, hook, body_text, cta):
    d = ImageDraw.Draw(c)
    hf = fnt(True, 82)
    hook_lines = wrap_text(hook, hf, W-120, max_lines=2)
    draw_text(d, hook_lines, hf, 80, style["hook_color"], "center", shadow=True)
    # sticker CTA at angle-like corner, but no actual rotation to keep quality
    cs = CTA_STYLES.get(style["cta_style_override"], CTA_STYLES["coral"])
    draw_pill_at(d, cta, fnt(True, 28), W-360, H-190, cs["bg"], cs["fg"], 48, 16, 40)
    if body_text:
        bf = fnt(False, 28)
        body_lines = wrap_text(body_text, bf, W-140, max_lines=2)
        draw_text(d, body_lines, bf, H-330, style["body_color"], "center", shadow=True)
    return c

def draw_dark_poster(c, style, hook, body_text, cta):
    c = add_overlay(c, 115, style["overlay_color"])
    c = add_gradient(c, 0, H, 40, 110, style["gradient_color"])
    d = ImageDraw.Draw(c)
    hf = fnt(True, 96)
    lines = wrap_text(hook, hf, W-110, max_lines=3)
    draw_text(d, lines, hf, 270, (255,255,255), "center", shadow=True)
    cs = CTA_STYLES.get(style["cta_style_override"], CTA_STYLES["coral"])
    draw_pill(d, cta, fnt(True, 30), W//2, H-170, cs["bg"], cs["fg"], 50, 15, 38)
    return c

def draw_clean_label_card(c, style, hook, body_text, cta):
    # Small editorial card, high whitespace.
    card = [70, 90, W-70, 460]
    c = add_panel(c, card, style["panel_color"], opacity=242, radius=28)
    d = ImageDraw.Draw(c)
    hf = fnt(True, 64)
    bf = fnt(False, 28)
    y = 135
    hook_lines = wrap_text(hook, hf, W-190, max_lines=2)
    for line in hook_lines:
        d.text((110,y), line, font=hf, fill=style["panel_text"])
        y += 70
    body_lines = wrap_text(body_text, bf, W-190, max_lines=2)
    y += 8
    for line in body_lines:
        d.text((110,y), line, font=bf, fill=style["panel_text"])
        y += 38
    cs = CTA_STYLES.get(style["cta_style_override"], CTA_STYLES["coral"])
    draw_pill(d, cta, fnt(True, 28), W//2, H-135, cs["bg"], cs["fg"], 46, 14, 34)
    return c

def draw_top_band_editorial(c, style, hook, body_text, cta):
    c = add_panel(c, [0,0,W,360], style["panel_color"], opacity=244, radius=0)
    d = ImageDraw.Draw(c)
    hf = fnt(True, 70)
    bf = fnt(False, 26)
    y = 55
    hook_lines = wrap_text(hook, hf, W-120, max_lines=2)
    for line in hook_lines:
        tw,_ = text_size(d,line,hf)
        d.text((W//2-tw//2,y), line, font=hf, fill=style["panel_text"])
        y += 75
    body_lines = wrap_text(body_text, bf, W-140, max_lines=2)
    y += 8
    for line in body_lines:
        tw,_ = text_size(d,line,bf)
        d.text((W//2-tw//2,y), line, font=bf, fill=style["panel_text"])
        y += 35
    cs = CTA_STYLES.get(style["cta_style_override"], CTA_STYLES["coral"])
    draw_pill(d, cta, fnt(True, 28), W//2, H-130, cs["bg"], cs["fg"], 46, 14, 34)
    return c

def draw_floating_note(c, style, hook, body_text, cta):
    # Two cards: hook and body separated.
    c = add_panel(c, [65,120,W-160,470], style["panel_color"], opacity=235, radius=30)
    c = add_panel(c, [170,900,W-65,1180], style["panel_color"], opacity=225, radius=30)
    d = ImageDraw.Draw(c)
    hf = fnt(True, 68)
    bf = fnt(False, 28)
    y = 165
    for line in wrap_text(hook, hf, W-290, max_lines=3):
        d.text((105,y), line, font=hf, fill=style["panel_text"])
        y += 75
    y = 945
    for line in wrap_text(body_text, bf, W-300, max_lines=3):
        d.text((210,y), line, font=bf, fill=style["panel_text"])
        y += 40
    cs = CTA_STYLES.get(style["cta_style_override"], CTA_STYLES["coral"])
    draw_pill(d, cta, fnt(True, 28), W//2, H-130, cs["bg"], cs["fg"], 46, 14, 34)
    return c

def make_blur_backdrop(original):
    bg = crop_img(original, zoom=1.18).filter(ImageFilter.GaussianBlur(12))
    fg = crop_img(original, zoom=0.86)
    # Center smaller foreground with rounded border
    canvas = bg
    x0, y0, x1, y1 = 90, 150, W-90, H-360
    fg = fg.resize((x1-x0, y1-y0), Image.LANCZOS)
    mask = Image.new("L", fg.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0,0,fg.size[0],fg.size[1]], radius=40, fill=255)
    canvas.paste(fg, (x0,y0), mask)
    return canvas

def render_pin(img, hook, body_text, cta, content_type, piece_number, block_style):
    ct = normalize_content_type(content_type)
    L, layout_num = get_layout(ct, piece_number)
    style = BLOCK_STYLES.get(block_style, BLOCK_STYLES["collagen_editorial"])
    mode = creative_mode_for(piece_number, ct, block_style)

    # Crop/creative base.
    if mode == "zoom_blur_backdrop":
        c = make_blur_backdrop(img)
    else:
        zoom = 1.08 if mode in ["dark_poster", "giant_hook_minimal"] else 1.0
        c = crop_img(img, zoom=zoom)

    c = adjust_image_for_block(c, style)

    overlay = clamp(L["overlay"] + style.get("overlay_boost", 0), 0, 170)
    grad_top = clamp(L["grad_top"] + style.get("grad_top_boost", 0), 0, 255)
    grad_bot = clamp(L["grad_bot"] + style.get("grad_bot_boost", 0), 0, 255)

    gradient_color = style.get("gradient_color", (0,0,0))
    overlay_color = style.get("overlay_color", (0,0,0))

    # Softer overlays for panel-based modes.
    if mode in ["left_editorial_panel", "bottom_magazine_panel", "center_card", "split_soft_panel", "clean_label_card", "top_band_editorial", "floating_note"]:
        overlay = max(0, overlay - 25)

    c = add_overlay(c, overlay, overlay_color)

    if mode not in ["left_editorial_panel", "center_card", "clean_label_card"]:
        if grad_top > 0:
            c = add_gradient(c, 0, int(H*0.42), 0, grad_top, color=gradient_color)
        if grad_bot > 0:
            c = add_gradient(c, int(H*0.58), H, 0, grad_bot, color=gradient_color)

    if mode == "left_editorial_panel":
        c = draw_left_editorial_panel(c, style, hook, body_text, cta)
    elif mode == "bottom_magazine_panel":
        c = draw_bottom_magazine_panel(c, style, hook, body_text, cta)
    elif mode == "center_card":
        c = draw_center_card(c, style, hook, body_text, cta)
    elif mode == "split_soft_panel":
        c = draw_split_soft_panel(c, style, hook, body_text, cta)
    elif mode == "giant_hook_minimal":
        c = draw_giant_hook_minimal(c, style, hook, body_text, cta)
    elif mode == "sticker_cta":
        c = draw_sticker_cta(c, style, hook, body_text, cta)
    elif mode == "dark_poster":
        c = draw_dark_poster(c, style, hook, body_text, cta)
    elif mode == "clean_label_card":
        c = draw_clean_label_card(c, style, hook, body_text, cta)
    elif mode == "top_band_editorial":
        c = draw_top_band_editorial(c, style, hook, body_text, cta)
    elif mode == "floating_note":
        c = draw_floating_note(c, style, hook, body_text, cta)
    elif mode == "zoom_blur_backdrop":
        c = draw_bottom_magazine_panel(c, style, hook, body_text, cta)
    else:
        c = draw_standard(c, L, style, hook, body_text, cta, ct)

    buf = io.BytesIO()
    c.save(buf, "JPEG", quality=93, optimize=True)
    return buf.getvalue(), layout_num, mode

@app.get("/health")
def health():
    return {
        "status": "ok",
        "version": "15.0",
        "layouts_per_type": 9,
        "total_layouts": 27,
        "creative_modes": CREATIVE_MODES,
        "block_styles": list(BLOCK_STYLES.keys())
    }

@app.get("/", response_class=HTMLResponse)
def index():
    return """
    <h1>Aurevia Pin Maker v15</h1>
    <p>27 layouts + block styles + creative diversity engine.</p>
    <p>POST /process-json-custom</p>
    """

@app.post("/process-json-custom")
async def process_custom(request: Request):
    data = await request.json()

    fname = (data.get("filename") or "pin.jpg").strip()
    piece_number = str(data.get("piece_number") or "1")
    hook = " ".join(str(data.get("hook","")).split())
    body_text = " ".join(str(data.get("body_text","")).split())
    cta = " ".join(str(data.get("cta","Learn More")).split())
    content_type = normalize_content_type(data.get("content_type","money_post"))
    block_style = infer_block_style(data)

    url = (
        data.get("image_url") or
        data.get("direct_url") or
        data.get("drive_url") or
        ""
    ).strip()

    if not url:
        return JSONResponse({"status":"error","error":"image_url/direct_url/drive_url required"}, status_code=400)

    try:
        img = load_from_url(url)
        jpg, layout_used, creative_mode = render_pin(
            img, hook, body_text, cta, content_type, piece_number, block_style
        )
        out_name = fname.rsplit(".",1)[0] + "_pin.jpg"
        b64 = base64.b64encode(jpg).decode("utf-8")

        return JSONResponse({
            "status": "ok",
            "filename": out_name,
            "piece_number": piece_number,
            "content_type": content_type,
            "block_style": block_style,
            "layout_used": layout_used,
            "creative_mode": creative_mode,
            "image_b64": b64,
            "size_bytes": len(jpg)
        })

    except Exception as e:
        return JSONResponse({"status":"error","error":str(e)}, status_code=500)
