"""
Aurevia Pin Maker v7
- 24 layouts total (16 originales + 8 nuevos)
- Selección inteligente de layout por tipo de imagen y content_type
- Opción A: CSV con URLs / Opción B: Subir desde PC
"""
from fastapi import FastAPI, UploadFile, File
from fastapi.responses import HTMLResponse, StreamingResponse
from PIL import Image, ImageDraw, ImageFont
import csv, io, zipfile, numpy as np, requests
from typing import List

app = FastAPI(title="Aurevia Pin Maker v7")

FB = "/usr/share/fonts/truetype/google-fonts/Poppins-Bold.ttf"
FR = "/usr/share/fonts/truetype/google-fonts/Poppins-Regular.ttf"
W, H = 1000, 1500

CORAL    = (232, 80,  28)
WHITE    = (255, 255, 255)
DARK     = (26,  26,  26)
CREAM    = (255, 248, 240)
LIGHT_BG = (250, 247, 243)
GRAY     = (100, 100, 100)
TERRA    = (180, 90,  50)


# ── Utilities ──────────────────────────────────────────────────────────────────

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
    """Detect best neutral zone AND image type."""
    arr = np.array(img.convert("L"))
    third = H//3
    scores = {}
    for name, zone in [("top",arr[:third,:]),("middle",arr[third:2*third,:]),("bottom",arr[2*third:,:])]:
        gy = np.abs(np.diff(zone.astype(float),axis=0)).mean()
        gx = np.abs(np.diff(zone.astype(float),axis=1)).mean()
        scores[name] = 100-(gy+gx)/2
    best_zone = max(scores, key=scores.__getitem__)

    # Detect image type based on brightness variance and edge density
    brightness = arr.mean()
    variance = arr.var()
    total_edges = (np.abs(np.diff(arr.astype(float),axis=0)).mean() +
                   np.abs(np.diff(arr.astype(float),axis=1)).mean()) / 2

    if variance < 800:
        img_type = "minimal"      # flat lay, minimal, clean
    elif brightness > 180:
        img_type = "bright"       # outdoor, lifestyle bright
    elif brightness < 80:
        img_type = "dark"         # dramatic, dark background
    elif total_edges > 20:
        img_type = "busy"         # portrait close-up, detailed
    else:
        img_type = "lifestyle"    # general lifestyle

    return best_zone, img_type


# ══════════════════════════════════════════════════════════════════════════════
# LAYOUTS 1-16 (originales)
# ══════════════════════════════════════════════════════════════════════════════

def layout_1(img, hook, body, cta):
    c = Image.new("RGB",(W,H),LIGHT_BG); d = ImageDraw.Draw(c)
    hf = ImageFont.truetype(FB,88); hl = wrap(hook,hf,W-80)
    y = 55; y = draw_lines(d,hl,hf,y,DARK,lh=8)
    ih=540; iy=y+40; iw=W-100; ph=crop(img,iw,ih)
    c.paste(Image.new("RGB",(iw+14,ih+14),(200,200,200)),(43,iy-7))
    c.paste(Image.new("RGB",(iw+6,ih+6),WHITE),(47,iy-3))
    c.paste(ph,(50,iy)); d=ImageDraw.Draw(c)
    bf=ImageFont.truetype(FR,40); bl=wrap(body,bf,W-120)
    y=iy+ih+55; y=draw_lines(d,bl,bf,y,GRAY,lh=8)
    pill(d,cta,ImageFont.truetype(FB,42),W//2,y+18,CORAL,WHITE,px=58,py=20,r=8)
    return c

def layout_2(img, hook, body, cta):
    c=Image.new("RGB",(W,H),CORAL); d=ImageDraw.Draw(c)
    ih=int(H*0.52); pad=28; ip=14
    ph=crop(img,W-pad*2-ip*2,ih-ip*2)
    c.paste(Image.new("RGB",(W-pad*2,ih),CREAM),(pad,pad))
    c.paste(ph,(pad+ip,pad+ip))
    hf=ImageFont.truetype(FB,96); hl=wrap(hook.upper(),hf,W-80)
    y=ih+pad+45; d=ImageDraw.Draw(c)
    y=draw_lines(d,hl,hf,y,CREAM,lh=4)
    bf=ImageFont.truetype(FR,38); bl=wrap(body,bf,W-80)
    y+=8; y=draw_lines(d,bl,bf,y,(255,230,220),lh=8)
    pill(d,cta.upper(),ImageFont.truetype(FB,40),W//2,y+20,CREAM,CORAL,px=55,py=18,r=6)
    return c

def layout_3(img, hook, body, cta):
    c=crop(img); d=ImageDraw.Draw(c)
    hf=ImageFont.truetype(FB,76); hl=wrap(hook,hf,W-100-40)
    bh2=th(d,hl,hf)+60
    c=overlay_box(c,40,75,W-40,75+bh2,(200,190,180,200),radius=12)
    d=ImageDraw.Draw(c); y=95; y=draw_lines(d,hl,hf,y,WHITE,shadow=True)
    bf=ImageFont.truetype(FB,44); bl=wrap(body,bf,W-100)
    y=int(H*0.62); y=draw_lines(d,bl,bf,y,WHITE,shadow=True)
    draw_lines(d,[cta],ImageFont.truetype(FR,38),H-100,CREAM)
    return c

def layout_4(img, hook, body, cta):
    split=int(H*0.62); c=Image.new("RGB",(W,H),WHITE)
    c.paste(crop(img,W,split),(0,0)); d=ImageDraw.Draw(c)
    d.rectangle([0,split,W,split+8],fill=CORAL)
    hf=ImageFont.truetype(FB,70); hl=wrap(hook.upper(),hf,W-80)
    y=split+50; y=draw_lines(d,hl,hf,y,DARK,lh=6)
    bf=ImageFont.truetype(FR,36); bl=wrap(body,bf,W-100)
    y+=10; y=draw_lines(d,bl,bf,y,GRAY,lh=6)
    draw_lines(d,[cta.upper()],ImageFont.truetype(FR,34),H-90,CORAL)
    return c

def layout_5(img, hook, body, cta):
    c=crop(img); c=grad(c,0,320,0,170); c=grad(c,H-260,H,0,200)
    d=ImageDraw.Draw(c)
    d.rectangle([60,300,W-60,H-240],outline=WHITE,width=3)
    hf=ImageFont.truetype(FB,82); hl=wrap(hook,hf,W-80)
    y=55; y=draw_lines(d,hl,hf,y,WHITE,shadow=True,lh=6)
    bf=ImageFont.truetype(FR,44); bl=wrap(body,bf,W-80)
    bh2=th(d,bl,bf)+20; y=H-bh2-60
    draw_lines(d,bl,bf,y,CREAM,shadow=True)
    pill(d,cta.upper(),ImageFont.truetype(FR,34),W//2,H-52,(255,255,255,180),DARK,px=40,py=12,r=20)
    return c

def layout_6(img, hook, body, cta):
    c=crop(img); zone,_=analyze(c)
    box_y=int(H*0.62) if zone=="bottom" else 70
    hf=ImageFont.truetype(FB,80); hl=wrap(hook.upper(),hf,W-100-20)
    d=ImageDraw.Draw(c); box_h=th(d,hl,hf)+60
    c=overlay_box(c,40,box_y,W-40,box_y+box_h,(*CORAL,230))
    d=ImageDraw.Draw(c)
    draw_lines(d,[body[:40]],ImageFont.truetype(FR,32),box_y-44,WHITE,shadow=True)
    draw_lines(d,hl,hf,box_y+20,WHITE)
    cf=ImageFont.truetype(FR,40); cta_y=H-130
    c=overlay_box(c,W//2-260,cta_y,W//2+260,cta_y+66,(255,255,255,210),radius=33)
    d=ImageDraw.Draw(c)
    bb=d.textbbox((0,0),cta,font=cf)
    d.text((W//2-(bb[2]-bb[0])//2,cta_y+18),cta,font=cf,fill=CORAL)
    return c

def layout_7(img, hook, body, cta):
    c=crop(img); c=grad(c,0,H,60,60)
    hf1=ImageFont.truetype(FB,76); hf2=ImageFont.truetype(FR,72); bf=ImageFont.truetype(FR,40)
    words=hook.split(); half=max(len(words)//2,1)
    l1=wrap(" ".join(words[:half]),hf1,W-120); l2=wrap(" ".join(words[half:]),hf2,W-120)
    bl=wrap(body,bf,W-120)
    dummy=ImageDraw.Draw(Image.new("RGB",(1,1)))
    total=th(dummy,l1,hf1)+th(dummy,l2,hf2)+th(dummy,bl,bf)+80
    box_y=H//2-total//2-30; box_h=total+80
    c=overlay_box(c,60,box_y,W-60,box_y+box_h,(245,240,235,205))
    d=ImageDraw.Draw(c); y=box_y+30
    y=draw_lines(d,l1,hf1,y,DARK,lh=6)
    y=draw_lines(d,l2,hf2,y,CORAL,lh=6); y+=10
    draw_lines(d,bl,bf,y,GRAY,lh=6)
    draw_lines(d,[cta],ImageFont.truetype(FR,38),box_y+box_h+20,DARK)
    return c

def layout_8(img, hook, body, cta):
    c=crop(img); zone,_=analyze(c)
    top_y=int(H*0.55) if zone=="bottom" else 60
    lf=ImageFont.truetype(FB,38); d=ImageDraw.Draw(c)
    lbl=cta.upper(); lb=d.textbbox((0,0),lbl,font=lf)
    lw=lb[2]-lb[0]+80; lh2=lb[3]-lb[1]+24; lx=W//2-lw//2
    c=overlay_box(c,lx,top_y,lx+lw,top_y+lh2,(255,255,255,240))
    d=ImageDraw.Draw(c); d.text((lx+40,top_y+12),lbl,font=lf,fill=DARK)
    hf=ImageFont.truetype(FB,82); hl=wrap(hook.upper(),hf,W-100-20)
    hook_y=top_y+lh2; hook_h=th(d,hl,hf)+40
    c=overlay_box(c,40,hook_y,W-40,hook_y+hook_h,(*CORAL,235))
    d=ImageDraw.Draw(c); draw_lines(d,hl,hf,hook_y+16,WHITE)
    bf=ImageFont.truetype(FR,38); bl=wrap(body,bf,W-100)
    body_y=hook_y+hook_h+16; bbox_h=th(d,bl,bf)+30
    c=overlay_box(c,40,body_y,W-40,body_y+bbox_h,(255,255,255,210),radius=10)
    d=ImageDraw.Draw(c); draw_lines(d,bl,bf,body_y+14,DARK)
    return c

def layout_9(img, hook, body, cta):
    c=Image.new("RGB",(W,H),LIGHT_BG); d=ImageDraw.Draw(c)
    d.ellipse([40,410,720,1090],fill=(232,80,28,60))
    ih=680; iw=620; ph=crop(img,iw,ih)
    mask=Image.new("L",(iw,ih),0)
    ImageDraw.Draw(mask).rounded_rectangle([0,0,iw,ih],radius=30,fill=255)
    c.paste(ph,(50,370),mask); d=ImageDraw.Draw(c)
    hf=ImageFont.truetype(FB,78); hl=wrap(hook.upper(),hf,480)
    y=60
    for line in hl:
        bb=d.textbbox((0,0),line,font=hf)
        d.text((W-50-(bb[2]-bb[0]),y),line,font=hf,fill=CORAL)
        y+=bb[3]-bb[1]+8
    bf=ImageFont.truetype(FR,34); bl=wrap(body,bf,150)
    y2=400
    for line in bl:
        d.text((10,y2),line,font=bf,fill=DARK); y2+=44
    pill(d,cta,ImageFont.truetype(FB,38),W-180,H-130,CORAL,WHITE,px=40,py=16,r=8)
    return c

def layout_10(img, hook, body, cta):
    c=crop(img); c=grad(c,0,H,80,80); d=ImageDraw.Draw(c)
    hf=ImageFont.truetype(FB,130); hl=wrap(hook.upper(),hf,W-40)
    total=th(d,hl,hf,lh=6); y=H//2-total//2-60
    for line in hl:
        bb=d.textbbox((0,0),line,font=hf)
        d.text((32,y+3),line,font=hf,fill=(0,0,0,140))
        d.text((30,y),line,font=hf,fill=CREAM); y+=bb[3]-bb[1]+6
    cf=ImageFont.truetype(FB,38); cta_y=H-110
    c=overlay_box(c,60,cta_y,460,cta_y+62,WHITE)
    d=ImageDraw.Draw(c); d.text((80,cta_y+16),cta.upper(),font=cf,fill=CORAL)
    return c

def layout_11(img, hook, body, cta):
    split=int(H*0.42); c=Image.new("RGB",(W,H),LIGHT_BG)
    ih=H-split-20; iw=W-60; ph=crop(img,iw,ih)
    mask=Image.new("L",(iw,ih),0)
    ImageDraw.Draw(mask).rounded_rectangle([0,0,iw,ih],radius=28,fill=255)
    c.paste(ph,(30,split+10),mask); d=ImageDraw.Draw(c)
    hf=ImageFont.truetype(FB,82); hl=wrap(hook,hf,W-80)
    y=50; y=draw_lines(d,hl,hf,y,CORAL,lh=6)
    cf=ImageFont.truetype(FR,38); lbl=f"{cta} >"
    bb=d.textbbox((0,0),lbl,font=cf)
    bw=bb[2]-bb[0]+60; bh2=bb[3]-bb[1]+24
    bx=W//2-bw//2; by=y+20
    d.rounded_rectangle([bx,by,bx+bw,by+bh2],radius=bh2//2,outline=CORAL,width=3)
    d.text((bx+30,by+12),lbl,font=cf,fill=CORAL)
    return c

def layout_12(img, hook, body, cta):
    BG=(252,230,220); c=Image.new("RGB",(W,H),BG)
    d=ImageDraw.Draw(c)
    ow,oh=700,480; ox,oy=(W-ow)//2,100
    ph=crop(img,ow,oh); mask=Image.new("L",(ow,oh),0)
    ImageDraw.Draw(mask).ellipse([0,0,ow,oh],fill=255)
    c.paste(ph,(ox,oy),mask); d=ImageDraw.Draw(c)
    d.line([W//2-150,70,W-60,70],fill=DARK,width=2)
    hf=ImageFont.truetype(FB,80); hl=wrap(hook.upper(),hf,W-80)
    y=oy+oh+50; y=draw_lines(d,hl,hf,y,DARK,lh=4)
    bf=ImageFont.truetype(FR,44); bl=wrap(body,bf,W-80)
    y=draw_lines(d,bl,bf,y+8,GRAY,lh=6)
    draw_lines(d,[cta],ImageFont.truetype(FR,32),H-70,GRAY)
    return c

def layout_13(img, hook, body, cta):
    c=crop(img); c=grad(c,0,400,0,150); d=ImageDraw.Draw(c)
    draw_lines(d,[cta.upper()],ImageFont.truetype(FR,32),60,WHITE)
    hf=ImageFont.truetype(FB,84); hl=wrap(hook,hf,W-80)
    y=120; y=draw_lines(d,hl,hf,y,WHITE,shadow=True,lh=10)
    bf=ImageFont.truetype(FR,38); bl=wrap(body,bf,W-100)
    draw_lines(d,bl,bf,y+16,CREAM,shadow=True)
    return c

def layout_14(img, hook, body, cta):
    c=crop(img); c=grad(c,int(H*0.3),int(H*0.75),0,160)
    c=grad(c,H-200,H,0,180); d=ImageDraw.Draw(c)
    d.text((W//2-80,40),"joinaurevia.com",font=ImageFont.truetype(FR,28),fill=(255,255,255,180))
    hf=ImageFont.truetype(FB,80); hl=wrap(hook.upper(),hf,W-80)
    total=th(d,hl,hf); y=H//2-total//2
    for line in hl:
        bb=d.textbbox((0,0),line,font=hf)
        d.text((54,y+2),line,font=hf,fill=(0,0,0,120))
        d.text((52,y),line,font=hf,fill=WHITE); y+=bb[3]-bb[1]+10
    draw_lines(d,wrap(body,ImageFont.truetype(FR,38),W-80),ImageFont.truetype(FR,38),H-170,CREAM,shadow=True)
    return c

def layout_15(img, hook, body, cta):
    c=crop(img); d=ImageDraw.Draw(c)
    d.rectangle([22,22,W-22,H-22],outline=WHITE,width=3)
    hf=ImageFont.truetype(FB,72); bf=ImageFont.truetype(FR,40)
    hl=wrap(hook,hf,W-160); bl=wrap(body,bf,W-160)
    dummy=ImageDraw.Draw(Image.new("RGB",(1,1)))
    total=th(dummy,hl,hf)+th(dummy,bl,bf)+50
    box_y=H//2-total//2-30; box_h=total+70
    c=overlay_box(c,70,box_y,W-70,box_y+box_h,(255,255,255,220),radius=24)
    d=ImageDraw.Draw(c); y=box_y+30
    y=draw_lines(d,hl,hf,y,DARK,lh=8); y+=10
    draw_lines(d,bl,bf,y,GRAY,lh=6)
    draw_lines(d,[cta],ImageFont.truetype(FR,36),H-80,WHITE,shadow=True)
    return c

def layout_16(img, hook, body, cta):
    DARK_BG=(40,20,10); c=Image.new("RGB",(W,H),DARK_BG)
    top_h=int(H*0.58); col1_w=W//2; col2_w=W-col1_w
    h1=top_h//2; h2=top_h-h1
    c.paste(crop(img,col1_w,h1),(0,0))
    c.paste(crop(img,col1_w,h2),(0,h1))
    c.paste(crop(img,col2_w,top_h),(col1_w,0))
    d=ImageDraw.Draw(c)
    d.line([(0,h1),(col1_w,h1)],fill=(20,10,5),width=4)
    d.line([(col1_w,0),(col1_w,top_h)],fill=(20,10,5),width=4)
    draw_lines(d,[body.upper()],ImageFont.truetype(FR,32),top_h+40,(180,140,120),lh=6)
    hf=ImageFont.truetype(FB,76); hl=wrap(hook,hf,W-80)
    y=top_h+90; y=draw_lines(d,hl,hf,y,WHITE,lh=6)
    draw_lines(d,[cta],ImageFont.truetype(FR,34),y+16,(200,160,140),lh=6)
    return c


# ══════════════════════════════════════════════════════════════════════════════
# LAYOUTS 17-24 (nuevos)
# ══════════════════════════════════════════════════════════════════════════════

def layout_17(img, hook, body, cta):
    """Arco decorativo — imagen en arco, fondo terracota, título script abajo."""
    BG = (180, 100, 60)
    c = Image.new("RGB", (W, H), BG)
    # Arch mask for image
    arch_w, arch_h = W - 60, int(H * 0.62)
    arch_x, arch_y = 30, 0
    ph = crop(img, arch_w, arch_h)
    mask = Image.new("L", (arch_w, arch_h), 0)
    md = ImageDraw.Draw(mask)
    # Arch = rectangle bottom + semicircle top
    half = arch_w // 2
    md.rectangle([0, half, arch_w, arch_h], fill=255)
    md.ellipse([0, 0, arch_w, arch_w], fill=255)
    c.paste(ph, (arch_x, arch_y), mask)
    d = ImageDraw.Draw(c)
    # Title bottom
    hf = ImageFont.truetype(FB, 82)
    hl = wrap(hook, hf, W - 80)
    y = arch_y + arch_h + 40
    y = draw_lines(d, hl, hf, y, WHITE, lh=6)
    # Body small
    bf = ImageFont.truetype(FR, 40)
    bl = wrap(body, bf, W - 100)
    y = draw_lines(d, bl, bf, y + 10, CREAM, lh=6)
    # CTA
    pill(d, cta.upper(), ImageFont.truetype(FB, 38), W//2, y+16, WHITE, BG, px=50, py=16, r=30)
    return c


def layout_18(img, hook, body, cta):
    """Imagen 65% + fondo color sólido abajo con label pill + título grande."""
    split = int(H * 0.60)
    BG_BOTTOM = (232, 80, 28)
    c = Image.new("RGB", (W, H), BG_BOTTOM)
    c.paste(crop(img, W, split), (0, 0))
    d = ImageDraw.Draw(c)
    # Label pill
    lf = ImageFont.truetype(FR, 32)
    lbl = cta.upper()
    lb = d.textbbox((0,0), lbl, font=lf)
    lw = lb[2]-lb[0]+60; lh2 = lb[3]-lb[1]+20
    lx = 50; ly = split + 30
    d.rounded_rectangle([lx, ly, lx+lw, ly+lh2], radius=lh2//2, fill=WHITE)
    d.text((lx+30, ly+10), lbl, font=lf, fill=CORAL)
    # Title
    hf = ImageFont.truetype(FB, 76)
    hl = wrap(hook.upper(), hf, W - 80)
    y = ly + lh2 + 24
    y = draw_lines(d, hl, hf, y, WHITE, lh=4)
    # Body
    bf = ImageFont.truetype(FR, 36)
    bl = wrap(body, bf, W - 80)
    draw_lines(d, bl, bf, y + 8, (255, 220, 200), lh=6)
    return c


def layout_19(img, hook, body, cta):
    """Full bleed, texto right-aligned con barra vertical coral derecha."""
    c = crop(img)
    c = grad(c, 0, H, 40, 40)
    # Coral vertical bar right
    bar_x = W - 80
    c = overlay_box(c, bar_x, 0, W, H, (*CORAL, 200))
    d = ImageDraw.Draw(c)
    # Vertical CTA text in bar
    cf = ImageFont.truetype(FR, 26)
    cta_chars = cta.upper()
    y_c = 60
    for ch in cta_chars:
        d.text((bar_x + 18, y_c), ch, font=cf, fill=WHITE)
        y_c += 34
    # Hook right-aligned
    hf = ImageFont.truetype(FB, 76)
    hl = wrap(hook.upper(), hf, bar_x - 80)
    y = 80
    y = draw_lines(d, hl, hf, y, WHITE, cx=bar_x-30, shadow=True, lh=8, align="right")
    # Line
    d.rectangle([100, y+10, bar_x-30, y+4], fill=CORAL)
    y += 30
    # Body
    bf = ImageFont.truetype(FR, 40)
    bl = wrap(body, bf, bar_x - 80)
    draw_lines(d, bl, bf, y, CREAM, cx=bar_x-30, shadow=True, lh=8, align="right")
    return c


def layout_20(img, hook, body, cta):
    """Full bleed, caja grande semitransparente centro — hook bold + body."""
    c = crop(img)
    d = ImageDraw.Draw(c)
    hf = ImageFont.truetype(FB, 78)
    bf = ImageFont.truetype(FR, 42)
    hl = wrap(hook, hf, W - 120)
    bl = wrap(body, bf, W - 140)
    dummy = ImageDraw.Draw(Image.new("RGB", (1,1)))
    total = th(dummy, hl, hf) + th(dummy, bl, bf) + 60
    box_y = H//2 - total//2 - 20
    box_h = total + 60
    c = overlay_box(c, 50, box_y, W-50, box_y+box_h, (230, 210, 190, 210), radius=20)
    d = ImageDraw.Draw(c)
    y = box_y + 28
    y = draw_lines(d, hl, hf, y, DARK, lh=8)
    y += 10
    draw_lines(d, bl, bf, y, (80, 60, 40), lh=6)
    # CTA bottom
    c = grad(c, H-220, H, 0, 180)
    d = ImageDraw.Draw(c)
    pill(d, cta.upper(), ImageFont.truetype(FB, 40), W//2, H-150, CORAL, WHITE, px=55, py=18, r=30)
    return c


def layout_21(img, hook, body, cta):
    """Imagen 70% arriba + fondo oscuro abajo, CTA pill blanco."""
    split = int(H * 0.68)
    DARK_BG = (30, 25, 20)
    c = Image.new("RGB", (W, H), DARK_BG)
    c.paste(crop(img, W, split), (0, 0))
    d = ImageDraw.Draw(c)
    # Small label
    sf = ImageFont.truetype(FR, 30)
    draw_lines(d, [body.upper()[:35]], sf, split+30, (180,150,120), lh=4)
    # Large hook
    hf = ImageFont.truetype(FB, 74)
    hl = wrap(hook, hf, W-80)
    y = split + 70
    y = draw_lines(d, hl, hf, y, WHITE, lh=6)
    # CTA pill
    pill(d, cta.upper(), ImageFont.truetype(FB, 40), W//2, y+20, WHITE, DARK_BG, px=55, py=18, r=30)
    return c


def layout_22(img, hook, body, cta):
    """Full bleed, caja blanca con esquinas decorativas tipo sticker, hook bold."""
    c = crop(img)
    c = grad(c, 0, H, 50, 50)
    hf = ImageFont.truetype(FB, 80)
    hl = wrap(hook.upper(), hf, W - 160)
    bf = ImageFont.truetype(FR, 40)
    bl = wrap(body, bf, W - 160)
    dummy = ImageDraw.Draw(Image.new("RGB",(1,1)))
    total = th(dummy,hl,hf) + th(dummy,bl,bf) + 60
    box_y = H//2 - total//2 - 30
    box_h = total + 70
    pad = 70
    c = overlay_box(c, pad, box_y, W-pad, box_y+box_h, (255,255,255,230), radius=16)
    d = ImageDraw.Draw(c)
    # Corner decorations
    corner_size = 20
    for cx2, cy2 in [(pad, box_y), (W-pad, box_y), (pad, box_y+box_h), (W-pad, box_y+box_h)]:
        d.rectangle([cx2-corner_size, cy2-4, cx2+corner_size, cy2+4], fill=CORAL)
        d.rectangle([cx2-4, cy2-corner_size, cx2+4, cy2+corner_size], fill=CORAL)
    y = box_y + 30
    y = draw_lines(d, hl, hf, y, DARK, lh=6)
    y += 8
    draw_lines(d, bl, bf, y, GRAY, lh=6)
    pill(d, cta.upper(), ImageFont.truetype(FB,38), W//2, H-130, CORAL, WHITE, px=50, py=16, r=30)
    return c


def layout_23(img, hook, body, cta):
    """Full bleed, hook GRANDE top left + body como quote centrado bottom."""
    c = crop(img)
    c = grad(c, 0, 500, 0, 160)
    c = grad(c, H-300, H, 0, 190)
    d = ImageDraw.Draw(c)
    # Hook top large
    hf = ImageFont.truetype(FB, 90)
    hl = wrap(hook.upper(), hf, W - 80)
    y = 50
    for line in hl:
        bb = d.textbbox((0,0), line, font=hf)
        d.text((52+2, y+2), line, font=hf, fill=(0,0,0,120))
        d.text((52, y), line, font=hf, fill=WHITE)
        y += bb[3]-bb[1]+8
    # Coral line
    d.rectangle([52, y+10, W-52, y+5], fill=CORAL)
    # Body bottom centered
    bf = ImageFont.truetype(FR, 42)
    bl = wrap(body, bf, W-100)
    bh2 = th(d, bl, bf)
    y2 = H - bh2 - 100
    draw_lines(d, bl, bf, y2, CREAM, shadow=True)
    # CTA
    pill(d, cta.upper(), ImageFont.truetype(FB,38), W//2, H-80, (255,255,255,200), DARK, px=45,py=14,r=28)
    return c


def layout_24(img, hook, body, cta):
    """Doble caja apilada: caja blanca top con label + caja coral con hook + URL bottom."""
    c = crop(img)
    c = grad(c, 0, H, 30, 30)
    d = ImageDraw.Draw(c)
    pad = 50
    # Top box — label
    lf = ImageFont.truetype(FR, 32)
    lbl = body[:35]
    lb = d.textbbox((0,0), lbl, font=lf)
    lbox_h = lb[3]-lb[1]+36
    c = overlay_box(c, pad, 60, W-pad, 60+lbox_h, (255,255,255,230))
    d = ImageDraw.Draw(c)
    draw_lines(d, [lbl], lf, 78, DARK)
    # Middle box — hook
    hf = ImageFont.truetype(FB, 78)
    hl = wrap(hook.upper(), hf, W-pad*2-20)
    hook_y = 60+lbox_h+8
    hook_h = th(d, hl, hf)+44
    c = overlay_box(c, pad, hook_y, W-pad, hook_y+hook_h, (*CORAL, 240))
    d = ImageDraw.Draw(c)
    draw_lines(d, hl, hf, hook_y+18, WHITE)
    # Sub box — body
    bf = ImageFont.truetype(FR, 38)
    bl = wrap(body[:50], bf, W-pad*2-20)
    sub_y = hook_y+hook_h+8
    sub_h = th(d, bl, bf)+36
    c = overlay_box(c, pad, sub_y, W-pad, sub_y+sub_h, (255,255,255,210), radius=10)
    d = ImageDraw.Draw(c)
    draw_lines(d, bl, bf, sub_y+16, DARK)
    # CTA bottom
    draw_lines(d, [cta], ImageFont.truetype(FR,32), H-70, (200,200,200), shadow=True)
    return c


# ══════════════════════════════════════════════════════════════════════════════
# Intelligent Layout Selection
# ══════════════════════════════════════════════════════════════════════════════

# All layouts by number
ALL_LAYOUTS = {
    "layout_1": layout_1, "layout_2": layout_2, "layout_3": layout_3,
    "layout_4": layout_4, "layout_5": layout_5, "layout_6": layout_6,
    "layout_7": layout_7, "layout_8": layout_8, "layout_9": layout_9,
    "layout_10": layout_10, "layout_11": layout_11, "layout_12": layout_12,
    "layout_13": layout_13, "layout_14": layout_14, "layout_15": layout_15,
    "layout_16": layout_16, "layout_17": layout_17, "layout_18": layout_18,
    "layout_19": layout_19, "layout_20": layout_20, "layout_21": layout_21,
    "layout_22": layout_22, "layout_23": layout_23, "layout_24": layout_24,
    # content_type aliases
    "money_post": layout_8, "informative": layout_6, "retention": layout_7,
}

# Smart selection: content_type + image_type → best layouts (in priority order)
SMART_LAYOUTS = {
    ("money_post", "bright"):    ["layout_8", "layout_13", "layout_23"],
    ("money_post", "lifestyle"):  ["layout_8", "layout_6", "layout_18"],
    ("money_post", "minimal"):    ["layout_4", "layout_1", "layout_21"],
    ("money_post", "dark"):       ["layout_10", "layout_21", "layout_16"],
    ("money_post", "busy"):       ["layout_3", "layout_20", "layout_7"],
    ("informative", "bright"):   ["layout_6", "layout_11", "layout_4"],
    ("informative", "lifestyle"): ["layout_6", "layout_15", "layout_24"],
    ("informative", "minimal"):   ["layout_1", "layout_17", "layout_12"],
    ("informative", "dark"):      ["layout_5", "layout_14", "layout_19"],
    ("informative", "busy"):      ["layout_3", "layout_22", "layout_20"],
    ("retention", "bright"):     ["layout_7", "layout_5", "layout_13"],
    ("retention", "lifestyle"):   ["layout_7", "layout_15", "layout_17"],
    ("retention", "minimal"):     ["layout_9", "layout_12", "layout_7"],
    ("retention", "dark"):        ["layout_21", "layout_5", "layout_19"],
    ("retention", "busy"):        ["layout_7", "layout_22", "layout_3"],
}

# Track used layouts per batch to ensure variety
_used_layouts: list = []

def smart_select_layout(img, content_type, piece_number):
    """Select layout based on image characteristics and content type."""
    global _used_layouts
    zone, img_type = analyze(img)
    key = (content_type, img_type)
    candidates = SMART_LAYOUTS.get(key, ["layout_8", "layout_6", "layout_7"])

    # Pick first candidate not recently used
    for candidate in candidates:
        if candidate not in _used_layouts[-6:]:
            _used_layouts.append(candidate)
            if len(_used_layouts) > 30:
                _used_layouts = _used_layouts[-20:]
            return ALL_LAYOUTS[candidate]

    # Fallback: rotate through candidates
    idx = int(piece_number or 0) % len(candidates)
    chosen = candidates[idx]
    _used_layouts.append(chosen)
    return ALL_LAYOUTS[chosen]


def apply_template(img, row):
    ct       = row.get("content_type", "money_post").strip()
    template = row.get("template", "auto").strip()
    piece    = row.get("piece_number", "0")

    if template == "auto":
        fn = smart_select_layout(img, ct, piece)
    else:
        fn = ALL_LAYOUTS.get(template, layout_8)

    out = fn(img, row.get("hook",""), row.get("body_text",""), row.get("cta","Learn More"))
    buf = io.BytesIO()
    out.save(buf, "JPEG", quality=92)
    return buf.getvalue()


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status":"ok","version":"7.0","layouts":24,"smart_selection":True}


@app.get("/", response_class=HTMLResponse)
def index():
    return """<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Aurevia Pin Maker v7</title>
<style>
*{box-sizing:border-box}
body{font-family:'Segoe UI',sans-serif;background:#f0f0f0;margin:0;padding:30px 16px}
.box{max-width:700px;margin:0 auto;background:#fff;border-radius:20px;padding:40px;box-shadow:0 6px 30px rgba(0,0,0,.09)}
h1{color:#E8501C;margin-top:0}p{color:#666;margin-top:0}
.tabs{display:flex;gap:8px;margin-bottom:22px}
.tab{flex:1;padding:12px;border:2px solid #eee;border-radius:10px;cursor:pointer;text-align:center;font-weight:600;color:#666;background:#fff;font-size:14px}
.tab.active{border-color:#E8501C;color:#E8501C;background:#fff8f5}
.panel{display:none}.panel.active{display:block}
label{display:block;font-weight:600;margin:16px 0 6px;color:#222;font-size:14px}
input[type=file]{width:100%;padding:10px;border:2px dashed #e0e0e0;border-radius:10px;font-size:13px}
button{background:#E8501C;color:#fff;border:none;padding:14px;border-radius:32px;font-size:15px;font-weight:700;cursor:pointer;margin-top:20px;width:100%}
button:hover{background:#c43d10}
.note{background:#fff8f5;border-left:4px solid #E8501C;padding:14px 16px;border-radius:8px;margin-top:20px;font-size:12px;color:#555;line-height:1.8}
code{background:#f0f0f0;padding:2px 5px;border-radius:4px;font-size:11px}
.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:5px;margin-top:8px}
.lc{background:#fff8f5;border:1px solid #fdd;border-radius:6px;padding:7px;font-size:10px;text-align:center}
.lc b{color:#E8501C;display:block;font-size:12px}
.smart-badge{background:#E8501C;color:#fff;font-size:10px;padding:2px 8px;border-radius:8px;margin-left:6px}
</style>
</head><body>
<div class="box">
<h1>🖼 Aurevia Pin Maker <span style="background:#E8501C;color:#fff;font-size:11px;padding:3px 10px;border-radius:10px;margin-left:6px">v7 · 24 layouts</span></h1>
<p>La app analiza cada imagen y selecciona el layout más adecuado automáticamente. <span class="smart-badge">✨ Smart Selection</span></p>

<div class="tabs">
  <div class="tab active" onclick="showTab('url',this)">🔗 Desde URL / Drive</div>
  <div class="tab" onclick="showTab('upload',this)">💻 Desde mi PC</div>
</div>

<div id="tab-url" class="panel active">
  <form action="/process" method="post" enctype="multipart/form-data">
    <label>📄 CSV con textos y drive_url</label>
    <input type="file" name="csv_file" accept=".csv" required>
    <button type="submit">⚡ Generar Pines</button>
  </form>
</div>

<div id="tab-upload" class="panel">
  <form action="/process-upload" method="post" enctype="multipart/form-data">
    <label>🖼 Imágenes base (selecciona varias con Ctrl+clic)</label>
    <input type="file" name="images" accept="image/*" multiple required>
    <label>📄 CSV con textos</label>
    <input type="file" name="csv_file" accept=".csv" required>
    <button type="submit">⚡ Generar Pines</button>
  </form>
</div>

<div class="note">
  <b>Columnas CSV:</b> <code>piece_number, filename, content_type, hook, body_text, cta, template, drive_url</code><br>
  <b>template = auto</b> → selección inteligente por imagen + content_type<br>
  <b>content_type:</b> <code>money_post</code> | <code>informative</code> | <code>retention</code><br><br>
  <b>24 Layouts:</b>
  <div class="grid">
    <div class="lc"><b>layout_1</b>Fondo blanco + marco</div>
    <div class="lc"><b>layout_2</b>Coral abajo</div>
    <div class="lc"><b>layout_3</b>Caja semitrans</div>
    <div class="lc"><b>layout_4</b>62% + separador</div>
    <div class="lc"><b>layout_5</b>Marco interior</div>
    <div class="lc"><b>layout_6</b>Caja coral arriba</div>
    <div class="lc"><b>layout_7</b>Caja blanca centro</div>
    <div class="lc"><b>layout_8</b>Dos cajas apiladas</div>
    <div class="lc"><b>layout_9</b>Círculo deco</div>
    <div class="lc"><b>layout_10</b>Texto gigante</div>
    <div class="lc"><b>layout_11</b>Crema + oval</div>
    <div class="lc"><b>layout_12</b>Rosa + elipse</div>
    <div class="lc"><b>layout_13</b>Minimal top</div>
    <div class="lc"><b>layout_14</b>Left-aligned bold</div>
    <div class="lc"><b>layout_15</b>Marco fino + caja</div>
    <div class="lc"><b>layout_16</b>Collage 3 fotos</div>
    <div class="lc"><b>layout_17</b>Arco decorativo</div>
    <div class="lc"><b>layout_18</b>65% + pill + título</div>
    <div class="lc"><b>layout_19</b>Barra coral lateral</div>
    <div class="lc"><b>layout_20</b>Caja sepia centro</div>
    <div class="lc"><b>layout_21</b>70% + fondo oscuro</div>
    <div class="lc"><b>layout_22</b>Esquinas deco</div>
    <div class="lc"><b>layout_23</b>Hook grande top-left</div>
    <div class="lc"><b>layout_24</b>Triple caja apilada</div>
  </div>
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
</body></html>"""


@app.post("/process")
async def process_urls(csv_file: UploadFile = File(...)):
    content = (await csv_file.read()).decode("utf-8-sig")
    reader  = csv.DictReader(io.StringIO(content))
    buf     = io.BytesIO()
    errors  = []
    with zipfile.ZipFile(buf,"w",zipfile.ZIP_DEFLATED) as zf:
        for i, row in enumerate(reader,1):
            fname = row.get("filename",f"pin_{i:03d}.jpg")
            try:
                url = row.get("drive_url","").strip()
                if not url: raise ValueError("drive_url vacía")
                img = load_from_url(url)
                jpg = apply_template(img, row)
                zf.writestr(fname.rsplit(".",1)[0]+"_pin.jpg", jpg)
            except Exception as e:
                errors.append(f"{fname}: {e}")
        if errors:
            zf.writestr("errors.txt","\n".join(errors))
    buf.seek(0)
    return StreamingResponse(buf, media_type="application/zip",
        headers={"Content-Disposition":"attachment; filename=aurevia_pins.zip"})


@app.post("/process-upload")
async def process_upload(images: List[UploadFile]=File(...), csv_file: UploadFile=File(...)):
    image_map = {}
    for upload in images:
        data = await upload.read()
        image_map[upload.filename] = data
    content = (await csv_file.read()).decode("utf-8-sig")
    reader  = csv.DictReader(io.StringIO(content))
    buf     = io.BytesIO()
    errors  = []
    with zipfile.ZipFile(buf,"w",zipfile.ZIP_DEFLATED) as zf:
        for i, row in enumerate(reader,1):
            fname = row.get("filename",f"pin_{i:03d}.jpg").strip()
            try:
                if fname not in image_map:
                    raise ValueError(f"Imagen '{fname}' no encontrada")
                img = load_from_bytes(image_map[fname])
                jpg = apply_template(img, row)
                zf.writestr(fname.rsplit(".",1)[0]+"_pin.jpg", jpg)
            except Exception as e:
                errors.append(f"{fname}: {e}")
        if errors:
            zf.writestr("errors.txt","\n".join(errors))
    buf.seek(0)
    return StreamingResponse(buf, media_type="application/zip",
        headers={"Content-Disposition":"attachment; filename=aurevia_pins.zip"})
