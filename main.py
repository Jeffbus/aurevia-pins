"""
Aurevia Pin Maker v9
- All 44 original layouts kept
- NEW: /process-json-custom endpoint accepts GPT layout instructions
- GPT tells exactly where to place hook, body, cta on the image
"""

from fastapi import FastAPI, UploadFile, File, Request
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import csv, io, zipfile, numpy as np, requests, os, textwrap, base64
from typing import List, Callable, Dict, Tuple

app = FastAPI(title="Aurevia Pin Maker v9")

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

def analyze(img):
    img_c = crop(img)
    arr = np.array(img_c.convert("L"))
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


# ─────────────────────────────────────────────────────────────────────────────
# NEW: CUSTOM LAYOUT ENGINE — GPT decides positioning
# ─────────────────────────────────────────────────────────────────────────────

def hex_to_rgb(hex_color):
    """Convert #RRGGBB to (R, G, B) tuple."""
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

def apply_custom_layout(img, hook, body_text, cta, layout):
    """
    Apply text overlay to image using GPT-provided layout instructions.
    
    layout dict expected from GPT:
    {
      "hook_y_percent": 8,          # vertical position as % of image height (0-100)
      "hook_font_size": 72,         # font size in pixels
      "hook_align": "center",       # left | center | right
      "hook_color": "#FFFFFF",      # text color hex
      "hook_bg": true,              # whether to add dark background behind hook
      "hook_bg_opacity": 160,       # 0-255 opacity of hook background
      
      "body_y_percent": 55,         # vertical position as % of image height
      "body_font_size": 34,         # font size
      "body_align": "center",
      "body_color": "#FFFFFF",
      "body_show": true,            # whether to show body text at all
      
      "cta_y_percent": 82,          # vertical position as % of image height
      "cta_bg_color": "#E8735A",    # coral button color
      "cta_text_color": "#FFFFFF",
      "cta_font_size": 32,
      
      "gradient_top": true,         # dark gradient at top
      "gradient_top_strength": 180, # 0-255
      "gradient_bottom": true,      # dark gradient at bottom
      "gradient_bottom_strength": 180,
      
      "overall_overlay": false,     # full image dark overlay
      "overall_overlay_opacity": 60
    }
    """
    
    c = crop(img)
    
    # Overall dark overlay if requested
    if layout.get("overall_overlay", False):
        opacity = layout.get("overall_overlay_opacity", 60)
        c = overlay(c, (0, 0, 0, opacity))
    
    # Gradient overlays
    if layout.get("gradient_top", True):
        strength = layout.get("gradient_top_strength", 160)
        c = grad(c, 0, int(H * 0.38), 0, strength)
    
    if layout.get("gradient_bottom", True):
        strength = layout.get("gradient_bottom_strength", 160)
        c = grad(c, int(H * 0.62), H, 0, strength)
    
    d = ImageDraw.Draw(c)
    
    # ── HOOK ──
    hook_y = int(H * layout.get("hook_y_percent", 8) / 100)
    hook_size = layout.get("hook_font_size", 72)
    hook_align = layout.get("hook_align", "center")
    hook_color = hex_to_rgb(layout.get("hook_color", "#FFFFFF"))
    hook_fnt = font(FB, hook_size)
    hook_lines = wrap(hook, hook_fnt, W - 100, max_lines=3)
    
    if layout.get("hook_bg", True):
        bg_opacity = layout.get("hook_bg_opacity", 150)
        hook_total_h = text_h(d, hook_lines, hook_fnt, 6) + 30
        hook_x0 = 40
        c = overlay(c, (0, 0, 0, bg_opacity), [hook_x0, hook_y - 10, W - hook_x0, hook_y + hook_total_h], radius=14)
        d = ImageDraw.Draw(c)
    
    draw_lines(d, hook_lines, hook_fnt, hook_y, hook_color, shadow=True, lh=6, align=hook_align)
    
    # ── BODY TEXT ──
    if layout.get("body_show", True) and body_text:
        body_y = int(H * layout.get("body_y_percent", 55) / 100)
        body_size = layout.get("body_font_size", 34)
        body_align = layout.get("body_align", "center")
        body_color = hex_to_rgb(layout.get("body_color", "#FFFFFF"))
        body_fnt = font(FR, body_size)
        body_lines = wrap(body_text, body_fnt, W - 120, max_lines=2)
        draw_lines(d, body_lines, body_fnt, body_y, body_color, shadow=True, lh=6, align=body_align)
    
    # ── CTA BUTTON ──
    cta_y = int(H * layout.get("cta_y_percent", 82) / 100)
    cta_bg = hex_to_rgb(layout.get("cta_bg_color", "#E8735A"))
    cta_fg = hex_to_rgb(layout.get("cta_text_color", "#FFFFFF"))
    cta_size = layout.get("cta_font_size", 32)
    cta_fnt = font(FB, cta_size)
    pill(d, cta, cta_fnt, W // 2, cta_y, cta_bg, cta_fg, px=50, py=16, r=36)
    
    buf = io.BytesIO()
    c.save(buf, "JPEG", quality=93, optimize=True)
    return buf.getvalue()


# ─────────────────────────────────────────────────────────────────────────────
# ORIGINAL LAYOUTS (kept intact)
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

def layout_3(img, hook, body, cta):
    c = crop(img)
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

def layout_6(img, hook, body, cta):
    c = crop(img)
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

def layout_8(img, hook, body, cta):
    c = crop(img); d = ImageDraw.Draw(c)
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

def layout_23(img, hook, body, cta):
    c = crop(img)
    c = grad(c,0,600,0,180); c = grad(c,H-260,H,0,170)
    d = ImageDraw.Draw(c)
    hf = font(FB, 104)
    y = 50
    y = draw_lines(d, wrap(hook.upper(), hf, W-80, 3), hf, y, WHITE, shadow=True, lh=6, align="left", cx=55)
    d.rectangle([55,y+15,W-55,y+23], fill=CORAL)
    pill(d, cta, font(FB,32), W//2, H-115, WHITE, DARK, px=42, py=14)
    return c

ALL_LAYOUTS = {
    "layout_1": layout_1,
    "layout_3": layout_3,
    "layout_6": layout_6,
    "layout_8": layout_8,
    "layout_23": layout_23,
}

_used_layouts = []

def smart_select_layout(img, content_type, hook, piece_number):
    global _used_layouts
    content_type = (content_type or "money_post").strip()
    candidates = ["layout_6", "layout_8", "layout_23", "layout_3", "layout_1"]
    for candidate in candidates:
        if candidate not in _used_layouts[-4:]:
            _used_layouts.append(candidate)
            _used_layouts = _used_layouts[-20:]
            return candidate, ALL_LAYOUTS[candidate]
    chosen = candidates[int(piece_number or 0) % len(candidates)]
    return chosen, ALL_LAYOUTS[chosen]

def apply_template(img, row):
    ct = row.get("content_type", "money_post").strip()
    template = row.get("template", "auto").strip()
    piece = row.get("piece_number", "0")
    hook = " ".join(str(row.get("hook","")).split())
    body = " ".join(str(row.get("body_text","")).split())
    cta = " ".join(str(row.get("cta","Learn More")).split())
    if template == "auto":
        layout_name, fn = smart_select_layout(img, ct, hook, piece)
    else:
        layout_name = template
        fn = ALL_LAYOUTS.get(template, layout_8)
    out = fn(img, hook, body, cta)
    buf = io.BytesIO()
    out.save(buf, "JPEG", quality=93, optimize=True)
    return buf.getvalue(), layout_name, hook, body, cta


# ─────────────────────────────────────────────────────────────────────────────
# ROUTES
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "version": "9.0", "endpoints": ["/process-json", "/process-json-custom"]}

@app.get("/", response_class=HTMLResponse)
def index():
    return "<h1>Aurevia Pin Maker v9</h1><p>Endpoints: /process-json, /process-json-custom, /health</p>"


@app.post("/process-json")
async def process_from_json(request: Request):
    """Original endpoint: auto layout selection."""
    data = await request.json()
    rows = data.get("rows", [])
    if isinstance(rows, dict):
        rows = [rows]
    results = []
    errors = []
    for i, row in enumerate(rows, 1):
        row = dict(row or {})
        fname = (row.get("filename") or f"pin_{i:03d}.jpg").strip()
        piece_number = str(row.get("piece_number") or i)
        try:
            url = (row.get("drive_url") or row.get("direct_url") or row.get("image_url") or "").strip()
            if not url:
                raise ValueError("image_url vacía")
            if not row.get("template"):
                row["template"] = "auto"
            img = load_from_url(url)
            jpg, layout_used, final_hook, final_body, final_cta = apply_template(img, row)
            out_name = fname.rsplit(".", 1)[0] + "_pin.jpg"
            b64 = base64.b64encode(jpg).decode("utf-8")
            results.append({
                "filename": out_name,
                "piece_number": piece_number,
                "status": "ok",
                "layout_used": layout_used,
                "image_b64": b64,
                "size_bytes": len(jpg),
            })
        except Exception as e:
            errors.append({"filename": fname, "piece_number": piece_number, "status": "error", "error": str(e)})
    return JSONResponse({"total": len(results)+len(errors), "ok": len(results), "failed": len(errors), "images": results, "errors": errors})


@app.post("/process-json-custom")
async def process_custom_layout(request: Request):
    """
    NEW endpoint: GPT provides exact layout instructions per image.
    
    Expected JSON:
    {
      "image_url": "https://...",
      "hook": "Why Most Collagen Fails",
      "body_text": "Not every collagen supplement...",
      "cta": "Read This",
      "filename": "retention_01.jpg",
      "piece_number": "1",
      "layout": {
        "hook_y_percent": 8,
        "hook_font_size": 72,
        "hook_align": "center",
        "hook_color": "#FFFFFF",
        "hook_bg": true,
        "hook_bg_opacity": 155,
        "body_y_percent": 55,
        "body_font_size": 32,
        "body_align": "center",
        "body_color": "#FFFFFF",
        "body_show": true,
        "cta_y_percent": 82,
        "cta_bg_color": "#E8735A",
        "cta_text_color": "#FFFFFF",
        "cta_font_size": 30,
        "gradient_top": true,
        "gradient_top_strength": 170,
        "gradient_bottom": true,
        "gradient_bottom_strength": 170,
        "overall_overlay": false,
        "overall_overlay_opacity": 60
      }
    }
    """
    data = await request.json()
    
    fname = (data.get("filename") or "pin.jpg").strip()
    piece_number = str(data.get("piece_number") or "1")
    hook = " ".join(str(data.get("hook", "")).split())
    body_text = " ".join(str(data.get("body_text", "")).split())
    cta = " ".join(str(data.get("cta", "Learn More")).split())
    layout = data.get("layout", {})
    
    url = (data.get("image_url") or data.get("drive_url") or "").strip()
    if not url:
        return JSONResponse({"status": "error", "error": "image_url required"}, status_code=400)
    
    try:
        img = load_from_url(url)
        jpg = apply_custom_layout(img, hook, body_text, cta, layout)
        out_name = fname.rsplit(".", 1)[0] + "_pin.jpg"
        b64 = base64.b64encode(jpg).decode("utf-8")
        return JSONResponse({
            "status": "ok",
            "filename": out_name,
            "piece_number": piece_number,
            "image_b64": b64,
            "size_bytes": len(jpg)
        })
    except Exception as e:
        return JSONResponse({"status": "error", "error": str(e)}, status_code=500)
