"""
Aurevia Pin Maker v13
- 9 layout variants per content_type (27 total)
- Layout chosen by piece_number — guaranteed variety, no repeats nearby
- No GPT needed for positioning — Railway handles it all
- 3 distinct visual styles: money_post, informative, retention
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, HTMLResponse
from PIL import Image, ImageDraw, ImageFont
import io, requests, os, base64, numpy as np

app = FastAPI(title="Aurevia Pin Maker v13")

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

# ─── 9 layout variants per content_type ──────────────────────────────────────
# Each variant defines: hook_y, body_y, cta_y, hook_size, body_size,
# hook_align, overlay, grad_top_str, grad_bot_str, cta_style

LAYOUTS = {
    "retention": [
        # 1. Hook top center, body middle, CTA bottom — dramatic
        {"hook_y":6,  "body_y":52, "cta_y":80, "hook_size":102, "body_size":32, "hook_align":"center", "overlay":80, "grad_top":200, "grad_bot":230, "cta_style":"coral", "hook_box":False},
        # 2. Hook top left, body below hook, CTA bottom center
        {"hook_y":8,  "body_y":38, "cta_y":82, "hook_size":88,  "body_size":30, "hook_align":"left",   "overlay":70, "grad_top":180, "grad_bot":220, "cta_style":"coral", "hook_box":False},
        # 3. Hook upper center with box, no body, CTA bottom
        {"hook_y":7,  "body_y":0,  "cta_y":83, "hook_size":96,  "body_size":0,  "hook_align":"center", "overlay":75, "grad_top":210, "grad_bot":240, "cta_style":"coral", "hook_box":True,  "hook_box_color":"#1a1a1a", "hook_box_opacity":180},
        # 4. Hook bottom area, no body, CTA just below hook
        {"hook_y":62, "body_y":0,  "cta_y":80, "hook_size":94,  "body_size":0,  "hook_align":"center", "overlay":60, "grad_top":80,  "grad_bot":230, "cta_style":"coral", "hook_box":False},
        # 5. Hook top right-aligned, body center, CTA bottom left
        {"hook_y":5,  "body_y":55, "cta_y":81, "hook_size":84,  "body_size":32, "hook_align":"right",  "overlay":72, "grad_top":190, "grad_bot":215, "cta_style":"coral", "hook_box":False},
        # 6. Hook middle center huge, no body, CTA bottom
        {"hook_y":38, "body_y":0,  "cta_y":78, "hook_size":110, "body_size":0,  "hook_align":"center", "overlay":85, "grad_top":160, "grad_bot":200, "cta_style":"white", "hook_box":False},
        # 7. Hook top with coral box, body below, CTA bottom
        {"hook_y":6,  "body_y":30, "cta_y":80, "hook_size":90,  "body_size":30, "hook_align":"center", "overlay":65, "grad_top":150, "grad_bot":220, "cta_style":"coral", "hook_box":True,  "hook_box_color":"#E8501C", "hook_box_opacity":230},
        # 8. Hook top left large, body bottom, CTA bottom center
        {"hook_y":7,  "body_y":68, "cta_y":82, "hook_size":98,  "body_size":28, "hook_align":"left",   "overlay":70, "grad_top":200, "grad_bot":180, "cta_style":"coral", "hook_box":False},
        # 9. Hook center with dark box, no body, CTA bottom
        {"hook_y":42, "body_y":0,  "cta_y":79, "hook_size":88,  "body_size":0,  "hook_align":"center", "overlay":80, "grad_top":120, "grad_bot":210, "cta_style":"white", "hook_box":True,  "hook_box_color":"#000000", "hook_box_opacity":160},
    ],
    "informative": [
        # 1. Hook top left clean, body below, dark CTA
        {"hook_y":8,  "body_y":32, "cta_y":83, "hook_size":72,  "body_size":28, "hook_align":"left",   "overlay":20, "grad_top":160, "grad_bot":140, "cta_style":"dark",  "hook_box":False},
        # 2. Hook top center with white box, body middle, dark CTA
        {"hook_y":7,  "body_y":54, "cta_y":82, "hook_size":68,  "body_size":26, "hook_align":"center", "overlay":15, "grad_top":150, "grad_bot":130, "cta_style":"dark",  "hook_box":True,  "hook_box_color":"#FFFFFF", "hook_box_opacity":220},
        # 3. Hook bottom with white box, no body, coral CTA above
        {"hook_y":64, "body_y":0,  "cta_y":55, "hook_size":70,  "body_size":0,  "hook_align":"left",   "overlay":25, "grad_top":100, "grad_bot":200, "cta_style":"coral", "hook_box":True,  "hook_box_color":"#FFFFFF", "hook_box_opacity":230},
        # 4. Hook top center, body center, white CTA
        {"hook_y":6,  "body_y":50, "cta_y":80, "hook_size":74,  "body_size":28, "hook_align":"center", "overlay":20, "grad_top":140, "grad_bot":150, "cta_style":"white", "hook_box":False},
        # 5. Hook top right, body below hook, dark CTA bottom
        {"hook_y":8,  "body_y":36, "cta_y":82, "hook_size":66,  "body_size":26, "hook_align":"right",  "overlay":18, "grad_top":155, "grad_bot":135, "cta_style":"dark",  "hook_box":False},
        # 6. Hook top center large, no body, dark CTA
        {"hook_y":7,  "body_y":0,  "cta_y":81, "hook_size":78,  "body_size":0,  "hook_align":"center", "overlay":22, "grad_top":165, "grad_bot":145, "cta_style":"dark",  "hook_box":False},
        # 7. Hook top left with cream box, body middle, coral CTA
        {"hook_y":6,  "body_y":55, "cta_y":82, "hook_size":70,  "body_size":27, "hook_align":"left",   "overlay":15, "grad_top":130, "grad_bot":140, "cta_style":"coral", "hook_box":True,  "hook_box_color":"#FFF8F0", "hook_box_opacity":225},
        # 8. Hook middle left, body below, white CTA
        {"hook_y":40, "body_y":60, "cta_y":80, "hook_size":72,  "body_size":26, "hook_align":"left",   "overlay":20, "grad_top":80,  "grad_bot":180, "cta_style":"white", "hook_box":False},
        # 9. Hook top center, body bottom, dark CTA
        {"hook_y":8,  "body_y":68, "cta_y":82, "hook_size":68,  "body_size":28, "hook_align":"center", "overlay":18, "grad_top":150, "grad_bot":160, "cta_style":"dark",  "hook_box":False},
    ],
    "money_post": [
        # 1. Hook top with coral box, body middle, white CTA
        {"hook_y":6,  "body_y":54, "cta_y":81, "hook_size":86,  "body_size":30, "hook_align":"center", "overlay":35, "grad_top":60,  "grad_bot":210, "cta_style":"white", "hook_box":True,  "hook_box_color":"#E8501C", "hook_box_opacity":240},
        # 2. Hook top left, body below, coral CTA
        {"hook_y":7,  "body_y":36, "cta_y":82, "hook_size":80,  "body_size":30, "hook_align":"left",   "overlay":30, "grad_top":80,  "grad_bot":200, "cta_style":"coral", "hook_box":False},
        # 3. Hook center huge, no body, white CTA
        {"hook_y":38, "body_y":0,  "cta_y":78, "hook_size":96,  "body_size":0,  "hook_align":"center", "overlay":45, "grad_top":100, "grad_bot":210, "cta_style":"white", "hook_box":False},
        # 4. Hook top center, body center, coral CTA bottom
        {"hook_y":8,  "body_y":52, "cta_y":82, "hook_size":84,  "body_size":32, "hook_align":"center", "overlay":35, "grad_top":70,  "grad_bot":215, "cta_style":"coral", "hook_box":False},
        # 5. Hook bottom with dark box, no body, white CTA above
        {"hook_y":65, "body_y":0,  "cta_y":56, "hook_size":88,  "body_size":0,  "hook_align":"center", "overlay":40, "grad_top":50,  "grad_bot":230, "cta_style":"white", "hook_box":True,  "hook_box_color":"#1a1a1a", "hook_box_opacity":190},
        # 6. Hook top right, body middle, coral CTA
        {"hook_y":6,  "body_y":56, "cta_y":80, "hook_size":82,  "body_size":28, "hook_align":"right",  "overlay":32, "grad_top":60,  "grad_bot":205, "cta_style":"coral", "hook_box":False},
        # 7. Hook top with cream box, body below hook, coral CTA
        {"hook_y":7,  "body_y":30, "cta_y":82, "hook_size":78,  "body_size":30, "hook_align":"center", "overlay":30, "grad_top":65,  "grad_bot":200, "cta_style":"coral", "hook_box":True,  "hook_box_color":"#FFF0E0", "hook_box_opacity":225},
        # 8. Hook top left large, body bottom, white CTA
        {"hook_y":6,  "body_y":70, "cta_y":83, "hook_size":90,  "body_size":28, "hook_align":"left",   "overlay":35, "grad_top":70,  "grad_bot":210, "cta_style":"white", "hook_box":False},
        # 9. Hook middle center with box, no body, coral CTA
        {"hook_y":44, "body_y":0,  "cta_y":78, "hook_size":86,  "body_size":0,  "hook_align":"center", "overlay":40, "grad_top":40,  "grad_bot":220, "cta_style":"coral", "hook_box":True,  "hook_box_color":"#E8501C", "hook_box_opacity":220},
    ],
    "money": [  # alias
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

CTA_STYLES = {
    "coral": {"bg": (232,80,28),  "fg": (255,255,255), "px":52, "py":16, "r":40},
    "white": {"bg": (255,255,255),"fg": (26,26,26),    "px":50, "py":15, "r":38},
    "dark":  {"bg": (26,26,26),   "fg": (255,255,255), "px":48, "py":14, "r":36},
}


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
            if cur: lines.append(cur)
            cur = word
            if max_lines and len(lines) >= max_lines: break
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

def add_overlay(img, opacity):
    if opacity <= 0: return img
    ov = Image.new("RGBA", img.size, (0,0,0,0))
    ImageDraw.Draw(ov).rectangle([0,0,W,H], fill=(0,0,0,opacity))
    return Image.alpha_composite(img.convert("RGBA"),ov).convert("RGB")

def add_box(img, color_rgba, box, radius=14):
    ov = Image.new("RGBA", img.size, (0,0,0,0))
    ImageDraw.Draw(ov).rounded_rectangle(box, radius=radius, fill=color_rgba)
    return Image.alpha_composite(img.convert("RGBA"),ov).convert("RGB")

def draw_text(draw, lines, f, y, color, align, left_x=65, shadow=True):
    for line in lines:
        bb = draw.textbbox((0,0),line,font=f)
        tw, lh = bb[2]-bb[0], bb[3]-bb[1]
        if align == "center": x = W//2 - tw//2
        elif align == "left":  x = left_x
        else:                  x = W - left_x - tw
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

def get_layout(content_type, piece_number):
    """Pick layout variant based on piece_number — guaranteed rotation."""
    ct = content_type.lower().strip()
    if ct not in LAYOUTS:
        ct = "money_post"
    variants = LAYOUTS[ct]
    idx = (int(piece_number or 0) - 1) % len(variants)
    return variants[idx]

def render_pin(img, hook, body_text, cta, content_type, piece_number):
    L = get_layout(content_type, piece_number)
    c = crop_img(img)

    # Overlay
    c = add_overlay(c, L["overlay"])

    # Gradients
    if L["grad_top"] > 0:
        c = add_gradient(c, 0, int(H*0.42), 0, L["grad_top"])
    if L["grad_bot"] > 0:
        c = add_gradient(c, int(H*0.58), H, 0, L["grad_bot"])

    # Hook box
    hook_y = int(H * L["hook_y"] / 100)
    hook_f = fnt(True, L["hook_size"])
    if hook_f:
        hook_lines = wrap_text(hook, hook_f, W-90, max_lines=3)
        if L.get("hook_box") and hook_lines:
            dummy_d = ImageDraw.Draw(Image.new("RGB",(1,1)))
            total_h = sum(
                dummy_d.textbbox((0,0),l,font=hook_f)[3]-dummy_d.textbbox((0,0),l,font=hook_f)[1]+6
                for l in hook_lines
            ) + 30
            box_color = tuple(int(L["hook_box_color"].lstrip('#')[i:i+2],16) for i in (0,2,4))
            c = add_box(c, (*box_color, L.get("hook_box_opacity",180)),
                        [38, hook_y-14, W-38, hook_y+total_h])

        d = ImageDraw.Draw(c)
        hook_y = draw_text(d, hook_lines, hook_f, hook_y,
                           (255,255,255), L["hook_align"], shadow=True)

    d = ImageDraw.Draw(c)

    # Body text
    if body_text and L["body_size"] > 0 and L["body_y"] > 0:
        body_y = int(H * L["body_y"] / 100)
        body_f = fnt(False, L["body_size"])
        if body_f:
            body_lines = wrap_text(body_text, body_f, W-120, max_lines=2)
            draw_text(d, body_lines, body_f, body_y,
                      (240,228,210), L["hook_align"], shadow=True)

    # CTA
    cta_y = int(H * L["cta_y"] / 100)
    cs = CTA_STYLES.get(L["cta_style"], CTA_STYLES["coral"])
    cta_f = fnt(True, 30)
    if cta_f:
        draw_pill(d, cta, cta_f, W//2, cta_y,
                  cs["bg"], cs["fg"], cs["px"], cs["py"], cs["r"])

    buf = io.BytesIO()
    c.save(buf, "JPEG", quality=93, optimize=True)
    return buf.getvalue()


@app.get("/health")
def health():
    return {"status":"ok","version":"13.0","layouts_per_type":9,"total_layouts":27}

@app.get("/", response_class=HTMLResponse)
def index():
    return "<h1>Aurevia Pin Maker v13</h1><p>27 layouts. POST /process-json-custom</p>"

@app.post("/process-json-custom")
async def process_custom(request: Request):
    data = await request.json()

    fname        = (data.get("filename") or "pin.jpg").strip()
    piece_number = str(data.get("piece_number") or "1")
    hook         = " ".join(str(data.get("hook","")).split())
    body_text    = " ".join(str(data.get("body_text","")).split())
    cta          = " ".join(str(data.get("cta","Learn More")).split())
    content_type = str(data.get("content_type","money_post")).strip()
    url = (data.get("image_url") or data.get("drive_url") or "").strip()

    if not url:
        return JSONResponse({"status":"error","error":"image_url required"}, status_code=400)

    try:
        img = load_from_url(url)
        jpg = render_pin(img, hook, body_text, cta, content_type, piece_number)
        out_name = fname.rsplit(".",1)[0] + "_pin.jpg"
        b64 = base64.b64encode(jpg).decode("utf-8")
        return JSONResponse({
            "status":       "ok",
            "filename":     out_name,
            "piece_number": piece_number,
            "content_type": content_type,
            "layout_used":  (int(piece_number)-1) % 9 + 1,
            "image_b64":    b64,
            "size_bytes":   len(jpg)
        })
    except Exception as e:
        return JSONResponse({"status":"error","error":str(e)}, status_code=500)
        
