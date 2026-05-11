"""
Aurevia Pin Maker v14
- Keeps v13 logic: 9 layout variants per content_type, 27 total.
- NEW: block_style controls visual identity per Pinterest block/campaign.
- content_type = intent: retention, informative, money/money_post.
- block_style = visual identity: collagen_editorial, gut_health_fresh,
  sleep_night_calm, clean_supplements_minimal, fitness_energy.
- If block_style is missing, it is inferred from board/name.
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, HTMLResponse
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
import io, requests, os, base64

app = FastAPI(title="Aurevia Pin Maker v14")

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

# ─────────────────────────────────────────────────────────────────────────────
# 27 CORE LAYOUTS: 9 per content_type
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
        {"hook_y":44, "body_y":0,  "cta_y":78, "hook_size":86,  "body_size":0,  "hook_align":"center", "overlay":40, "grad_top":40, "grad_bot":220, "cta_style":"coral", "hook_box":True, "hook_box_color":"#E8501C", "hook_box_opacity":220},
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

# ─────────────────────────────────────────────────────────────────────────────
# BLOCK VISUAL IDENTITIES
# ─────────────────────────────────────────────────────────────────────────────

BLOCK_STYLES = {
    "collagen_editorial": {
        "overlay_boost": -8,
        "grad_top_boost": -20,
        "grad_bot_boost": -10,
        "cta_style_override": "coral",
        "body_color": (245, 232, 215),
        "hook_color": (255, 255, 255),
        "gradient_color": (40, 24, 18),
        "overlay_color": (35, 24, 18),
        "contrast": 1.03,
        "brightness": 1.03,
    },
    "gut_health_fresh": {
        "overlay_boost": -12,
        "grad_top_boost": -30,
        "grad_bot_boost": -16,
        "cta_style_override": "green",
        "body_color": (230, 246, 226),
        "hook_color": (255, 255, 255),
        "gradient_color": (20, 74, 48),
        "overlay_color": (16, 60, 38),
        "contrast": 1.05,
        "brightness": 1.05,
    },
    "sleep_night_calm": {
        "overlay_boost": 18,
        "grad_top_boost": 35,
        "grad_bot_boost": 30,
        "cta_style_override": "blue",
        "body_color": (225, 235, 250),
        "hook_color": (255, 255, 255),
        "gradient_color": (14, 28, 64),
        "overlay_color": (8, 18, 45),
        "contrast": 1.08,
        "brightness": 0.92,
    },
    "clean_supplements_minimal": {
        "overlay_boost": -25,
        "grad_top_boost": -45,
        "grad_bot_boost": -30,
        "cta_style_override": "dark",
        "body_color": (245, 240, 230),
        "hook_color": (255, 255, 255),
        "gradient_color": (45, 38, 32),
        "overlay_color": (35, 30, 26),
        "contrast": 1.02,
        "brightness": 1.08,
    },
    "fitness_energy": {
        "overlay_boost": 3,
        "grad_top_boost": 8,
        "grad_bot_boost": 14,
        "cta_style_override": "coral",
        "body_color": (255, 240, 220),
        "hook_color": (255, 255, 255),
        "gradient_color": (66, 42, 28),
        "overlay_color": (45, 32, 22),
        "contrast": 1.12,
        "brightness": 1.03,
    },
}

BOARD_TO_BLOCK_STYLE = {
    "collagenrefresh": "collagen_editorial",
    "options for skin and joint support": "collagen_editorial",
    "probiotic options for better digestion": "gut_health_fresh",
    "guthealthreset": "gut_health_fresh",
    "top magnesium picks for better sleep": "sleep_night_calm",
    "clean supplements that fit your routine": "clean_supplements_minimal",
    "fitness": "fitness_energy",
    "7-minute-workouts-women-over-40": "fitness_energy",
}

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

def fnt(bold, size):
    path = FB if bold else FR
    if path and size > 0:
        return ImageFont.truetype(path, size)
    return None

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

def crop_img(img, w=W, h=H):
    rw, rh = w/img.width, h/img.height
    ratio = max(rw, rh)
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

def add_box(img, color_rgba, box, radius=14):
    ov = Image.new("RGBA", img.size, (0,0,0,0))
    ImageDraw.Draw(ov).rounded_rectangle(box, radius=radius, fill=color_rgba)
    return Image.alpha_composite(img.convert("RGBA"),ov).convert("RGB")

def draw_text(draw, lines, f, y, color, align, left_x=65, shadow=True):
    for line in lines:
        bb = draw.textbbox((0,0),line,font=f)
        tw, lh = bb[2]-bb[0], bb[3]-bb[1]
        if align == "center":
            x = W//2 - tw//2
        elif align == "left":
            x = left_x
        else:
            x = W - left_x - tw
        if shadow:
            for ox,oy in [(-3,3),(3,3),(3,-3),(-3,-3),(0,4),(4,0),(-4,0),(0,-4)]:
                draw.text((x+ox,y+oy), line, font=f, fill=(0,0,0))
        draw.text((x,y), line, font=f, fill=color)
        y += lh + 6
    return y

def draw_pill(draw, text, f, cx, y, bg, fg, px, py, r):
    text = str(text or "").upper()
    bb = draw.textbbox((0,0),text,font=f)
    tw,th = bb[2]-bb[0], bb[3]-bb[1]
    bw,bh = tw+px*2, th+py*2
    x0 = cx - bw//2
    draw.rounded_rectangle([x0,y,x0+bw,y+bh], radius=r, fill=bg)
    draw.text((x0+px,y+py), text, font=f, fill=fg)
    return bh

def normalize_content_type(content_type):
    ct = str(content_type or "money_post").lower().strip()
    if ct == "money":
        return "money_post"
    if ct not in LAYOUTS:
        return "money_post"
    return ct

def get_layout(content_type, piece_number):
    ct = normalize_content_type(content_type)
    variants = LAYOUTS[ct]
    try:
        idx = (int(piece_number or 1) - 1) % len(variants)
    except Exception:
        idx = 0
    return variants[idx], idx + 1

def adjust_image_for_block(img, style):
    c = img
    if style.get("brightness", 1.0) != 1.0:
        c = ImageEnhance.Brightness(c).enhance(style["brightness"])
    if style.get("contrast", 1.0) != 1.0:
        c = ImageEnhance.Contrast(c).enhance(style["contrast"])
    return c

def render_pin(img, hook, body_text, cta, content_type, piece_number, block_style):
    L, layout_num = get_layout(content_type, piece_number)
    style = BLOCK_STYLES.get(block_style, BLOCK_STYLES["collagen_editorial"])

    c = crop_img(img)
    c = adjust_image_for_block(c, style)

    overlay = clamp(L["overlay"] + style.get("overlay_boost", 0), 0, 170)
    grad_top = clamp(L["grad_top"] + style.get("grad_top_boost", 0), 0, 255)
    grad_bot = clamp(L["grad_bot"] + style.get("grad_bot_boost", 0), 0, 255)

    gradient_color = style.get("gradient_color", (0,0,0))
    overlay_color = style.get("overlay_color", (0,0,0))

    c = add_overlay(c, overlay, overlay_color)

    if grad_top > 0:
        c = add_gradient(c, 0, int(H*0.42), 0, grad_top, color=gradient_color)
    if grad_bot > 0:
        c = add_gradient(c, int(H*0.58), H, 0, grad_bot, color=gradient_color)

    hook_y = int(H * L["hook_y"] / 100)
    hook_f = fnt(True, L["hook_size"])
    if hook_f:
        hook_lines = wrap_text(hook, hook_f, W-90, max_lines=2)
        if L.get("hook_box") and hook_lines:
            dummy_d = ImageDraw.Draw(Image.new("RGB",(1,1)))
            total_h = sum(
                dummy_d.textbbox((0,0),line,font=hook_f)[3] -
                dummy_d.textbbox((0,0),line,font=hook_f)[1] + 6
                for line in hook_lines
            ) + 34
            box_hex = L.get("hook_box_color", "#1a1a1a").lstrip("#")
            box_color = tuple(int(box_hex[i:i+2],16) for i in (0,2,4))
            c = add_box(
                c,
                (*box_color, L.get("hook_box_opacity", 180)),
                [38, hook_y-14, W-38, hook_y+total_h],
                radius=18
            )

        d = ImageDraw.Draw(c)
        draw_text(
            d,
            hook_lines,
            hook_f,
            hook_y,
            style.get("hook_color", (255,255,255)),
            L["hook_align"],
            shadow=True
        )

    d = ImageDraw.Draw(c)

    if body_text and L["body_size"] > 0 and L["body_y"] > 0:
        body_y = int(H * L["body_y"] / 100)
        body_f = fnt(False, L["body_size"])
        if body_f:
            body_lines = wrap_text(body_text, body_f, W-120, max_lines=2)
            draw_text(
                d,
                body_lines,
                body_f,
                body_y,
                style.get("body_color", (240,228,210)),
                L["hook_align"],
                shadow=True
            )

    cta_y = int(H * L["cta_y"] / 100)
    cta_style = style.get("cta_style_override") or L.get("cta_style", "coral")
    cs = CTA_STYLES.get(cta_style, CTA_STYLES["coral"])
    cta_f = fnt(True, 30)
    if cta_f:
        draw_pill(d, cta, cta_f, W//2, cta_y, cs["bg"], cs["fg"], cs["px"], cs["py"], cs["r"])

    buf = io.BytesIO()
    c.save(buf, "JPEG", quality=93, optimize=True)
    return buf.getvalue(), layout_num

@app.get("/health")
def health():
    return {
        "status": "ok",
        "version": "14.0",
        "layouts_per_type": 9,
        "total_layouts": 27,
        "block_styles": list(BLOCK_STYLES.keys())
    }

@app.get("/", response_class=HTMLResponse)
def index():
    return """
    <h1>Aurevia Pin Maker v14</h1>
    <p>27 layouts + block_style visual identities.</p>
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
        jpg, layout_used = render_pin(img, hook, body_text, cta, content_type, piece_number, block_style)
        out_name = fname.rsplit(".",1)[0] + "_pin.jpg"
        b64 = base64.b64encode(jpg).decode("utf-8")

        return JSONResponse({
            "status": "ok",
            "filename": out_name,
            "piece_number": piece_number,
            "content_type": content_type,
            "block_style": block_style,
            "layout_used": layout_used,
            "image_b64": b64,
            "size_bytes": len(jpg)
        })

    except Exception as e:
        return JSONResponse({"status":"error","error":str(e)}, status_code=500)
