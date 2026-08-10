import json
from PIL import Image, ImageDraw, ImageFilter

GEO = json.load(open('assets/us-states.json'))
SKIP = {'Alaska','Hawaii','Puerto Rico'}

def lower48():
    feats=[]
    for f in GEO['features']:
        nm=f['properties'].get('name','')
        if nm in SKIP: continue
        feats.append(f)
    return feats

def all_rings(feat):
    g=feat['geometry']; t=g['type']; out=[]
    if t=='Polygon':
        for ring in g['coordinates']: out.append(ring)
    elif t=='MultiPolygon':
        for poly in g['coordinates']:
            for ring in poly: out.append(ring)
    return out

def bounds():
    xs=[];ys=[]
    for f in lower48():
        for ring in all_rings(f):
            for lon,lat in ring:
                xs.append(lon);ys.append(lat)
    return min(xs),max(xs),min(ys),max(ys)

LON_MIN,LON_MAX,LAT_MIN,LAT_MAX=bounds()

def project(lon,lat,W,H,pad=0.06):
    pw=W*pad; ph=H*pad
    x=pw+(lon-LON_MIN)/(LON_MAX-LON_MIN)*(W-2*pw)
    y=ph+(LAT_MAX-lat)/(LAT_MAX-LAT_MIN)*(H-2*ph)
    return x,y

def render_map(W,H,highlight='Tennessee',
               line=(196,160,84,200), hl=(220,60,40,255), glow=(230,70,40)):
    base=Image.new('RGBA',(W,H),(0,0,0,0))
    d=ImageDraw.Draw(base)
    hl_layer=Image.new('RGBA',(W,H),(0,0,0,0))
    hd=ImageDraw.Draw(hl_layer)
    hifeat=None
    for f in lower48():
        nm=f['properties'].get('name','')
        is_hl = nm==highlight
        for ring in all_rings(f):
            pts=[project(lon,lat,W,H) for lon,lat in ring]
            if is_hl:
                hd.polygon(pts, fill=hl, outline=(245,200,170,255))
            d.line(pts+[pts[0]], fill=line, width=2)
        if is_hl: hifeat=nm
    # glow around highlight
    glowimg=Image.new('RGBA',(W,H),(0,0,0,0))
    gd=ImageDraw.Draw(glowimg)
    for f in lower48():
        if f['properties'].get('name','')!=highlight: continue
        for ring in all_rings(f):
            pts=[project(lon,lat,W,H) for lon,lat in ring]
            gd.polygon(pts, fill=(*glow,255))
    glowimg=glowimg.filter(ImageFilter.GaussianBlur(28))
    out=Image.alpha_composite(base.copy(), glowimg)
    out=Image.alpha_composite(out, hl_layer)
    out=Image.alpha_composite(out, base)
    return out, hifeat

if __name__=='__main__':
    img,hi=render_map(1400,900)
    img.save('/tmp/map_test.png')
    print('highlight found:', hi, 'bounds:', round(LON_MIN,1),round(LON_MAX,1),round(LAT_MIN,1),round(LAT_MAX,1))
    print('saved', img.size)
