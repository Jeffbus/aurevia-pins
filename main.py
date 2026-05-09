"""
Aurevia Pin Maker v12
GPT decides the FULL design for each image:
- Text positions (y percent)
- Font sizes
- Text colors
- Overlay/gradient intensity
- CTA style (coral, white, dark)
- Hook alignment (center, left)
Railway just renders what GPT says.
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, HTMLResponse
from PIL import Image, ImageDraw, ImageFont
import io, requests, os, base64, numpy as np

app = FastAPI(title="Aurevia Pin Maker v12")

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
    if path:
        return ImageFont.truetype(path, size)
    return ImageFont.load_default()

def hex_to_rgb(h):
    h = h.lstrip('#')
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

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
    rw, rh = w / img.width, h / img.height
    ratio = max(rw, rh)
    nw, nh = int(img.width * ratio), int(img.height * ratio)
    img = img.resize((nw, nh), Image.LANCZOS)
    l, t = (nw - w) // 2, (nh - h) // 2
    return img.crop((l, t, l + w, t + h))

def wrap_text(text, f, max_w, max_lines=None):
    text = " ".join(str(text or "").replace("\n", " ").split())
    if not text:
        return []
    dummy = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    words, lines, cur = text.split(), [], ""
    for word in words:
        test = (cur + " " + word).strip()
        if dummy.textbbox((0, 0), test, font=f)[2] <= max_w:
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
    span = max(y1-y0, 1)
    for i in range(span):
        a = int(a0 + (a1-a0)*i/span)
        d.rectangle([0, y0+i, W, y0+i+1], fill=(*color, a))
    return Image.alpha_composite(img.convert("RGBA"), ov).convert("RGB")

def add_overlay(img, opacity):
    if opacity <= 0:
        return img
    ov = Image.new("RGBA", img.size, (0,0,0,0))
    ImageDraw.Draw(ov).rectangle([0,0,W,H], fill=(0,0,0,opacity))
    return Image.alpha_composite(img.convert("RGBA"), ov).convert("RGB")

def add_box(img, color_rgba, box, radius=0):
    ov = Image.new("RGBA", img.size, (0,0,0,0))
    d = ImageDraw.Draw(ov)
    if radius:
        d.rounded_rectangle(box, radius=radius, fill=color_rgba)
    else:
        d.rectangle(box, fill=color_rgba)
    return Image.alpha_composite(img.convert("RGBA"), ov).convert("RGB")

def draw_text_clean(draw, lines, f, y, color, align, shadow_strength, left_x=65):
    """Draw text with multi-layer shadow for legibility — no box needed."""
    for line in lines:
        bb = draw.textbbox((0,0), line, font=f)
        tw, lh = bb[2]-bb[0], bb[3]-bb[1]
        x = (W//2 - tw//2) if align == "center" else left_x
        if shadow_strength > 0:
            offsets = [(-3,3),(3,3),(3,-3),(-3,-3),(0,4),(4,0),(-4,0),(0,-4),(0,0)]
            for i, (ox, oy) in enumerate(offsets):
                if i < len(offsets)-1:
                    draw.text((x+ox, y+oy), line, font=f, fill=(0,0,0))
                else:
                    draw.text((x, y), line, font=f, fill=color)
        else:
            draw.text((x, y), line, font=f, fill=color)
        y += lh + 6
    return y

def draw_pill(draw, text, f, cx, y, bg, fg, px, py, r):
    text = str(text or "").upper()
    bb = draw.textbbox((0,0), text, font=f)
    tw, th = bb[2]-bb[0], bb[3]-bb[1]
    bw, bh = tw+px*2, th+py*2
    x0 = cx - bw//2
    draw.rounded_rectangle([x0, y, x0+bw, y+bh], radius=r, fill=bg)
    draw.text((x0+px, y+py), text, font=f, fill=fg)
    return bh

def analyze_image(img):
    arr = np.array(img.convert("L"))
    third = H // 3
    zones = {
        "top":    arr[:third,:],
        "middle": arr[third:2*third,:],
        "bottom": arr[2*third:,:]
    }
    scores = {}
    for name, zone in zones.items():
        gy = np.abs(np.diff(zone.astype(float), axis=0)).mean()
        gx = np.abs(np.diff(zone.astype(float), axis=1)).mean()
        scores[name] = 100 - (gy+gx)/2
    return max(scores, key=scores.get), arr.mean()


def render_pin(img, hook, body_text, cta, content_type, design):
    """
    Render pin using full design spec from GPT.
    
    design keys:
      hook_y_percent        int   0-100
      hook_font_size        int   60-110
      hook_color            str   hex e.g. "#FFFFFF"
      hook_align            str   "center" | "left"
      hook_bold             bool
      hook_shadow           int   0=none 1=light 2=heavy
      hook_box              bool  add semi-transparent box behind hook
      hook_box_color        str   hex
      hook_box_opacity      int   0-255
      
      body_show             bool
      body_y_percent        int   0-100
      body_font_size        int   24-40
      body_color            str   hex
      body_align            str   "center" | "left"
      body_shadow           int   0-2
      
      cta_y_percent         int   0-100
      cta_style             str   "coral" | "white" | "dark" | "outline"
      cta_font_size         int   24-36
      
      overlay_opacity       int   0-120   full image dark overlay
      grad_top              bool
      grad_top_strength     int   0-220
      grad_bottom           bool
      grad_bottom_strength  int   0-240
    """
    c = crop_img(img)
    best_zone, brightness = analyze_image(c)

    # ── Full overlay ──
    opacity = int(design.get("overlay_opacity", 40))
    c = add_overlay(c, opacity)

    # ── Gradients ──
    if design.get("grad_top", True):
        strength = int(design.get("grad_top_strength", 160))
        c = add_gradient(c, 0, int(H*0.42), 0, strength)

    if design.get("grad_bottom", True):
        strength = int(design.get("grad_bottom_strength", 190))
        c = add_gradient(c, int(H*0.58), H, 0, strength)

    # ── Hook box (optional) ──
    hook_y = int(H * float(design.get("hook_y_percent", 7)) / 100)
    hook_f = fnt(design.get("hook_bold", True), int(design.get("hook_font_size", 80)))
    hook_lines = wrap_text(hook, hook_f, W-90, max_lines=3)

    if design.get("hook_box", False) and hook_lines:
        box_color = hex_to_rgb(design.get("hook_box_color", "#000000"))
        box_opacity = int(design.get("hook_box_opacity", 140))
        dummy = ImageDraw.Draw(Image.new("RGB",(1,1)))
        total_h = sum(
            dummy.textbbox((0,0), l, font=hook_f)[3] -
            dummy.textbbox((0,0), l, font=hook_f)[1] + 6
            for l in hook_lines
        ) + 30
        c = add_box(c, (*box_color, box_opacity),
                    [38, hook_y-14, W-38, hook_y+total_h],
                    radius=14)

    d = ImageDraw.Draw(c)

    # ── Draw hook ──
    hook_color = hex_to_rgb(design.get("hook_color", "#FFFFFF"))
    hook_align = design.get("hook_align", "center")
    hook_shadow = int(design.get("hook_shadow", 2))
    hook_y = draw_text_clean(d, hook_lines, hook_f, hook_y,
                              hook_color, hook_align, hook_shadow)

    # ── Draw body ──
    if body_text and design.get("body_show", True):
        body_y = int(H * float(design.get("body_y_percent", 55)) / 100)
        body_f = fnt(False, int(design.get("body_font_size", 30)))
        body_lines = wrap_text(body_text, body_f, W-120, max_lines=2)
        body_color = hex_to_rgb(design.get("body_color", "#F0E8E0"))
        body_align = design.get("body_align", "center")
        body_shadow = int(design.get("body_shadow", 1))
        draw_text_clean(d, body_lines, body_f, body_y,
                        body_color, body_align, body_shadow)

    # ── CTA button ──
    cta_y   = int(H * float(design.get("cta_y_percent", 82)) / 100)
    cta_style = design.get("cta_style", "coral")
    cta_size  = int(design.get("cta_font_size", 30))
    cta_f = fnt(True, cta_size)

    CTA_STYLES = {
        "coral":   {"bg": (232,80,28),  "fg": (255,255,255)},
        "white":   {"bg": (255,255,255),"fg": (26,26,26)},
        "dark":    {"bg": (26,26,26),   "fg": (255,255,255)},
        "outline": {"bg": (0,0,0,0),    "fg": (255,255,255)},
    }
    cs = CTA_STYLES.get(cta_style, CTA_STYLES["coral"])
    draw_pill(d, cta, cta_f, W//2, cta_y, cs["bg"], cs["fg"], 50, 16, 38)

    buf = io.BytesIO()
    c.save(buf, "JPEG", quality=93, optimize=True)
    return buf.getvalue()


# ─── Routes ───────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "version": "12.0",
            "mode": "GPT decides full design per image"}

@app.get("/", response_class=HTMLResponse)
def index():
    return "<h1>Aurevia Pin Maker v12</h1><p>GPT decides full design. POST /process-json-custom</p>"


@app.post("/process-json-custom")
async def process_custom(request: Request):
    """
    Input:
    {
      "image_url":    "https://...",
      "hook":         "...",
      "body_text":    "...",
      "cta":          "...",
      "content_type": "money_post|informative|retention",
      "filename":     "pin.jpg",
      "piece_number": "1",
      "design": {
        "hook_y_percent": 8,
        "hook_font_size": 82,
        "hook_color": "#FFFFFF",
        "hook_align": "center",
        "hook_bold": true,
        "hook_shadow": 2,
        "hook_box": false,
        "hook_box_color": "#000000",
        "hook_box_opacity": 140,
        "body_show": true,
        "body_y_percent": 55,
        "body_font_size": 30,
        "body_color": "#F0E8E0",
        "body_align": "center",
        "body_shadow": 1,
        "cta_y_percent": 82,
        "cta_style": "coral",
        "cta_font_size": 30,
        "overlay_opacity": 40,
        "grad_top": true,
        "grad_top_strength": 160,
        "grad_bottom": true,
        "grad_bottom_strength": 200
      }
    }
    """
    data = await request.json()

    fname        = (data.get("filename") or "pin.jpg").strip()
    piece_number = str(data.get("piece_number") or "1")
    hook         = " ".join(str(data.get("hook", "")).split())
    body_text    = " ".join(str(data.get("body_text", "")).split())
    cta          = " ".join(str(data.get("cta", "Learn More")).split())
    content_type = str(data.get("content_type", "money_post")).strip()
    design       = data.get("design", {})

    url = (data.get("image_url") or data.get("drive_url") or "").strip()
    if not url:
        return JSONResponse({"status": "error", "error": "image_url required"}, status_code=400)

    try:
        img = load_from_url(url)
        jpg = render_pin(img, hook, body_text, cta, content_type, design)
        out_name = fname.rsplit(".", 1)[0] + "_pin.jpg"
        b64 = base64.b64encode(jpg).decode("utf-8")
        return JSONResponse({
            "status":       "ok",
            "filename":     out_name,
            "piece_number": piece_number,
            "content_type": content_type,
            "image_b64":    b64,
            "size_bytes":   len(jpg)
        })
    except Exception as e:
        return JSONResponse({"status": "error", "error": str(e)}, status_code=500)
