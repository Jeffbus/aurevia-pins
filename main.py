"""
Aurevia Pin Maker v10
- /process-json-custom: GPT provides layout positions + content_type determines visual style
- 3 distinct visual styles: money_post, informative, retention
- money_post:  high contrast, coral hook bg, white CTA pill, conversion-focused
- informative: clean editorial, white card, dark CTA, educational tone
- retention:   dramatic, dark overlay, huge hook, stop-scroll energy
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, HTMLResponse
from PIL import Image, ImageDraw, ImageFont
import io, requests, os, base64, numpy as np

app = FastAPI(title="Aurevia Pin Maker v10")

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

# ─── Visual style presets per content_type ───────────────────────────────────
STYLE_PRESETS = {

    # MONEY POST — high contrast, coral hook background, white CTA, conversion
    "money_post": {
        "hook_font_size":      88,
        "hook_color":          (255, 255, 255),
        "hook_bg_color":       (232, 80, 28),    # coral box behind hook
        "hook_bg_opacity":     245,
        "hook_bg_radius":      16,
        "hook_align":          "center",
        "hook_shadow":         False,
        "body_font_size":      32,
        "body_color":          (255, 248, 240),
        "body_font":           "bold",
        "body_bg":             True,
        "body_bg_color":       (0, 0, 0),
        "body_bg_opacity":     130,
        "body_bg_radius":      10,
        "cta_bg":              (255, 255, 255),
        "cta_fg":              (232, 80, 28),
        "cta_font_size":       36,
        "cta_px":              56,
        "cta_py":              18,
        "cta_radius":          40,
        "gradient_top":        True,
        "gradient_top_str":    50,
        "gradient_bottom":     True,
        "gradient_bottom_str": 210,
        "overall_overlay":     True,
        "overall_opacity":     35,
        "border":              False,
    },

    # INFORMATIVE — clean editorial, white semi-transparent card, dark CTA
    "informative": {
        "hook_font_size":      68,
        "hook_color":          (26, 26, 26),
        "hook_bg_color":       (255, 255, 255),
        "hook_bg_opacity":     235,
        "hook_bg_radius":      12,
        "hook_align":          "left",
        "hook_shadow":         False,
        "body_font_size":      28,
        "body_color":          (55, 55, 55),
        "body_font":           "regular",
        "body_bg":             True,
        "body_bg_color":       (255, 255, 255),
        "body_bg_opacity":     215,
        "body_bg_radius":      10,
        "cta_bg":              (26, 26, 26),
        "cta_fg":              (255, 255, 255),
        "cta_font_size":       26,
        "cta_px":              44,
        "cta_py":              14,
        "cta_radius":          30,
        "gradient_top":        False,
        "gradient_top_str":    0,
        "gradient_bottom":     False,
        "gradient_bottom_str": 0,
        "overall_overlay":     False,
        "overall_opacity":     0,
        "border":              True,
        "border_color":        (255, 255, 255),
        "border_width":        7,
    },

    # RETENTION — dramatic, dark overlay, huge hook, stop-scroll, urgent CTA
    "retention": {
        "hook_font_size":      102,
        "hook_color":          (255, 255, 255),
        "hook_bg_color":       (0, 0, 0),
        "hook_bg_opacity":     0,              # no box — pure shadow effect
        "hook_bg_radius":      0,
        "hook_align":          "center",
        "hook_shadow":         True,
        "body_font_size":      34,
        "body_color":          (255, 230, 200),
        "body_font":           "bold",
        "body_bg":             False,
        "body_bg_color":       (0, 0, 0),
        "body_bg_opacity":     0,
        "body_bg_radius":      0,
        "cta_bg":              (232, 80, 28),
        "cta_fg":              (255, 255, 255),
        "cta_font_size":       34,
        "cta_px":              52,
        "cta_py":              17,
        "cta_radius":          40,
        "gradient_top":        True,
        "gradient_top_str":    200,
        "gradient_bottom":     True,
        "gradient_bottom_str": 230,
        "overall_overlay":     True,
        "overall_opacity":     80,
        "border":              False,
    },
}


# ─── Utilities ───────────────────────────────────────────────────────────────

def fnt(bold, size):
    path = FB if bold else FR
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

def line_heights(draw, lines, f, lh=8):
    total = 0
    for line in lines:
        bb = draw.textbbox((0, 0), line, font=f)
        total += (bb[3] - bb[1]) + lh
    return total

def draw_lines(draw, lines, f, y, color, align="center", shadow=False, lh=8, left_x=65):
    for line in lines:
        bb = draw.textbbox((0, 0), line, font=f)
        tw, lh_actual = bb[2] - bb[0], bb[3] - bb[1]
        x = (W // 2 - tw // 2) if align == "center" else left_x
        if shadow:
            for ox, oy in [(-2,2),(2,2),(0,3),(2,-1),(-2,-1),(0,4)]:
                draw.text((x+ox, y+oy), line, font=f, fill=(0,0,0))
        draw.text((x, y), line, font=f, fill=color)
        y += lh_actual + lh
    return y

def add_rect_overlay(img, color_rgba, box, radius=0):
    ov = Image.new("RGBA", img.size, (0,0,0,0))
    d = ImageDraw.Draw(ov)
    if radius:
        d.rounded_rectangle(box, radius=radius, fill=color_rgba)
    else:
        d.rectangle(box, fill=color_rgba)
    return Image.alpha_composite(img.convert("RGBA"), ov).convert("RGB")

def add_gradient(img, y0, y1, a0, a1, color=(0,0,0)):
    ov = Image.new("RGBA", img.size, (0,0,0,0))
    d = ImageDraw.Draw(ov)
    span = max(y1 - y0, 1)
    for i in range(span):
        a = int(a0 + (a1 - a0) * i / span)
        d.rectangle([0, y0+i, W, y0+i+1], fill=(*color, a))
    return Image.alpha_composite(img.convert("RGBA"), ov).convert("RGB")

def draw_pill_cta(draw, text, f, cx, y, bg, fg, px, py, r):
    text = str(text or "").upper()
    bb = draw.textbbox((0,0), text, font=f)
    tw, th = bb[2]-bb[0], bb[3]-bb[1]
    bw, bh = tw + px*2, th + py*2
    x0 = cx - bw//2
    draw.rounded_rectangle([x0, y, x0+bw, y+bh], radius=r, fill=bg)
    draw.text((x0+px, y+py), text, font=f, fill=fg)
    return bh

def analyze_image(img):
    arr = np.array(img.convert("L"))
    third = H // 3
    zones = {"top": arr[:third,:], "middle": arr[third:2*third,:], "bottom": arr[2*third:,:]}
    scores = {}
    for name, zone in zones.items():
        gy = np.abs(np.diff(zone.astype(float), axis=0)).mean()
        gx = np.abs(np.diff(zone.astype(float), axis=1)).mean()
        scores[name] = 100 - (gy + gx) / 2
    return max(scores, key=scores.get), arr.mean()


# ─── Main render ─────────────────────────────────────────────────────────────

def render_pin(img, hook, body_text, cta, content_type, layout):
    s = STYLE_PRESETS.get(content_type, STYLE_PRESETS["money_post"])
    c = crop_img(img)
    best_zone, brightness = analyze_image(c)

    # Full overlay
    if s["overall_overlay"] and s["overall_opacity"] > 0:
        c = add_rect_overlay(c, (0,0,0,s["overall_opacity"]), [0,0,W,H])

    # Gradients
    if s["gradient_top"] and s["gradient_top_str"] > 0:
        c = add_gradient(c, 0, int(H*0.42), 0, s["gradient_top_str"])
    if s["gradient_bottom"] and s["gradient_bottom_str"] > 0:
        c = add_gradient(c, int(H*0.58), H, 0, s["gradient_bottom_str"])

    # Border (informative)
    if s.get("border"):
        d_tmp = ImageDraw.Draw(c)
        bw = s.get("border_width", 6)
        d_tmp.rectangle([bw, bw, W-bw, H-bw],
                         outline=s.get("border_color",(255,255,255)), width=bw)

    d = ImageDraw.Draw(c)

    # ── Positions from GPT or smart defaults ──
    hook_y_pct = layout.get("hook_y_percent", 7)
    body_y_pct = layout.get("body_y_percent", 56)
    cta_y_pct  = layout.get("cta_y_percent", 82)

    # Informative: if subject is at top, flip text to bottom
    if content_type == "informative" and best_zone == "top":
        hook_y_pct = max(hook_y_pct, 56)
        body_y_pct = max(body_y_pct, 72)
        cta_y_pct  = max(cta_y_pct, 86)

    hook_y = int(H * hook_y_pct / 100)
    body_y = int(H * body_y_pct / 100)
    cta_y  = int(H * cta_y_pct  / 100)

    # ── HOOK ──
    hook_f     = fnt(True, s["hook_font_size"])
    hook_lines = wrap_text(hook, hook_f, W - 110, max_lines=3)
    hook_h     = line_heights(d, hook_lines, hook_f, 6) + 38

    if s["hook_bg_opacity"] > 0:
        pad = 22
        c = add_rect_overlay(c,
            (*s["hook_bg_color"], s["hook_bg_opacity"]),
            [38, hook_y - pad, W - 38, hook_y + hook_h],
            radius=s["hook_bg_radius"])
        d = ImageDraw.Draw(c)

    draw_lines(d, hook_lines, hook_f, hook_y,
               s["hook_color"], align=s["hook_align"],
               shadow=s["hook_shadow"], lh=6)

    # ── BODY TEXT ──
    if body_text and layout.get("body_show", True):
        body_bold = s["body_font"] == "bold"
        body_f    = fnt(body_bold, s["body_font_size"])
        body_lines = wrap_text(body_text, body_f, W - 130, max_lines=2)

        if body_lines:
            if s["body_bg"] and s["body_bg_opacity"] > 0:
                bh = line_heights(d, body_lines, body_f, 6) + 26
                c = add_rect_overlay(c,
                    (*s["body_bg_color"], s["body_bg_opacity"]),
                    [48, body_y - 12, W - 48, body_y + bh],
                    radius=s["body_bg_radius"])
                d = ImageDraw.Draw(c)

            draw_lines(d, body_lines, body_f, body_y,
                       s["body_color"], align=s["hook_align"],
                       shadow=s["hook_shadow"], lh=6)

    # ── CTA ──
    cta_f = fnt(True, s["cta_font_size"])
    draw_pill_cta(d, cta, cta_f, W//2, cta_y,
                  s["cta_bg"], s["cta_fg"],
                  s["cta_px"], s["cta_py"], s["cta_radius"])

    buf = io.BytesIO()
    c.save(buf, "JPEG", quality=93, optimize=True)
    return buf.getvalue()


# ─── Routes ──────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "version": "10.0",
            "styles": list(STYLE_PRESETS.keys())}

@app.get("/", response_class=HTMLResponse)
def index():
    return """<h1>Aurevia Pin Maker v10</h1>
<p>3 visual styles: money_post | informative | retention</p>
<p>Endpoints: POST /process-json-custom &nbsp;|&nbsp; GET /health</p>"""


@app.post("/process-json-custom")
async def process_custom(request: Request):
    """
    n8n + GPT pipeline endpoint.

    Input JSON:
    {
      "image_url":    "https://img.theapi.app/temp/...",
      "hook":         "Why Most Collagen Fails",
      "body_text":    "Not every collagen supplement...",
      "cta":          "Read This",
      "content_type": "retention",          <- money_post | informative | retention
      "filename":     "retention_01.jpg",
      "piece_number": "1",
      "layout": {                           <- from GPT vision analysis
        "hook_y_percent": 8,
        "body_y_percent": 54,
        "cta_y_percent":  82,
        "body_show":      true
      }
    }

    Returns:
    {
      "status":       "ok",
      "filename":     "retention_01_pin.jpg",
      "piece_number": "1",
      "content_type": "retention",
      "image_b64":    "...",
      "size_bytes":   123456
    }
    """
    data = await request.json()

    fname        = (data.get("filename") or "pin.jpg").strip()
    piece_number = str(data.get("piece_number") or "1")
    hook         = " ".join(str(data.get("hook", "")).split())
    body_text    = " ".join(str(data.get("body_text", "")).split())
    cta          = " ".join(str(data.get("cta", "Learn More")).split())
    content_type = str(data.get("content_type", "money_post")).strip()
    layout       = data.get("layout", {})

    url = (data.get("image_url") or data.get("drive_url") or "").strip()
    if not url:
        return JSONResponse({"status": "error", "error": "image_url is required"}, status_code=400)

    if content_type not in STYLE_PRESETS:
        content_type = "money_post"

    try:
        img = load_from_url(url)
        jpg = render_pin(img, hook, body_text, cta, content_type, layout)
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
