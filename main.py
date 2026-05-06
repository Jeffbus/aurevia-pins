"""
Aurevia Pin Maker v5 — 16 layouts Pinterest
"""
from fastapi import FastAPI, UploadFile, File
from fastapi.responses import HTMLResponse, StreamingResponse
from PIL import Image, ImageDraw, ImageFont
import requests, csv, io, zipfile, numpy as np

app = FastAPI(title="Aurevia Pin Maker v5")

FB = "/usr/share/fonts/truetype/google-fonts/Poppins-Bold.ttf"
FR = "/usr/share/fonts/truetype/google-fonts/Poppins-Regular.ttf"
W, H = 1000, 1500

CORAL      = (232, 80,  28)
WHITE      = (255, 255, 255)
DARK       = (26,  26,  26)
CREAM      = (255, 248, 240)
LIGHT_BG   = (250, 247, 243)
GRAY       = (100, 100, 100)


# ── Utilities ──────────────────────────────────────────────────────────────────

def load_image(url):
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
    rw, rh = w/img.width, h/img.height
    ratio = max(rw, rh)
    nw, nh = int(img.width*ratio), int(img.height*ratio)
    img = img.resize((nw, nh), Image.LANCZOS)
    l, t = (nw-w)//2, (nh-h)//2
    return img.crop((l, t, l+w, t+h))


def wrap(text, font, max_w):
    dummy = ImageDraw.Draw(Image.new("RGB",(1,1)))
    words, lines, cur = text.split(), [], ""
    for word in words:
        test = (cur+" "+word).strip()
        if dummy.textbbox((0,0),test,font=font)[2] <= max_w:
            cur = test
        else:
            if cur: lines.append(cur)
            cur = word
    if cur: lines.append(cur)
    return lines


def draw_lines(draw, lines, font, y, color, cx=W//2, shadow=False, lh=10, align="center"):
    for line in lines:
        bb = draw.textbbox((0,0), line, font=font)
        tw = bb[2]-bb[0]
        if align == "center": x = cx - tw//2
        elif align == "left":  x = cx
        elif align == "right": x = cx - tw
        if shadow: draw.text((x+2,y+2), line, font=font, fill=(0,0,0,110))
        draw.text((x,y), line, font=font, fill=color)
        y += bb[3]-bb[1]+lh
    return y


def th(draw, lines, font, lh=10):
    total = 0
    for line in lines:
        bb = draw.textbbox((0,0), line, font=font)
        total += bb[3]-bb[1]+lh
    return total


def pill(draw, text, font, cx, y, bg, fg, px=50, py=18, r=32):
    bb = draw.textbbox((0,0), text, font=font)
    tw, tht = bb[2]-bb[0], bb[3]-bb[1]
    bw, bh = tw+px*2, tht+py*2
    x0 = cx-bw//2
    draw.rounded_rectangle([x0,y,x0+bw,y+bh], radius=r, fill=bg)
    draw.text((x0+px, y+py), text, font=font, fill=fg)
    return bh


def grad(img, y0, y1, a0, a1, color=(0,0,0)):
    ov = Image.new("RGBA", img.size, (0,0,0,0))
    d = ImageDraw.Draw(ov)
    span = max(y1-y0,1)
    for i in range(span):
        a = int(a0+(a1-a0)*i/span)
        d.rectangle([0,y0+i,W,y0+i+1], fill=(*color,a))
    return Image.alpha_composite(img.convert("RGBA"), ov).convert("RGB")


def overlay_box(img, x0, y0, x1, y1, fill, radius=0):
    box = Image.new("RGBA", img.size, (0,0,0,0))
    d = ImageDraw.Draw(box)
    if radius:
        d.rounded_rectangle([x0,y0,x1,y1], radius=radius, fill=fill)
    else:
        d.rectangle([x0,y0,x1,y1], fill=fill)
    return Image.alpha_composite(img.convert("RGBA"), box).convert("RGB")


def analyze(img):
    arr = np.array(img.convert("L"))
    third = H//3
    scores = {}
    for name, zone in [("top",arr[:third,:]),("middle",arr[third:2*third,:]),("bottom",arr[2*third:,:])]:
        gy = np.abs(np.diff(zone.astype(float),axis=0)).mean()
        gx = np.abs(np.diff(zone.astype(float),axis=1)).mean()
        scores[name] = 100-(gy+gx)/2
    return max(scores, key=scores.__getitem__)


# ══════════════════════════════════════════════════════════════════════════════
# 16 LAYOUTS
# ══════════════════════════════════════════════════════════════════════════════

def layout_1(img, hook, body, cta):
    """Fondo blanco, título negro grande arriba, imagen centro con marco, body+CTA abajo"""
    c = Image.new("RGB",(W,H),LIGHT_BG)
    d = ImageDraw.Draw(c)
    hf = ImageFont.truetype(FB,88)
    hl = wrap(hook,hf,W-80)
    y = 55
    y = draw_lines(d,hl,hf,y,DARK,lh=8)
    ih = 540; iy = y+40; iw = W-100
    ph = crop(img,iw,ih)
    shadow = Image.new("RGB",(iw+14,ih+14),(200,200,200))
    c.paste(shadow,(43,iy-7))
    frame = Image.new("RGB",(iw+6,ih+6),WHITE)
    c.paste(frame,(47,iy-3))
    c.paste(ph,(50,iy))
    d = ImageDraw.Draw(c)
    bf = ImageFont.truetype(FR,40)
    bl = wrap(body,bf,W-120)
    y = iy+ih+55
    y = draw_lines(d,bl,bf,y,GRAY,lh=8)
    cf = ImageFont.truetype(FB,42)
    pill(d,cta,cf,W//2,y+18,CORAL,WHITE,px=58,py=20,r=8)
    return c


def layout_2(img, hook, body, cta):
    """Imagen arriba con marco en fondo coral, título grande + body abajo en coral"""
    c = Image.new("RGB",(W,H),CORAL)
    d = ImageDraw.Draw(c)
    ih = int(H*0.52); pad=28; ip=14
    ph = crop(img,W-pad*2-ip*2,ih-ip*2)
    frame = Image.new("RGB",(W-pad*2,ih),CREAM)
    c.paste(frame,(pad,pad))
    c.paste(ph,(pad+ip,pad+ip))
    hf = ImageFont.truetype(FB,96)
    hl = wrap(hook.upper(),hf,W-80)
    y = ih+pad+45
    d = ImageDraw.Draw(c)
    y = draw_lines(d,hl,hf,y,CREAM,lh=4)
    bf = ImageFont.truetype(FR,38)
    bl = wrap(body,bf,W-80)
    y += 8
    y = draw_lines(d,bl,bf,y,(255,230,220),lh=8)
    cf = ImageFont.truetype(FB,40)
    pill(d,cta.upper(),cf,W//2,y+20,CREAM,CORAL,px=55,py=18,r=6)
    return c


def layout_3(img, hook, body, cta):
    """Full bleed, caja semitransparente neutral arriba con hook, body+CTA sobre imagen"""
    c = crop(img)
    d = ImageDraw.Draw(c)
    hf = ImageFont.truetype(FB,76)
    hl = wrap(hook,hf,W-100-40)
    bh = th(d,hl,hf)+60
    c = overlay_box(c,40,75,W-40,75+bh,(200,190,180,200),radius=12)
    d = ImageDraw.Draw(c)
    y = 95
    y = draw_lines(d,hl,hf,y,WHITE,shadow=True)
    bf = ImageFont.truetype(FB,44)
    bl = wrap(body,bf,W-100)
    y = int(H*0.62)
    y = draw_lines(d,bl,bf,y,WHITE,shadow=True)
    cf = ImageFont.truetype(FR,38)
    draw_lines(d,[cta],cf,H-100,CREAM)
    return c


def layout_4(img, hook, body, cta):
    """Imagen 62% arriba, línea coral, fondo blanco abajo con título+body"""
    split = int(H*0.62)
    c = Image.new("RGB",(W,H),WHITE)
    ph = crop(img,W,split)
    c.paste(ph,(0,0))
    d = ImageDraw.Draw(c)
    d.rectangle([0,split,W,split+8],fill=CORAL)
    hf = ImageFont.truetype(FB,70)
    hl = wrap(hook.upper(),hf,W-80)
    y = split+50
    y = draw_lines(d,hl,hf,y,DARK,lh=6)
    bf = ImageFont.truetype(FR,36)
    bl = wrap(body,bf,W-100)
    y += 10
    y = draw_lines(d,bl,bf,y,GRAY,lh=6)
    cf = ImageFont.truetype(FR,34)
    draw_lines(d,[cta.upper()],cf,H-90,CORAL)
    return c


def layout_5(img, hook, body, cta):
    """Full bleed con marco blanco interior, hook arriba, body abajo"""
    c = crop(img)
    c = grad(c,0,320,0,170)
    c = grad(c,H-260,H,0,200)
    d = ImageDraw.Draw(c)
    margin = 60
    d.rectangle([margin,margin+240,W-margin,H-margin-200],outline=WHITE,width=3)
    hf = ImageFont.truetype(FB,82)
    hl = wrap(hook,hf,W-80)
    y = 55
    y = draw_lines(d,hl,hf,y,WHITE,shadow=True,lh=6)
    bf = ImageFont.truetype(FR,44)
    bl = wrap(body,bf,W-80)
    bh2 = th(d,bl,bf)+20
    y = H-bh2-60
    draw_lines(d,bl,bf,y,CREAM,shadow=True)
    cf = ImageFont.truetype(FR,34)
    pill(d,cta.upper(),cf,W//2,H-52,(255,255,255,180),DARK,px=40,py=12,r=20)
    return c


def layout_6(img, hook, body, cta):
    """Full bleed, caja coral sólida arriba detectada por zona, CTA pill blanco abajo"""
    c = crop(img)
    zone = analyze(c)
    box_y = int(H*0.62) if zone=="bottom" else 70
    hf = ImageFont.truetype(FB,80)
    hl = wrap(hook.upper(),hf,W-100-20)
    d = ImageDraw.Draw(c)
    box_h = th(d,hl,hf)+60
    c = overlay_box(c,40,box_y,W-40,box_y+box_h,(*CORAL,230))
    d = ImageDraw.Draw(c)
    lf = ImageFont.truetype(FR,32)
    draw_lines(d,[body[:40]],lf,box_y-44,WHITE,shadow=True)
    y = box_y+20
    draw_lines(d,hl,hf,y,WHITE)
    cf = ImageFont.truetype(FR,40)
    cta_y = H-130
    c = overlay_box(c,W//2-260,cta_y,W//2+260,cta_y+66,(255,255,255,210),radius=33)
    d = ImageDraw.Draw(c)
    bb = d.textbbox((0,0),cta,font=cf)
    d.text((W//2-(bb[2]-bb[0])//2,cta_y+18),cta,font=cf,fill=CORAL)
    return c


def layout_7(img, hook, body, cta):
    """Full bleed, gran caja blanca semitransparente centrada, dos estilos de texto"""
    c = crop(img)
    c = grad(c,0,H,60,60)
    hf1 = ImageFont.truetype(FB,76)
    hf2 = ImageFont.truetype(FR,72)
    bf  = ImageFont.truetype(FR,40)
    words = hook.split()
    half = max(len(words)//2,1)
    l1 = wrap(" ".join(words[:half]),hf1,W-120)
    l2 = wrap(" ".join(words[half:]),hf2,W-120)
    bl = wrap(body,bf,W-120)
    dummy = ImageDraw.Draw(Image.new("RGB",(1,1)))
    total = th(dummy,l1,hf1)+th(dummy,l2,hf2)+th(dummy,bl,bf)+80
    box_y = H//2-total//2-30
    box_h = total+80
    c = overlay_box(c,60,box_y,W-60,box_y+box_h,(245,240,235,205))
    d = ImageDraw.Draw(c)
    y = box_y+30
    y = draw_lines(d,l1,hf1,y,DARK,lh=6)
    y = draw_lines(d,l2,hf2,y,CORAL,lh=6)
    y += 10
    draw_lines(d,bl,bf,y,GRAY,lh=6)
    cf = ImageFont.truetype(FR,38)
    draw_lines(d,[cta],cf,box_y+box_h+20,DARK)
    return c


def layout_8(img, hook, body, cta):
    """Full bleed, label blanco pequeño + caja coral grande apiladas arriba"""
    c = crop(img)
    zone = analyze(c)
    top_y = int(H*0.55) if zone=="bottom" else 60
    lf = ImageFont.truetype(FB,38)
    d = ImageDraw.Draw(c)
    lbl = cta.upper()
    lb = d.textbbox((0,0),lbl,font=lf)
    lw = lb[2]-lb[0]+80; lh2 = lb[3]-lb[1]+24
    lx = W//2-lw//2
    c = overlay_box(c,lx,top_y,lx+lw,top_y+lh2,(255,255,255,240))
    d = ImageDraw.Draw(c)
    d.text((lx+40,top_y+12),lbl,font=lf,fill=DARK)
    hf = ImageFont.truetype(FB,82)
    hl = wrap(hook.upper(),hf,W-100-20)
    hook_y = top_y+lh2
    hook_h = th(d,hl,hf)+40
    c = overlay_box(c,40,hook_y,W-40,hook_y+hook_h,(*CORAL,235))
    d = ImageDraw.Draw(c)
    y = hook_y+16
    draw_lines(d,hl,hf,y,WHITE)
    bf = ImageFont.truetype(FR,38)
    bl = wrap(body,bf,W-100)
    body_y = hook_y+hook_h+16
    bbox_h = th(d,bl,bf)+30
    c = overlay_box(c,40,body_y,W-40,body_y+bbox_h,(255,255,255,210),radius=10)
    d = ImageDraw.Draw(c)
    draw_lines(d,bl,bf,body_y+14,DARK)
    return c


def layout_9(img, hook, body, cta):
    """Fondo crema, imagen izq con círculo decorativo, título arriba derecha, body lateral"""
    c = Image.new("RGB",(W,H),LIGHT_BG)
    d = ImageDraw.Draw(c)
    # Decorative circle behind image
    cx2, cy2, cr = 380, 750, 340
    d.ellipse([cx2-cr,cy2-cr,cx2+cr,cy2+cr], fill=(232,80,28,60))
    # Image with rounded corners, left-center
    ih = 680; iw = 620; ix = 50; iy = 370
    ph = crop(img,iw,ih)
    # paste with rounded mask
    mask = Image.new("L",(iw,ih),0)
    ImageDraw.Draw(mask).rounded_rectangle([0,0,iw,ih],radius=30,fill=255)
    c.paste(ph,(ix,iy),mask)
    d = ImageDraw.Draw(c)
    # Title top right
    hf = ImageFont.truetype(FB,78)
    hl = wrap(hook.upper(),hf,480)
    y = 60
    for line in hl:
        bb = d.textbbox((0,0),line,font=hf)
        d.text((W-50-(bb[2]-bb[0]),y),line,font=hf,fill=CORAL)
        y += bb[3]-bb[1]+8
    # Body text vertical left side
    bf = ImageFont.truetype(FR,34)
    bl = wrap(body,bf,150)
    y2 = 400
    for line in bl:
        d.text((10,y2),line,font=bf,fill=DARK)
        y2 += 44
    # CTA bottom right
    cf = ImageFont.truetype(FB,38)
    pill(d,cta,cf,W-180,H-130,CORAL,WHITE,px=40,py=16,r=8)
    return c


def layout_10(img, hook, body, cta):
    """Full bleed, hook MUY GRANDE que ocupa la imagen, CTA pequeño abajo"""
    c = crop(img)
    c = grad(c,0,H,80,80)
    d = ImageDraw.Draw(c)
    hf = ImageFont.truetype(FB,130)
    hl = wrap(hook.upper(),hf,W-40)
    total = th(d,hl,hf,lh=6)
    y = H//2 - total//2 - 60
    for line in hl:
        bb = d.textbbox((0,0),line,font=hf)
        x = 30
        d.text((x+3,y+3),line,font=hf,fill=(0,0,0,140))
        d.text((x,y),line,font=hf,fill=CREAM)
        y += bb[3]-bb[1]+6
    # CTA box bottom
    cf = ImageFont.truetype(FB,38)
    cta_y = H-110
    c = overlay_box(c,60,cta_y,460,cta_y+62,WHITE)
    d = ImageDraw.Draw(c)
    d.text((80,cta_y+16),cta.upper(),font=cf,fill=CORAL)
    return c


def layout_11(img, hook, body, cta):
    """Fondo crema arriba 40%, imagen abajo con esquinas redondeadas, título coral centrado, CTA outline"""
    split = int(H*0.42)
    c = Image.new("RGB",(W,H),LIGHT_BG)
    ih = H-split-20; iw = W-60
    ph = crop(img,iw,ih)
    mask = Image.new("L",(iw,ih),0)
    ImageDraw.Draw(mask).rounded_rectangle([0,0,iw,ih],radius=28,fill=255)
    c.paste(ph,(30,split+10),mask)
    d = ImageDraw.Draw(c)
    hf = ImageFont.truetype(FB,82)
    hl = wrap(hook,hf,W-80)
    y = 50
    y = draw_lines(d,hl,hf,y,CORAL,lh=6)
    # CTA outline style
    cf = ImageFont.truetype(FR,38)
    lbl = f"{cta} >"
    bb = d.textbbox((0,0),lbl,font=cf)
    bw = bb[2]-bb[0]+60; bh2 = bb[3]-bb[1]+24
    bx = W//2-bw//2; by = y+20
    d.rounded_rectangle([bx,by,bx+bw,by+bh2],radius=bh2//2,outline=CORAL,width=3)
    d.text((bx+30,by+12),lbl,font=cf,fill=CORAL)
    return c


def layout_12(img, hook, body, cta):
    """Fondo rosa, imagen oval/elipse centro, título serif grande abajo"""
    BG = (252,230,220)
    c = Image.new("RGB",(W,H),BG)
    d = ImageDraw.Draw(c)
    # Oval image
    ow, oh = 700, 480; ox, oy = (W-ow)//2, 100
    ph = crop(img,ow,oh)
    mask = Image.new("L",(ow,oh),0)
    ImageDraw.Draw(mask).ellipse([0,0,ow,oh],fill=255)
    c.paste(ph,(ox,oy),mask)
    d = ImageDraw.Draw(c)
    # Decorative line top
    d.line([W//2-150,70,W-60,70],fill=DARK,width=2)
    d.text((W-80,50),"★★★",font=ImageFont.truetype(FR,30),fill=DARK)
    # Large title bottom
    hf = ImageFont.truetype(FB,80)
    hl = wrap(hook.upper(),hf,W-80)
    y = oy+oh+50
    y = draw_lines(d,hl,hf,y,DARK,lh=4)
    # Body script style
    bf = ImageFont.truetype(FR,44)
    bl = wrap(body,bf,W-80)
    y = draw_lines(d,bl,bf,y+8,GRAY,lh=6)
    # CTA text bottom
    cf = ImageFont.truetype(FR,32)
    draw_lines(d,[cta],cf,H-70,GRAY)
    return c


def layout_13(img, hook, body, cta):
    """Full bleed, texto 3 líneas centrado en tercio superior sin caja, minimal"""
    c = crop(img)
    c = grad(c,0,400,0,150)
    d = ImageDraw.Draw(c)
    # Small label top
    sf = ImageFont.truetype(FR,32)
    draw_lines(d,[cta.upper()],sf,60,WHITE)
    # Large title
    hf = ImageFont.truetype(FB,84)
    hl = wrap(hook,hf,W-80)
    total = th(d,hl,hf,lh=10)
    y = 120
    y = draw_lines(d,hl,hf,y,WHITE,shadow=True,lh=10)
    # Body small
    bf = ImageFont.truetype(FR,38)
    bl = wrap(body,bf,W-100)
    draw_lines(d,bl,bf,y+16,CREAM,shadow=True)
    return c


def layout_14(img, hook, body, cta):
    """Full bleed, hook serif left-aligned middle, body small right, URL tiny top"""
    c = crop(img)
    c = grad(c,int(H*0.3),int(H*0.75),0,160)
    c = grad(c,H-200,H,0,180)
    d = ImageDraw.Draw(c)
    # Tiny URL top
    sf = ImageFont.truetype(FR,28)
    d.text((W//2-80,40),"joinaurevia.com",font=sf,fill=(255,255,255,180))
    # Large hook left-aligned middle
    hf = ImageFont.truetype(FB,80)
    hl = wrap(hook.upper(),hf,W-80)
    total = th(d,hl,hf)
    y = H//2 - total//2
    for line in hl:
        bb = d.textbbox((0,0),line,font=hf)
        d.text((52+2,y+2),line,font=hf,fill=(0,0,0,120))
        d.text((52,y),line,font=hf,fill=WHITE)
        y += bb[3]-bb[1]+10
    # Body bottom
    bf = ImageFont.truetype(FR,38)
    bl = wrap(body,bf,W-80)
    draw_lines(d,bl,bf,H-170,CREAM,shadow=True)
    return c


def layout_15(img, hook, body, cta):
    """Full bleed, marco fino exterior, caja blanca redondeada centrada hook+body"""
    c = crop(img)
    d = ImageDraw.Draw(c)
    # Outer thin frame
    d.rectangle([22,22,W-22,H-22],outline=WHITE,width=3)
    # White rounded box center
    hf = ImageFont.truetype(FB,72)
    hl = wrap(hook,hf,W-160)
    bf = ImageFont.truetype(FR,40)
    bl = wrap(body,bf,W-160)
    dummy = ImageDraw.Draw(Image.new("RGB",(1,1)))
    total = th(dummy,hl,hf)+th(dummy,bl,bf)+50
    box_y = H//2-total//2-30
    box_h = total+70
    c = overlay_box(c,70,box_y,W-70,box_y+box_h,(255,255,255,220),radius=24)
    d = ImageDraw.Draw(c)
    y = box_y+30
    y = draw_lines(d,hl,hf,y,DARK,lh=8)
    y += 10
    draw_lines(d,bl,bf,y,GRAY,lh=6)
    # CTA bottom
    cf = ImageFont.truetype(FR,36)
    draw_lines(d,[cta],cf,H-80,WHITE,shadow=True)
    return c


def layout_16(img, hook, body, cta):
    """3 fotos collage arriba 58%, fondo coral oscuro abajo, label pequeño + título"""
    DARK_BG = (40,20,10)
    c = Image.new("RGB",(W,H),DARK_BG)
    # Collage 3 images top
    top_h = int(H*0.58)
    col1_w = W//2; col2_w = W-col1_w
    # Left column: 2 stacked
    h1 = top_h//2; h2 = top_h-h1
    p1 = crop(img,col1_w,h1); c.paste(p1,(0,0))
    p2 = crop(img,col1_w,h2); c.paste(p2,(0,h1))
    # Right: 1 full height
    p3 = crop(img,col2_w,top_h); c.paste(p3,(col1_w,0))
    d = ImageDraw.Draw(c)
    # Grid lines
    d.line([(0,h1),(col1_w,h1)],fill=(20,10,5),width=4)
    d.line([(col1_w,0),(col1_w,top_h)],fill=(20,10,5),width=4)
    # Label small
    lf = ImageFont.truetype(FR,32)
    draw_lines(d,[body.upper()],lf,top_h+40,(180,140,120),lh=6)
    # Large title
    hf = ImageFont.truetype(FB,76)
    hl = wrap(hook,hf,W-80)
    y = top_h+90
    y = draw_lines(d,hl,hf,y,WHITE,lh=6)
    # CTA
    cf = ImageFont.truetype(FR,34)
    draw_lines(d,[cta],cf,y+16,(200,160,140),lh=6)
    return c


LAYOUTS = {
    "layout_1": layout_1, "layout_2": layout_2,
    "layout_3": layout_3, "layout_4": layout_4,
    "layout_5": layout_5, "layout_6": layout_6,
    "layout_7": layout_7, "layout_8": layout_8,
    "layout_9": layout_9, "layout_10": layout_10,
    "layout_11": layout_11, "layout_12": layout_12,
    "layout_13": layout_13, "layout_14": layout_14,
    "layout_15": layout_15, "layout_16": layout_16,
    "money_post":  layout_8,
    "informative": layout_6,
    "retention":   layout_7,
}

CT_DEFAULT = {
    "money_post": "layout_8",
    "informative": "layout_6",
    "retention": "layout_7",
}


def process_row(row):
    img = load_image(row.get("drive_url","").strip())
    ct  = row.get("content_type","money_post").strip()
    t   = row.get("template","auto").strip()
    if t == "auto": t = CT_DEFAULT.get(ct,"layout_8")
    fn  = LAYOUTS.get(t, layout_8)
    out = fn(img, row.get("hook",""), row.get("body_text",""), row.get("cta","Learn More"))
    buf = io.BytesIO()
    out.save(buf,"JPEG",quality=92)
    return buf.getvalue(), row.get("filename","output.jpg")


@app.get("/health")
def health():
    return {"status":"ok","version":"5.0","layouts":16}


@app.get("/", response_class=HTMLResponse)
def index():
    return """<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Aurevia Pin Maker v5</title>
<style>
*{box-sizing:border-box}
body{font-family:'Segoe UI',sans-serif;background:#f0f0f0;margin:0;padding:40px 16px}
.box{max-width:700px;margin:0 auto;background:#fff;border-radius:20px;padding:44px;box-shadow:0 6px 30px rgba(0,0,0,.09)}
h1{color:#E8501C;margin-top:0}p{color:#666;margin-top:0}
label{display:block;font-weight:600;margin:20px 0 6px;color:#222}
input[type=file]{width:100%;padding:12px;border:2px dashed #e0e0e0;border-radius:10px;font-size:14px}
button{background:#E8501C;color:#fff;border:none;padding:15px;border-radius:32px;font-size:16px;font-weight:700;cursor:pointer;margin-top:22px;width:100%}
button:hover{background:#c43d10}
.note{background:#fff8f5;border-left:4px solid #E8501C;padding:16px 18px;border-radius:8px;margin-top:26px;font-size:13px;color:#555;line-height:1.8}
code{background:#f0f0f0;padding:2px 6px;border-radius:4px;font-size:12px}
.grid{display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:6px;margin-top:10px}
.lc{background:#fff8f5;border:1px solid #fdd;border-radius:6px;padding:8px;font-size:11px;text-align:center}
.lc b{color:#E8501C;display:block;font-size:13px}
</style></head><body>
<div class="box">
<h1>🖼 Aurevia Pin Maker <span style="background:#E8501C;color:#fff;font-size:11px;padding:3px 10px;border-radius:10px;margin-left:6px">v5 · 16 layouts</span></h1>
<p>Sube tu CSV y descarga los pines con texto. Detección automática de zona neutra.</p>
<form action="/process" method="post" enctype="multipart/form-data">
<label>📄 CSV con textos</label>
<input type="file" name="csv_file" accept=".csv" required>
<button type="submit">⚡ Generar Pines</button>
</form>
<div class="note">
<b>Columnas:</b> <code>filename, content_type, hook, body_text, cta, template, drive_url</code><br>
<b>template:</b> <code>auto</code> o <code>layout_1</code>…<code>layout_16</code><br>
<b>auto:</b> money_post→layout_8 · informative→layout_6 · retention→layout_7
<div class="grid">
<div class="lc"><b>layout_1</b>Fondo blanco + marco</div>
<div class="lc"><b>layout_2</b>Coral abajo</div>
<div class="lc"><b>layout_3</b>Caja semitrans</div>
<div class="lc"><b>layout_4</b>62% + separador</div>
<div class="lc"><b>layout_5</b>Marco interior</div>
<div class="lc"><b>layout_6</b>Caja coral arriba</div>
<div class="lc"><b>layout_7</b>Caja blanca centro</div>
<div class="lc"><b>layout_8</b>Dos cajas apiladas</div>
<div class="lc"><b>layout_9</b>Círculo deco + lateral</div>
<div class="lc"><b>layout_10</b>Texto gigante</div>
<div class="lc"><b>layout_11</b>Crema + oval</div>
<div class="lc"><b>layout_12</b>Rosa + elipse</div>
<div class="lc"><b>layout_13</b>Minimal top</div>
<div class="lc"><b>layout_14</b>Left-aligned bold</div>
<div class="lc"><b>layout_15</b>Marco fino + caja</div>
<div class="lc"><b>layout_16</b>Collage 3 fotos</div>
</div>
</div>
</div></body></html>"""


@app.post("/process")
async def process(csv_file: UploadFile = File(...)):
    content = (await csv_file.read()).decode("utf-8-sig")
    reader  = csv.DictReader(io.StringIO(content))
    buf     = io.BytesIO()
    errors  = []
    with zipfile.ZipFile(buf,"w",zipfile.ZIP_DEFLATED) as zf:
        for i, row in enumerate(reader,1):
            fname = row.get("filename",f"pin_{i:03d}.jpg")
            try:
                jpg, name = process_row(row)
                zf.writestr(name.rsplit(".",1)[0]+"_pin.jpg",jpg)
            except Exception as e:
                errors.append(f"{fname}: {e}")
        if errors:
            zf.writestr("errors.txt","\n".join(errors))
    buf.seek(0)
    return StreamingResponse(buf,media_type="application/zip",
        headers={"Content-Disposition":"attachment; filename=aurevia_pins.zip"})
