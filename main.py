"""
Aurevia Pin Maker — FastAPI + Pillow
Recibe imagen (URL de Drive) + datos del CSV → devuelve imagen con texto superpuesto
"""
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import requests, csv, io, zipfile, traceback
from typing import Optional

app = FastAPI(title="Aurevia Pin Maker")

# ── Fonts ──────────────────────────────────────────────────────────────────────
FONT_BOLD   = "/usr/share/fonts/truetype/google-fonts/Poppins-Bold.ttf"
FONT_REGULAR = "/usr/share/fonts/truetype/google-fonts/Poppins-Regular.ttf"

# ── Canvas size ────────────────────────────────────────────────────────────────
W, H = 1000, 1500

# ── Colors ─────────────────────────────────────────────────────────────────────
WHITE      = (255, 255, 255)
BLACK      = (0, 0, 0)
CORAL      = (232, 80, 28)       # Aurevia brand
DARK_CORAL = (180, 55, 10)
CREAM      = (255, 248, 240)
DARK_OVERLAY = (0, 0, 0, 160)    # semitransparente
LIGHT_OVERLAY = (0, 0, 0, 110)


# ── Helpers ────────────────────────────────────────────────────────────────────

def load_image_from_url(url: str) -> Image.Image:
    """Download image from URL (Drive direct link or any public URL)."""
    # Convert Drive share URL → direct download URL
    if "drive.google.com" in url:
        if "/file/d/" in url:
            file_id = url.split("/file/d/")[1].split("/")[0]
            url = f"https://drive.google.com/uc?export=download&id={file_id}"
        elif "id=" in url:
            file_id = url.split("id=")[1].split("&")[0]
            url = f"https://drive.google.com/uc?export=download&id={file_id}"

    r = requests.get(url, timeout=30, stream=True)
    r.raise_for_status()
    return Image.open(io.BytesIO(r.content)).convert("RGB")


def cover_crop(img: Image.Image, w=W, h=H) -> Image.Image:
    """Resize + center crop to fill canvas without distortion."""
    ratio_w = w / img.width
    ratio_h = h / img.height
    ratio = max(ratio_w, ratio_h)
    new_w = int(img.width * ratio)
    new_h = int(img.height * ratio)
    img = img.resize((new_w, new_h), Image.LANCZOS)
    left = (new_w - w) // 2
    top  = (new_h - h) // 2
    return img.crop((left, top, left + w, top + h))


def wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    """Break text into lines that fit max_width."""
    words = text.split()
    lines, current = [], ""
    dummy = Image.new("RGB", (1, 1))
    draw  = ImageDraw.Draw(dummy)
    for word in words:
        test = (current + " " + word).strip()
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def draw_rounded_rect(draw, xy, radius=20, fill=None):
    """Draw a rounded rectangle."""
    x0, y0, x1, y1 = xy
    draw.rounded_rectangle([x0, y0, x1, y1], radius=radius, fill=fill)


def add_overlay(img: Image.Image, top_height=0, bottom_height=0, full=False) -> Image.Image:
    """Add dark gradient overlay on top and/or bottom."""
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    if full:
        draw.rectangle([0, 0, W, H], fill=(0, 0, 0, 120))
    if top_height:
        for i in range(top_height):
            alpha = int(180 * (1 - i / top_height))
            draw.rectangle([0, i, W, i+1], fill=(0, 0, 0, alpha))
    if bottom_height:
        for i in range(bottom_height):
            alpha = int(200 * (i / bottom_height))
            y = H - bottom_height + i
            draw.rectangle([0, y, W, y+1], fill=(0, 0, 0, alpha))
    return Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")


# ── Templates ─────────────────────────────────────────────────────────────────

def template_money_post(img: Image.Image, hook: str, body_text: str, cta: str) -> Image.Image:
    """
    Money Post — Hook grande arriba, body en medio, CTA botón abajo.
    Estilo agresivo, alto contraste, orientado al clic.
    """
    img = cover_crop(img)
    img = add_overlay(img, top_height=480, bottom_height=320)
    draw = ImageDraw.Draw(img)

    pad = 60

    # ── Hook (grande, arriba) ──
    hook_font = ImageFont.truetype(FONT_BOLD, 80)
    hook_lines = wrap_text(hook.upper(), hook_font, W - pad * 2)
    y = 60
    for line in hook_lines:
        bbox = draw.textbbox((0, 0), line, font=hook_font)
        x = (W - (bbox[2] - bbox[0])) // 2
        # sombra
        draw.text((x+3, y+3), line, font=hook_font, fill=(0,0,0,180))
        draw.text((x, y), line, font=hook_font, fill=WHITE)
        y += bbox[3] - bbox[1] + 12

    # ── Separador coral ──
    draw.rectangle([pad, y+10, W-pad, y+14], fill=CORAL)
    y += 40

    # ── Body text ──
    body_font = ImageFont.truetype(FONT_REGULAR, 44)
    body_lines = wrap_text(body_text, body_font, W - pad * 2)
    for line in body_lines:
        bbox = draw.textbbox((0, 0), line, font=body_font)
        x = (W - (bbox[2] - bbox[0])) // 2
        draw.text((x+2, y+2), line, font=body_font, fill=(0,0,0,140))
        draw.text((x, y), line, font=body_font, fill=CREAM)
        y += bbox[3] - bbox[1] + 10

    # ── CTA botón abajo ──
    cta_font = ImageFont.truetype(FONT_BOLD, 46)
    cta_text = cta.upper()
    cta_bbox = draw.textbbox((0, 0), cta_text, font=cta_font)
    cta_w = cta_bbox[2] - cta_bbox[0] + 80
    cta_h = cta_bbox[3] - cta_bbox[1] + 30
    cta_x = (W - cta_w) // 2
    cta_y = H - 120 - cta_h

    draw_rounded_rect(draw, [cta_x, cta_y, cta_x+cta_w, cta_y+cta_h], radius=30, fill=CORAL)
    draw.text((cta_x + 40, cta_y + 15), cta_text, font=cta_font, fill=WHITE)

    return img


def template_informative(img: Image.Image, hook: str, body_text: str, cta: str) -> Image.Image:
    """
    Informative — Diseño limpio tipo guía. Hook arriba, body en caja semi, CTA discreto.
    """
    img = cover_crop(img)
    img = add_overlay(img, top_height=300, bottom_height=400)
    draw = ImageDraw.Draw(img)

    pad = 60

    # ── Hook arriba ──
    hook_font = ImageFont.truetype(FONT_BOLD, 70)
    hook_lines = wrap_text(hook.upper(), hook_font, W - pad * 2)
    y = 70
    for line in hook_lines:
        bbox = draw.textbbox((0, 0), line, font=hook_font)
        x = (W - (bbox[2] - bbox[0])) // 2
        draw.text((x+2, y+2), line, font=hook_font, fill=(0,0,0,160))
        draw.text((x, y), line, font=hook_font, fill=WHITE)
        y += bbox[3] - bbox[1] + 14

    # ── Caja semitransparente para body ──
    body_font = ImageFont.truetype(FONT_REGULAR, 42)
    body_lines = wrap_text(body_text, body_font, W - pad * 4)
    line_h = 52
    box_h = len(body_lines) * line_h + 60
    box_y = H - 280 - box_h

    box_img = Image.new("RGBA", img.size, (0,0,0,0))
    box_draw = ImageDraw.Draw(box_img)
    box_draw.rounded_rectangle([pad, box_y, W-pad, box_y+box_h], radius=20, fill=(255,255,255,200))
    img = Image.alpha_composite(img.convert("RGBA"), box_img).convert("RGB")
    draw = ImageDraw.Draw(img)

    text_y = box_y + 30
    for line in body_lines:
        bbox = draw.textbbox((0, 0), line, font=body_font)
        x = (W - (bbox[2] - bbox[0])) // 2
        draw.text((x, text_y), line, font=body_font, fill=(40, 40, 40))
        text_y += line_h

    # ── CTA discreto ──
    cta_font = ImageFont.truetype(FONT_BOLD, 40)
    cta_text = "→  " + cta.upper()
    cta_bbox = draw.textbbox((0, 0), cta_text, font=cta_font)
    cta_w = cta_bbox[2] - cta_bbox[0] + 60
    cta_h = cta_bbox[3] - cta_bbox[1] + 24
    cta_x = (W - cta_w) // 2
    cta_y = H - 110 - cta_h

    draw_rounded_rect(draw, [cta_x, cta_y, cta_x+cta_w, cta_y+cta_h], radius=24, fill=WHITE)
    draw.text((cta_x + 30, cta_y + 12), cta_text, font=cta_font, fill=CORAL)

    return img


def template_retention(img: Image.Image, hook: str, body_text: str, cta: str) -> Image.Image:
    """
    Retention — Estilo emocional/testimonial. Hook centrado, body secundario, CTA limpio.
    """
    img = cover_crop(img)
    img = add_overlay(img, full=True)
    draw = ImageDraw.Draw(img)

    pad = 70

    # ── Línea decorativa coral arriba ──
    draw.rectangle([pad, 80, W - pad, 86], fill=CORAL)

    # ── Hook centrado (vertical center) ──
    hook_font = ImageFont.truetype(FONT_BOLD, 74)
    hook_lines = wrap_text(hook.upper(), hook_font, W - pad * 2)
    total_hook_h = sum(
        draw.textbbox((0,0), l, font=hook_font)[3] - draw.textbbox((0,0), l, font=hook_font)[1] + 16
        for l in hook_lines
    )
    y = (H - total_hook_h) // 2 - 80

    for line in hook_lines:
        bbox = draw.textbbox((0, 0), line, font=hook_font)
        x = (W - (bbox[2] - bbox[0])) // 2
        draw.text((x+3, y+3), line, font=hook_font, fill=(0,0,0,180))
        draw.text((x, y), line, font=hook_font, fill=WHITE)
        y += bbox[3] - bbox[1] + 16

    y += 20
    draw.rectangle([pad*2, y, W-pad*2, y+4], fill=CORAL)
    y += 30

    # ── Body como frase secundaria ──
    body_font = ImageFont.truetype(FONT_REGULAR, 42)
    body_lines = wrap_text(body_text, body_font, W - pad * 2)
    for line in body_lines:
        bbox = draw.textbbox((0, 0), line, font=body_font)
        x = (W - (bbox[2] - bbox[0])) // 2
        draw.text((x, y), line, font=body_font, fill=CREAM)
        y += bbox[3] - bbox[1] + 12

    # ── CTA limpio abajo ──
    cta_font = ImageFont.truetype(FONT_BOLD, 42)
    cta_text = cta.upper()
    cta_bbox = draw.textbbox((0, 0), cta_text, font=cta_font)
    cta_w = cta_bbox[2] - cta_bbox[0] + 80
    cta_h = cta_bbox[3] - cta_bbox[1] + 28
    cta_x = (W - cta_w) // 2
    cta_y = H - 120 - cta_h

    draw_rounded_rect(draw, [cta_x, cta_y, cta_x+cta_w, cta_y+cta_h], radius=28, fill=CORAL)
    draw.text((cta_x + 40, cta_y + 14), cta_text, font=cta_font, fill=WHITE)

    # ── Línea decorativa coral abajo ──
    draw.rectangle([pad, H - 80, W - pad, H - 74], fill=CORAL)

    return img


TEMPLATES = {
    "money_post":  template_money_post,
    "informative": template_informative,
    "retention":   template_retention,
}

def get_template(content_type: str, template_override: str = "auto"):
    t = template_override if template_override != "auto" else content_type
    return TEMPLATES.get(t, template_money_post)


def process_row(row: dict) -> tuple[bytes, str]:
    """Process one CSV row → return (jpg_bytes, filename)."""
    drive_url  = row.get("drive_url", "").strip()
    filename   = row.get("filename", "output.jpg").strip()
    content_type = row.get("content_type", "money_post").strip()
    hook       = row.get("hook", "").strip()
    body_text  = row.get("body_text", "").strip()
    cta        = row.get("cta", "Learn More").strip()
    template   = row.get("template", "auto").strip()

    img = load_image_from_url(drive_url)
    fn  = get_template(content_type, template)
    result = fn(img, hook, body_text, cta)

    buf = io.BytesIO()
    result.save(buf, format="JPEG", quality=92)
    return buf.getvalue(), filename


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
def index():
    return """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Aurevia Pin Maker</title>
<style>
  body { font-family: 'Segoe UI', sans-serif; background: #f5f5f5; margin: 0; padding: 40px 20px; }
  .container { max-width: 680px; margin: 0 auto; background: white; border-radius: 16px; padding: 40px; box-shadow: 0 4px 24px rgba(0,0,0,.08); }
  h1 { color: #E8501C; margin-top: 0; }
  label { display: block; font-weight: 600; margin: 20px 0 6px; color: #333; }
  input[type=file] { width: 100%; padding: 10px; border: 2px dashed #ddd; border-radius: 8px; }
  button { background: #E8501C; color: white; border: none; padding: 14px 36px; border-radius: 30px; font-size: 16px; font-weight: 700; cursor: pointer; margin-top: 24px; width: 100%; }
  button:hover { background: #c43d10; }
  .note { background: #fff8f5; border-left: 4px solid #E8501C; padding: 14px 18px; border-radius: 6px; margin-top: 28px; font-size: 14px; color: #555; }
  code { background: #f0f0f0; padding: 2px 6px; border-radius: 4px; font-size: 13px; }
</style>
</head>
<body>
<div class="container">
  <h1>🖼️ Aurevia Pin Maker</h1>
  <p style="color:#666">Sube tu CSV con los datos y los pines se generan automáticamente con las plantillas correctas.</p>

  <form action="/process" method="post" enctype="multipart/form-data">
    <label>📄 CSV con textos</label>
    <input type="file" name="csv_file" accept=".csv" required>

    <button type="submit">⚡ Generar Pines</button>
  </form>

  <div class="note">
    <b>Formato del CSV:</b><br><br>
    <code>filename, content_type, hook, body_text, cta, template, drive_url, article_url, product_url</code><br><br>
    <b>content_type:</b> <code>money_post</code> | <code>informative</code> | <code>retention</code><br>
    <b>template:</b> <code>auto</code> (usa content_type) o nombre específico<br>
    <b>drive_url:</b> URL directa o de Google Drive de la imagen base
  </div>
</div>
</body>
</html>
"""


@app.post("/process")
async def process(csv_file: UploadFile = File(...)):
    """
    Recibe CSV → descarga imágenes de Drive → aplica plantillas → devuelve ZIP con pines.
    """
    csv_content = (await csv_file.read()).decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(csv_content))

    zip_buf = io.BytesIO()
    errors  = []

    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for i, row in enumerate(reader, 1):
            filename = row.get("filename", f"pin_{i:03d}.jpg").strip()
            try:
                jpg_bytes, fname = process_row(row)
                out_name = fname.rsplit(".", 1)[0] + "_pin.jpg"
                zf.writestr(out_name, jpg_bytes)
            except Exception as e:
                errors.append({"filename": filename, "error": str(e)})

        if errors:
            err_lines = ["filename,error"]
            for e in errors:
                err_lines.append(f'{e["filename"]},{e["error"]}')
            zf.writestr("errors.csv", "\n".join(err_lines))

    zip_buf.seek(0)
    return StreamingResponse(
        zip_buf,
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=aurevia_pins.zip"}
    )


@app.post("/render")
async def render_single(
    drive_url: str = Form(...),
    hook: str = Form(...),
    body_text: str = Form(...),
    cta: str = Form(...),
    content_type: str = Form("money_post"),
    template: str = Form("auto"),
):
    """Renderiza una sola imagen y la devuelve como JPG."""
    try:
        row = {
            "drive_url": drive_url,
            "filename": "output.jpg",
            "content_type": content_type,
            "hook": hook,
            "body_text": body_text,
            "cta": cta,
            "template": template,
        }
        jpg_bytes, _ = process_row(row)
        return StreamingResponse(
            io.BytesIO(jpg_bytes),
            media_type="image/jpeg",
            headers={"Content-Disposition": "attachment; filename=pin_preview.jpg"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
