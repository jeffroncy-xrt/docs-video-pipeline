import math
from PIL import Image, ImageDraw, ImageFilter
import viz
from viz import (W,H,GOLD,GOLD_BR,RED,RED_BR,CREAM,MUTE,base_bg,glow_text,
                 draw_dna,wrap,caption_bar,disp,disp_r,body,body_b,serif_i)
from maprender import render_map

def spaced(d,xy,text,fnt,fill,ls=6,anchor_left=True):
    x,y=xy
    for ch in text:
        d.text((x,y),ch,font=fnt,fill=fill)
        x+=d.textlength(ch,font=fnt)+ls

def kicker(img,text,y=140):
    d=ImageDraw.Draw(img)
    fnt=body_b(28)
    d.rectangle([150,y+14,186,y+17],fill=GOLD)
    spaced(d,(200,y),text.upper(),fnt,GOLD,ls=6)

def headline(img,text,y=300,size=118,fill=CREAM,maxw=W-300,glow=(70,40,20)):
    d=ImageDraw.Draw(img)
    fnt=disp(size)
    lines=wrap(d,text,fnt,maxw)
    yy=y
    for ln in lines:
        glow_text(img,(150,yy),ln,fnt,fill,glow,gblur=12,gmul=1)
        yy+=int(size*0.92)
    return yy

# ---------------------------------------------------------------------------
# Kinetic card helpers — animated background + staggered text-in layers
# ---------------------------------------------------------------------------

def _glow_text_rgba(canvas, xy, text, fnt, fill, glow_color,
                    anchor="la", gblur=10):
    """Draw glowing text onto an RGBA transparent canvas.

    Returns the modified RGBA canvas (alpha_composite creates a new image
    each time, so callers must capture the return value).
    """
    glow_l = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow_l)
    gd.text(xy, text, font=fnt, fill=(*glow_color, 180), anchor=anchor)
    glow_l = glow_l.filter(ImageFilter.GaussianBlur(gblur))
    canvas = Image.alpha_composite(canvas, glow_l)
    ImageDraw.Draw(canvas).text(xy, text, font=fnt,
                                fill=(*fill, 255), anchor=anchor)
    return canvas


def _draw_title_dna(img):
    """Render the title-card DNA helix onto *img* and return the result."""
    return draw_dna(img, W//2, H//2-40, 720, turns=3.0, amp=150)


def _draw_outro_dna(img):
    """Render the outro-card DNA helix onto *img* and return the result."""
    return draw_dna(img, W//2, H//2-30, 640, turns=2.6, amp=120)


def compose_bg(beat):
    """Background + structural decorative elements only — no text.

    Supports 'title' and 'chapter' scenes only.  Used by build_v2's kinetic
    card branch to animate the background separately from the text layers.
    """
    s = beat['scene']
    img = base_bg(beat.get('seed', 0))

    if s == 'title':
        img = _draw_title_dna(img)
        ov = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        od = ImageDraw.Draw(ov)
        od.rectangle([0, H//2-150, W, H//2+200], fill=(0, 0, 0, 120))
        img = Image.alpha_composite(
            img.convert('RGBA'),
            ov.filter(ImageFilter.GaussianBlur(60))
        ).convert('RGB')
    # chapter: plain base_bg is fine

    return img


def compose_text_layers(beat):
    """Return (kicker_rgba, headline_rgba) for staggered text fade-in.

    Implemented for 'title' and 'chapter' scenes.  Both images are 1920x1080
    RGBA with a transparent background so ffmpeg's overlay filter can composite
    them over the animated background with per-layer fade timing.

    Raises NotImplementedError for any scene other than title/chapter so
    misuse fails loudly at the call site rather than crashing later.
    """
    s = beat['scene']
    _dummy_draw = ImageDraw.Draw(Image.new('RGB', (4, 4)))  # for textlength only

    if s == 'title':
        # --- kicker layer ---
        kk = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        kd = ImageDraw.Draw(kk)
        kick = beat.get('kicker', 'THE FORGOTTEN PEOPLE')
        spaced(kd, (W//2-300, H//2-150), kick, body_b(30), GOLD, ls=10)

        # --- headline layer (l1 + l2) ---
        hd = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        l1 = beat.get('line1', 'MELUNGEON')
        l2 = beat.get('line2', 'MYSTERY')
        hd = _glow_text_rgba(hd, (W//2, H//2+30), l1, disp(190), CREAM,
                             (120, 70, 30), anchor="ma", gblur=18)
        hd = _glow_text_rgba(hd, (W//2, H//2+210), l2, disp(190), RED_BR,
                             (150, 40, 20), anchor="ma", gblur=22)
        return kk, hd

    if s == 'chapter':
        # --- kicker layer: gold vertical rule + kicker text ---
        kk = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        kd = ImageDraw.Draw(kk)
        kd.line([(150, H//2-120), (150, H//2+120)],
                fill=(*GOLD, 255), width=4)
        spaced(kd, (210, H//2-110),
               beat.get('kicker', 'CHAPTER').upper(), body_b(30), GOLD, ls=8)

        # --- headline layer ---
        hd = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        fnt = disp(150)
        lines = wrap(_dummy_draw, beat['headline'], fnt, W-420)
        yy = H//2-60
        for ln in lines:
            hd = _glow_text_rgba(hd, (210, yy), ln, fnt, CREAM,
                                 (80, 45, 20), gblur=14)
            yy += 140
        return kk, hd

    raise NotImplementedError(f"compose_text_layers does not support scene {s!r}")


def compose(beat):
    s=beat['scene']; img=base_bg(beat.get('seed',0))
    cap=beat.get('cap','')

    if s=='title':
        img=_draw_title_dna(img)
        d=ImageDraw.Draw(img)
        # darken center band for text
        ov=Image.new('RGBA',(W,H),(0,0,0,0));od=ImageDraw.Draw(ov)
        od.rectangle([0,H//2-150,W,H//2+200],fill=(0,0,0,120))
        img=Image.alpha_composite(img.convert('RGBA'),ov.filter(ImageFilter.GaussianBlur(60))).convert('RGB')
        d=ImageDraw.Draw(img)
        kick=beat.get('kicker',"THE FORGOTTEN PEOPLE"); l1=beat.get('line1',"MELUNGEON"); l2=beat.get('line2',"MYSTERY")
        spaced(d,(W//2-300,H//2-150),kick,body_b(30),GOLD,ls=10)
        glow_text(img,(W//2,H//2+30),l1,disp(190),CREAM,(120,70,30),anchor="ma",gblur=18,gmul=1)
        glow_text(img,(W//2,H//2+210),l2,disp(190),RED_BR,(150,40,20),anchor="ma",gblur=22,gmul=1)
        return img

    if s=='chapter':
        d=ImageDraw.Draw(img)
        d.line([(150,H//2-120),(150,H//2+120)],fill=GOLD,width=4)
        # No 'CHAPTER' fallback: the word itself is what the user asked to lose
        # (2026-08-16).  A kicker the writer supplied still shows; nothing is
        # invented to fill the space.
        if beat.get('kicker'):
            spaced(d,(210,H//2-110),beat['kicker'].upper(),body_b(30),GOLD,ls=8)
        fnt=disp(150)
        lines=wrap(d,beat['headline'],fnt,W-420)
        yy=H//2-60
        for ln in lines:
            glow_text(img,(210,yy),ln,fnt,CREAM,(80,45,20),gblur=14,gmul=1);yy+=140
        return img

    if s=='map':
        mp,_=render_map(int(W*0.62),int(H*0.86),highlight=beat.get('state','Tennessee'))
        img=img.convert('RGBA'); img.alpha_composite(mp,(int(W*0.36),int(H*0.10))); img=img.convert('RGB')
        kicker(img,beat.get('kicker','APPALACHIA'))
        headline(img,beat['headline'],y=300,size=96,maxw=int(W*0.46))
        return caption_bar(img,cap)

    if s in ('evidence', 'dna'):
        img=draw_dna(img,int(W*0.74),H//2,820,turns=3.2,amp=150)
        kicker(img,beat.get('kicker','THE EVIDENCE'))
        headline(img,beat['headline'],y=300,size=104,maxw=int(W*0.5))
        return caption_bar(img,cap)

    if s=='theory':
        d=ImageDraw.Draw(img)
        num=beat.get('num','01')
        glow_text(img,(150,210),num,disp(260),(40,70,58),(20,40,30),gblur=2,gmul=0)
        d.text((150,210),num,font=disp(260),fill=(46,86,72))
        kicker(img,beat.get('kicker','THE THEORIES'),y=200)
        headline(img,beat['headline'],y=470,size=110,maxw=W-300)
        return caption_bar(img,cap)

    if s=='fact':
        d=ImageDraw.Draw(img)
        kicker(img,beat.get('kicker','WHAT THE DNA SAID'))
        big=beat['headline']
        glow_text(img,(W//2,H//2-30),big,disp(150),GOLD_BR,(120,80,20),anchor="mm",gblur=16,gmul=1)
        if beat.get('sub'):
            d.text((W//2,H//2+110),beat['sub'],font=serif_i(48),fill=MUTE,anchor="ma")
        return caption_bar(img,cap)

    if s=='reveal':
        d=ImageDraw.Draw(img)
        ov=Image.new('RGBA',(W,H),(0,0,0,0));od=ImageDraw.Draw(ov)
        od.ellipse([W//2-700,H//2-400,W//2+700,H//2+400],fill=(120,30,15,90))
        img=Image.alpha_composite(img.convert('RGBA'),ov.filter(ImageFilter.GaussianBlur(140))).convert('RGB')
        kicker(img,beat.get('kicker','THE TRUTH'))
        headline(img,beat['headline'],y=int(H*0.30),size=120,fill=CREAM,glow=(150,40,20))
        return caption_bar(img,cap)

    if s=='outro':
        img=_draw_outro_dna(img)
        d=ImageDraw.Draw(img)
        glow_text(img,(W//2,H//2+180),beat['headline'],disp(96),CREAM,(120,60,30),anchor="ma",gblur=12,gmul=1)
        d.text((W//2,H//2+300),beat.get('sub',''),font=body(40),fill=GOLD,anchor="ma")
        return img

    # plain
    kicker(img,beat.get('kicker','MELUNGEON'))
    headline(img,beat['headline'],y=320,size=100)
    return caption_bar(img,cap)

if __name__=='__main__':
    samples=[
     {'scene':'title'},
     {'scene':'chapter','kicker':'Chapter One','headline':'The Lost People'},
     {'scene':'map','kicker':'Hawkins County, TN','headline':'Families nobody could place','caption':'They were already there when the first settlers arrived.','seed':3},
     {'scene':'theory','num':'03','kicker':'The Theories','headline':'Shipwrecked Turks & Moors','caption':'One popular theory said they descended from Ottoman sailors.','seed':5},
     {'scene':'fact','headline':'AFRICAN','sub':'the paternal line','caption':'Many direct male lines carried a sub-Saharan African Y-chromosome.','seed':9},
     {'scene':'reveal','kicker':'The Truth','headline':'The mystery collapses into one answer','caption':'Not Portuguese. Not a lost colony.','seed':11},
    ]
    thumbs=[]
    for i,b in enumerate(samples):
        im=compose(b); im.save(f'/tmp/card_{i}.png'); thumbs.append(im.resize((W//3,H//3)))
    sheet=Image.new('RGB',(W//3*2,H//3*3),(0,0,0))
    for i,t in enumerate(thumbs):
        sheet.paste(t,((i%2)*(W//3),(i//2)*(H//3)))
    sheet.save('/tmp/contact.png'); print('rendered',len(samples),'cards')
