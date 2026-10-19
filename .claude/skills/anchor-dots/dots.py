"""Paired-anchor-dot proposal tool for registering any source image onto the canvas.

One work folder per source (default scratchpad/dots/<source stem>/) holds config.json, picks.json
(the hand-edited list), dots.json (built) and every render. Run from the repo root with the mapgen
venv. Subcommands (see SKILL.md for the workflow):

  init     --src PATH [--canvas PATH] [--ora PATH] [--work DIR]   set up a work folder, masks, previews
  crop     s|c x0 y0 x1 y1 [--h H]           one image, gridded (canvas gets coast + river trace)
  pair     sx0 sy0 sx1 sy1 cx0 cy0 cx1 cy1 [--h H]   source | canvas side by side, dots drawn
  tile     sx0 sy0 size                       source | source warped by current dots | canvas
  water    x0 y0 x1 y1 [--k K]                source crop with water-classified pixels tinted red
  set      name sx sy cx cy [conf] [kind] [--note TEXT] ...   add or move picks ('-' keeps a value)
  del      name ...                           remove picks
  build                                       picks.json -> dots.json (coast snap, unique colours)
  fit                                         affine / thin-plate leave-one-out, folds, worst dots
  render                                      overviews, region pairs, warp blend, disagreement, uncertainty
  sheets                                      the two flat 12 px dot sheets (copies, never the originals)
  all                                         build + fit + render + sheets

--work DIR selects the work folder on every subcommand (default: the most recently initialised one,
recorded in scratchpad/dots/.current).
"""
import argparse, colorsys, json, os, sys, zipfile
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage as nd
from scipy.interpolate import RBFInterpolator
from scipy.spatial import Delaunay, cKDTree

Image.MAX_IMAGE_PIXELS = None
ROOT_SCRATCH = os.path.join('scratchpad', 'dots')
DEFAULT_CANVAS = 'sources/originals/terraqueous_globe_reprojected.png'
DEFAULT_ORA = 'sources/oldworld-first/terraqueous_globe_reprojected - full.ora'
CONF = ('high', 'medium', 'low')
KIND = ('coast', 'point')
# Markup colours used elsewhere in this repo's sheets; a dot never takes one of them.
BANNED = {(0, 255, 255), (255, 0, 255), (174, 102, 213), (255, 127, 0), (0, 0, 255),
          (127, 127, 255), (255, 255, 255), (0, 0, 0), (63, 191, 0)}


# ---------------------------------------------------------------- work folder
def work_dir(args):
    if getattr(args, 'work', None):
        return args.work
    cur = os.path.join(ROOT_SCRATCH, '.current')
    if not os.path.exists(cur):
        sys.exit('no work folder: run init first or pass --work')
    return open(cur).read().strip()


def load_cfg(W):
    return json.load(open(os.path.join(W, 'config.json')))


def load_rgba(path):
    """RGBA array; alpha 0 means no data (erased strokes keep hidden RGB, so never trust RGB there)."""
    return np.array(Image.open(path).convert('RGBA'))


def ora_layer(ora, name):
    with zipfile.ZipFile(ora) as z:
        import xml.etree.ElementTree as ET
        st = ET.fromstring(z.read('stack.xml'))
        for L in st.iter('layer'):
            if L.get('name') == name:
                from io import BytesIO
                a = np.array(Image.open(BytesIO(z.read(L.get('src')))).convert('RGBA'))
                return a[..., 3] > 0
    return None


# ---------------------------------------------------------------- init
def cmd_init(a):
    stem = os.path.splitext(os.path.basename(a.src))[0]
    W = a.work or os.path.join(ROOT_SCRATCH, stem)
    os.makedirs(W, exist_ok=True)
    cfg_path = os.path.join(W, 'config.json')
    cfg = json.load(open(cfg_path)) if os.path.exists(cfg_path) else {}
    cfg.update(src=a.src, canvas=a.canvas or cfg.get('canvas', DEFAULT_CANVAS),
               ora=a.ora if a.ora is not None else cfg.get('ora', DEFAULT_ORA))
    cfg.setdefault('dot_px', 12)
    # Source water rule: a pixel is water when (b-r) > water_br and (g-r) > water_gr.
    # Tune per source by eye on water_check.png (shallow rims, ice and painted rivers vary).
    cfg.setdefault('water_br', 12)
    cfg.setdefault('water_gr', 8)
    cfg.setdefault('regions', {})
    json.dump(cfg, open(cfg_path, 'w'), indent=1)
    os.makedirs(ROOT_SCRATCH, exist_ok=True)
    open(os.path.join(ROOT_SCRATCH, '.current'), 'w').write(W)

    s = load_rgba(cfg['src'])
    print('source', s.shape[1], 'x', s.shape[0], ' alpha-0 share %.3f' % (s[..., 3] == 0).mean())
    water, land = src_water(s, cfg)
    coast = land & nd.binary_dilation(water, structure=[[0, 1, 0], [1, 1, 1], [0, 1, 0]])
    np.save(os.path.join(W, 'src_coast.npy'), coast)
    np.save(os.path.join(W, 'src_water.npy'), water)
    # canvas traces
    if cfg['ora'] and os.path.exists(cfg['ora']):
        for nm in ('coasts', 'rivers'):
            m = ora_layer(cfg['ora'], nm)
            if m is not None:
                np.save(os.path.join(W, f'canvas_{nm}.npy'), m)
                print('canvas layer', nm, int(m.sum()), 'px')
    else:
        print('no .ora: canvas coast snapping and river overlay disabled')
    # previews
    k = min(1.0, 1600 / s.shape[1])
    o = s[..., :3].astype(float) * 0.55
    o[coast] = [255, 40, 40]
    Image.fromarray(o.astype(np.uint8)).resize((int(s.shape[1] * k), int(s.shape[0] * k)), Image.LANCZOS) \
        .save(os.path.join(W, 'water_check.png'))
    Image.fromarray(s[..., :3]).resize((int(s.shape[1] * k), int(s.shape[0] * k)), Image.LANCZOS) \
        .save(os.path.join(W, 'src_preview.png'))
    c = Image.open(cfg['canvas']).convert('RGB')
    c.resize((c.width // 4, c.height // 4), Image.LANCZOS).save(os.path.join(W, 'canvas_preview.png'))
    if not os.path.exists(os.path.join(W, 'picks.json')):
        json.dump({}, open(os.path.join(W, 'picks.json'), 'w'))
    print('work folder', W, '\nlook at water_check.png (red = detected source coast) before snapping')


def src_water(s, cfg):
    r, g, b, al = (s[..., i].astype(int) for i in range(4))
    water = ((b - r) > cfg['water_br']) & ((g - r) > cfg['water_gr']) & (al > 0)
    land = ~water & (al > 0)
    lab, _ = nd.label(land); ar = np.bincount(lab.ravel()); land = (ar[lab] >= 40) & (lab > 0)
    lab, _ = nd.label(~land & (al > 0)); ar = np.bincount(lab.ravel()); water = (ar[lab] >= 25) & (lab > 0)
    return water, ~water & (al > 0)


# ---------------------------------------------------------------- drawing helpers
def images(cfg):
    S = Image.open(cfg['src']).convert('RGB')
    C = Image.open(cfg['canvas']).convert('RGB')
    return S, C


def canvas_crop(W, C, b):
    a = np.array(C.crop(b))
    for nm, col in (('coasts', (0, 200, 200)), ('rivers', (0, 0, 255))):
        p = os.path.join(W, f'canvas_{nm}.npy')
        if os.path.exists(p):
            m = np.load(p, mmap_mode='r')[b[1]:b[3], b[0]:b[2]]
            a[np.asarray(m)] = col
    return Image.fromarray(a)


def grid_step(k):
    for s in (2, 5, 10, 20, 25, 50, 100, 200, 500):
        if s * k >= 28:
            return s
    return 1000


def draw_grid(im, b, k):
    d = ImageDraw.Draw(im); st = grid_step(k)
    for g in range((b[0] // st + 1) * st, b[2], st):
        X = (g - b[0]) * k
        d.line([(X, 0), (X, im.height)], fill=(255, 0, 0) if g % (st * 5) == 0 else (255, 255, 0))
        d.text((X + 2, 2), str(g), fill=(255, 0, 0), stroke_width=2, stroke_fill=(255, 255, 255))
    for g in range((b[1] // st + 1) * st, b[3], st):
        Y = (g - b[1]) * k
        d.line([(0, Y), (im.width, Y)], fill=(255, 0, 0) if g % (st * 5) == 0 else (255, 255, 0))
        d.text((2, Y + 2), str(g), fill=(255, 0, 0), stroke_width=2, stroke_fill=(255, 255, 255))
    return d


def draw_dots(d, dots, key, b, k, label='name'):
    for i, o in enumerate(dots):
        x, y = o[key]
        if b[0] <= x < b[2] and b[1] <= y < b[3]:
            X, Y = (x - b[0]) * k, (y - b[1]) * k
            d.ellipse([X - 6, Y - 6, X + 6, Y + 6], fill=tuple(o['rgb']) if label == 'num' else None,
                      outline=(255, 0, 255) if label == 'name' else (0, 0, 0), width=2)
            t = o['name'] if label == 'name' else str(i + 1)
            d.text((X + 8, Y - 8), t, fill=(255, 255, 255), stroke_width=2, stroke_fill=(0, 0, 0))


def panel(W, im, b, H, dots, key, canvas=False, label='name'):
    k = H / (b[3] - b[1])
    base = canvas_crop(W, im, b) if canvas else im.crop(b)
    p = base.resize((max(1, int((b[2] - b[0]) * k)), H), Image.LANCZOS)
    d = draw_grid(p, b, k); draw_dots(d, dots, key, b, k, label)
    return p


def side_by_side(a, b, out):
    o = Image.new('RGB', (a.width + b.width + 10, max(a.height, b.height)), (30, 30, 30))
    o.paste(a, (0, 0)); o.paste(b, (a.width + 10, 0)); o.save(out)
    return out


def load_dots(W):
    p = os.path.join(W, 'dots.json')
    return json.load(open(p)) if os.path.exists(p) else []


# ---------------------------------------------------------------- inspection commands
def cmd_crop(a):
    W = work_dir(a); cfg = load_cfg(W); S, C = images(cfg); dots = load_dots(W)
    b = (a.x0, a.y0, a.x1, a.y1)
    p = panel(W, C if a.which == 'c' else S, b, a.h, dots, 'canvas' if a.which == 'c' else 'src', a.which == 'c')
    out = os.path.join(W, 'crop.png'); p.save(out); print(out, p.size)


def cmd_pair(a):
    W = work_dir(a); cfg = load_cfg(W); S, C = images(cfg); dots = load_dots(W)
    out = side_by_side(panel(W, S, (a.sx0, a.sy0, a.sx1, a.sy1), a.h, dots, 'src'),
                       panel(W, C, (a.cx0, a.cy0, a.cx1, a.cy1), a.h, dots, 'canvas', True),
                       os.path.join(W, 'pair.png'))
    print(out)


def cmd_water(a):
    W = work_dir(a); cfg = load_cfg(W)
    s = load_rgba(cfg['src'])[a.y0:a.y1, a.x0:a.x1]
    water, _ = src_water(np.pad(s, ((1, 1), (1, 1), (0, 0)), mode='edge'), cfg)
    water = water[1:-1, 1:-1]
    r, g, b = (s[..., i].astype(int) for i in range(3))
    raw = ((b - r) > cfg['water_br']) & ((g - r) > cfg['water_gr'])
    o = s[..., :3].astype(float); o[raw] = o[raw] * 0.4 + np.array([255, 0, 0]) * 0.6
    im = Image.fromarray(o.astype(np.uint8)).resize(((a.x1 - a.x0) * a.k, (a.y1 - a.y0) * a.k), Image.NEAREST)
    draw_grid(im, (a.x0, a.y0, a.x1, a.y1), a.k)
    out = os.path.join(W, 'water.png'); im.save(out); print(out)


def tps(Sx, Cx):
    return RBFInterpolator(Sx, Cx, kernel='thin_plate_spline')


def cmd_tile(a):
    W = work_dir(a); cfg = load_cfg(W); S, C = images(cfg); dots = load_dots(W)
    if len(dots) < 4:
        sys.exit('tile needs at least 4 dots')
    Sx = np.array([o['src'] for o in dots], float); Cx = np.array([o['canvas'] for o in dots], float)
    fwd, inv = tps(Sx, Cx), tps(Cx, Sx)
    x0, y0, n = a.sx0, a.sy0, a.size
    cs = fwd(np.array([[x0, y0], [x0 + n, y0], [x0, y0 + n], [x0 + n, y0 + n], [x0 + n / 2, y0 + n / 2]], float))
    half = max(np.ptp(cs[:4, 0]), np.ptp(cs[:4, 1])) / 2 * 1.15
    cb = (int(cs[4, 0] - half), int(cs[4, 1] - half), int(cs[4, 0] + half), int(cs[4, 1] + half))
    P = 600
    ys, xs = np.mgrid[0:P:4, 0:P:4]
    q = np.c_[cb[0] + xs.ravel() * (cb[2] - cb[0]) / P, cb[1] + ys.ravel() * (cb[3] - cb[1]) / P]
    sm = inv(q).reshape(ys.shape + (2,)); yy, xx = np.mgrid[0:P, 0:P]
    mx = nd.map_coordinates(sm[..., 0], [yy / 4, xx / 4], order=1); my = nd.map_coordinates(sm[..., 1], [yy / 4, xx / 4], order=1)
    sa = np.array(S).astype(float)
    w = np.stack([nd.map_coordinates(sa[..., c], [my, mx], order=1, cval=0) for c in range(3)], -1).astype(np.uint8)
    wp = Image.fromarray(w); k = P / (cb[2] - cb[0]); d = draw_grid(wp, cb, k); draw_dots(d, dots, 'canvas', cb, k)
    a1 = panel(W, S, (x0, y0, x0 + n, y0 + n), P, dots, 'src')
    a3 = panel(W, C, cb, P, dots, 'canvas', True)
    o = Image.new('RGB', (3 * P + 20, P), (30, 30, 30)); o.paste(a1, (0, 0)); o.paste(wp, (P + 10, 0)); o.paste(a3, (2 * P + 20, 0))
    out = os.path.join(W, 'tile.png'); o.save(out); print(out, 'canvas box', cb)


# ---------------------------------------------------------------- picks
def load_picks(W):
    return json.load(open(os.path.join(W, 'picks.json')))


def save_picks(W, P):
    json.dump(P, open(os.path.join(W, 'picks.json'), 'w'), indent=1)


def cmd_set(a):
    W = work_dir(a); P = load_picks(W); t = a.items; i = 0
    while i < len(t):
        n = t[i]; v = t[i + 1:i + 5]; i += 5
        o = P.get(n, dict(s=[0, 0], c=[0, 0], conf='low', kind='coast', note=''))
        val = lambda s, old: old if s == '-' else int(s)
        o['s'] = [val(v[0], o['s'][0]), val(v[1], o['s'][1])]
        o['c'] = [val(v[2], o['c'][0]), val(v[3], o['c'][1])]
        while i < len(t) and t[i] in CONF + KIND:
            o['conf' if t[i] in CONF else 'kind'] = t[i]; i += 1
        if a.note is not None:
            o['note'] = a.note
        P[n] = o
    save_picks(W, P); print(len(P), 'picks')


def cmd_del(a):
    W = work_dir(a); P = load_picks(W)
    for n in a.names:
        P.pop(n, None)
    save_picks(W, P); print(len(P), 'picks')


# ---------------------------------------------------------------- build
def snap(m, x, y, r):
    y0, x0 = max(0, y - r), max(0, x - r)
    w = np.asarray(m[y0:y + r + 1, x0:x + r + 1]); ys, xs = np.nonzero(w)
    if not len(xs):
        return [x, y]
    k = np.argmin((xs + x0 - x) ** 2 + (ys + y0 - y) ** 2)
    if np.hypot(xs[k] + x0 - x, ys[k] + y0 - y) > r:
        return [x, y]
    return [int(xs[k] + x0), int(ys[k] + y0)]


def cmd_build(a):
    W = work_dir(a); P = load_picks(W)
    old = {o['name']: o for o in load_dots(W)}
    sc = np.load(os.path.join(W, 'src_coast.npy'), mmap_mode='r')
    cp = os.path.join(W, 'canvas_coasts.npy'); cc = np.load(cp, mmap_mode='r') if os.path.exists(cp) else None
    used = {tuple(old[n]['rgb']) for n in P if n in old}

    def newc(seed):
        k = seed
        while True:
            h = (k * 0.618034) % 1; sat = (1.0, 0.8, 0.6)[k % 3]; v = (1.0, 0.85, 0.7)[(k // 3) % 3]
            c = tuple(int(round(t * 255)) for t in colorsys.hsv_to_rgb(h, sat, v))
            if c not in used and c not in BANNED:
                used.add(c); return list(c)
            k += 1
    out = []
    for i, (n, p) in enumerate(P.items()):
        s, c = p['s'], p['c']
        if p['kind'] == 'coast':
            s = snap(sc, *p['s'], 4)
            if cc is not None:
                c = snap(cc, *p['c'], 10)
        rgb = old[n]['rgb'] if n in old else newc(len(used) * 7 + i)
        out.append(dict(name=n, src=s, canvas=c, rgb=rgb, confidence=p['conf'], kind=p['kind'],
                        note=p.get('note', ''), pick_src=p['s'], pick_canvas=p['c']))
    # overlap check: 12 px discs must not touch on either sheet
    dp = load_cfg(W)['dot_px']
    for key in ('src', 'canvas'):
        X = np.array([o[key] for o in out], float)
        if len(X) > 1:
            D = np.hypot(*(X[:, None] - X[None]).transpose(2, 0, 1)); np.fill_diagonal(D, 1e9)
            for i, j in zip(*np.nonzero(D < dp + 1)):
                if i < j:
                    print(f'WARN {key}: {out[i]["name"]} and {out[j]["name"]} overlap ({D[i, j]:.1f} px)')
    json.dump(out, open(os.path.join(W, 'dots.json'), 'w'), indent=1)
    print(len(out), 'dots')


# ---------------------------------------------------------------- fit
def loo(Sx, Cx, kind):
    e = []
    for i in range(len(Sx)):
        m = np.arange(len(Sx)) != i
        if kind == 'affine':
            A = np.c_[Sx[m], np.ones(m.sum())]; M, *_ = np.linalg.lstsq(A, Cx[m], rcond=None)
            p = np.r_[Sx[i], 1] @ M
        else:
            p = tps(Sx[m], Cx[m])(Sx[i:i + 1])[0]
        e.append(float(np.hypot(*(p - Cx[i]))))
    return np.array(e)


def cmd_fit(a):
    W = work_dir(a); dots = load_dots(W)
    Sx = np.array([o['src'] for o in dots], float); Cx = np.array([o['canvas'] for o in dots], float)
    ea, et = loo(Sx, Cx, 'affine'), loo(Sx, Cx, 'tps')
    for nm, e in (('affine', ea), ('thin-plate', et)):
        print(f'{nm:10s} LOO median {np.median(e):6.1f}  p95 {np.percentile(e, 95):6.1f}  max {e.max():6.1f}')
    nn = cKDTree(Cx).query(Cx, k=2)[0][:, 1]
    print('error per unit nearest-dot distance: median %.2f, p75 %.2f' % (np.median(et / nn), np.percentile(et / nn, 75)))
    for c in CONF:
        ix = [i for i, o in enumerate(dots) if o['confidence'] == c]
        if ix:
            print(f'  {c:6s} n={len(ix):3d} median LOO {np.median(et[ix]):6.1f}')
    print('worst:')
    for i in np.argsort(-et)[:12]:
        print(f'  {i + 1:3d} {dots[i]["name"]:24s} {et[i]:6.1f}  (affine {ea[i]:6.1f})  {dots[i]["confidence"]}')
    # folds of the canvas->source map inside the hull
    inv = tps(Cx, Sx); gy, gx = np.mgrid[0:Cx[:, 1].max():20, 0:Cx[:, 0].max():20]
    q = np.c_[gx.ravel(), gy.ravel()].astype(float); q = q[Delaunay(Cx).find_simplex(q) >= 0]
    p = inv(q); J = np.stack([inv(q + [1, 0]) - p, inv(q + [0, 1]) - p], 2)
    det = J[:, 0, 0] * J[:, 1, 1] - J[:, 0, 1] * J[:, 1, 0]
    print('folds inside hull:', int((det <= 0).sum()), 'of', len(q), 'grid points')
    for i, o in enumerate(dots):
        o['loo_tps_canvas_px'] = round(et[i], 1); o['loo_affine_canvas_px'] = round(ea[i], 1)
    json.dump(dots, open(os.path.join(W, 'dots.json'), 'w'), indent=1)


# ---------------------------------------------------------------- render
def cmd_render(a):
    W = work_dir(a); cfg = load_cfg(W); S, C = images(cfg); dots = load_dots(W)
    if 'loo_tps_canvas_px' not in (dots[0] if dots else {}):
        sys.exit('run fit first')
    Sx = np.array([o['src'] for o in dots], float); Cx = np.array([o['canvas'] for o in dots], float)
    e = np.array([o['loo_tps_canvas_px'] for o in dots])
    # overviews
    for im, key, f, sc in ((S, 'src', 'overview_src.png', min(1.0, 1700 / S.width)), (C, 'canvas', 'overview_canvas.png', 0.25)):
        p = im.resize((int(im.width * sc), int(im.height * sc)), Image.LANCZOS); d = ImageDraw.Draw(p)
        for i, o in enumerate(dots):
            X, Y = o[key][0] * sc, o[key][1] * sc
            d.ellipse([X - 5, Y - 5, X + 5, Y + 5], fill=tuple(o['rgb']), outline=(0, 0, 0))
            d.text((X + 7, Y - 6), str(i + 1), fill=(255, 255, 255), stroke_width=2, stroke_fill=(0, 0, 0))
        p.save(os.path.join(W, f))
    # region pairs: configured boxes, else clusters of dots
    regions = cfg.get('regions') or auto_regions(dots)
    for name, r in regions.items():
        side_by_side(panel(W, S, tuple(r['s']), 800, dots, 'src', label='num'),
                     panel(W, C, tuple(r['c']), 800, dots, 'canvas', True, label='num'),
                     os.path.join(W, f'rev_{name}.png'))
    # warp blend, quarter scale
    sc = 0.25; Wc, Hc = int(C.width * sc), int(C.height * sc); inv = tps(Cx, Sx); st = 4
    gy, gx = np.mgrid[0:Hc:st, 0:Wc:st]; src = inv(np.c_[gx.ravel(), gy.ravel()] / sc).reshape(gy.shape + (2,))
    yy, xx = np.mgrid[0:Hc, 0:Wc]
    sx = nd.map_coordinates(src[..., 0], [yy / st, xx / st], order=1); sy = nd.map_coordinates(src[..., 1], [yy / st, xx / st], order=1)
    sa = load_rgba(cfg['src']).astype(float)
    out = np.stack([nd.map_coordinates(sa[..., c], [sy, sx], order=1, cval=0) for c in range(4)], -1)
    hull = (Delaunay(Cx).find_simplex(np.c_[xx.ravel(), yy.ravel()] / sc) >= 0).reshape(Hc, Wc)
    can = np.array(C.resize((Wc, Hc), Image.LANCZOS)).astype(float)
    al = (out[..., 3] / 255 * 0.55 * hull)[..., None]
    img = Image.fromarray((can * (1 - al) + out[..., :3] * al).clip(0, 255).astype(np.uint8)); d = ImageDraw.Draw(img)
    thr = np.percentile(e, 90)
    for i, o in enumerate(dots):
        X, Y = o['canvas'][0] * sc, o['canvas'][1] * sc
        d.ellipse([X - 3, Y - 3, X + 3, Y + 3], fill=tuple(o['rgb']), outline=(0, 0, 0))
        d.text((X + 5, Y - 5), str(i + 1), fill=(255, 255, 255), stroke_width=2, stroke_fill=(0, 0, 0))
        if e[i] >= thr:
            r = e[i] * sc; d.ellipse([X - r, Y - r, X + r, Y + r], outline=(255, 0, 0), width=2)
        elif o['confidence'] == 'low':
            d.ellipse([X - 6, Y - 6, X + 6, Y + 6], outline=(255, 200, 0), width=1)
    img.save(os.path.join(W, 'warp_blend.png'))
    # disagreement arrows
    im = Image.blend(C.resize((Wc, Hc), Image.LANCZOS), Image.new('RGB', (Wc, Hc), (255, 255, 255)), 0.35); d = ImageDraw.Draw(im)
    for i, o in enumerate(dots):
        m = np.arange(len(dots)) != i; p = tps(Sx[m], Cx[m])(Sx[i:i + 1])[0]
        col = (40, 160, 60) if e[i] < 50 else (230, 160, 0) if e[i] < 120 else (220, 30, 30)
        A, B = Cx[i] * sc, p * sc; d.line([tuple(A), tuple(B)], fill=col, width=2); v = B - A; L = np.hypot(*v)
        if L > 3:
            u = v / L; nrm = np.array([-u[1], u[0]]); d.polygon([tuple(B), tuple(B - u * 6 + nrm * 3), tuple(B - u * 6 - nrm * 3)], fill=col)
        d.ellipse([A[0] - 3, A[1] - 3, A[0] + 3, A[1] + 3], fill=tuple(o['rgb']), outline=(0, 0, 0)); d.text((A[0] + 4, A[1] - 10), str(i + 1), fill=(0, 0, 0))
    d.rectangle([5, Hc - 60, 470, Hc - 5], fill=(255, 255, 255), outline=(0, 0, 0))
    d.text((10, Hc - 56), 'dot = canvas point; arrow = where the other dots put its source point', fill=(0, 0, 0))
    for j, (t, col) in enumerate((('< 50 px', (40, 160, 60)), ('50-120 px', (230, 160, 0)), ('> 120 px', (220, 30, 30)))):
        d.line([(12 + j * 120, Hc - 25), (40 + j * 120, Hc - 25)], fill=col, width=3); d.text((45 + j * 120, Hc - 31), t, fill=(0, 0, 0))
    im.save(os.path.join(W, 'disagreement.png'))
    # uncertainty: error ~ k x distance to nearest dot
    nn = cKDTree(Cx).query(Cx, k=2)[0][:, 1]; kk = float(np.median(e / nn))
    dist = cKDTree(Cx).query(np.c_[xx.ravel(), yy.ravel()] / sc)[0].reshape(Hc, Wc) * kk
    col = np.zeros((Hc, Wc, 3)); lo = 0
    for hi, c in ((25, (40, 170, 60)), (50, (200, 200, 40)), (100, (240, 130, 30)), (1e9, (220, 40, 40))):
        col[(dist >= lo) & (dist < hi)] = c; lo = hi
    al = (0.45 * hull)[..., None]; u = Image.fromarray((can * (1 - al) + col * al).astype(np.uint8)); d = ImageDraw.Draw(u)
    d.rectangle([5, Hc - 40, 470, Hc - 5], fill=(255, 255, 255))
    d.text((10, Hc - 36), f'est. error = {kk:.2f} x distance to nearest dot (typical, not a bound)', fill=(0, 0, 0))
    d.text((10, Hc - 20), 'green <25  yellow 25-50  orange 50-100  red >100 canvas px; inside dot hull only', fill=(0, 0, 0))
    u.save(os.path.join(W, 'uncertainty.png'))
    print('rendered into', W)


def auto_regions(dots):
    """Bin dots into 1400x1000 canvas-px cells; each cell with 2+ dots becomes one region pair render."""
    Cx = np.array([o['canvas'] for o in dots], float); Sx = np.array([o['src'] for o in dots], float)
    cell = (Cx[:, 0] // 1400).astype(int) * 100 + (Cx[:, 1] // 1000).astype(int)
    out = {}
    for g in np.unique(cell):
        ix = cell == g
        if ix.sum() < 2:
            continue
        def box(X, pad):
            lo, hi = X[ix].min(0) - pad, X[ix].max(0) + pad
            return [int(max(0, lo[0])), int(max(0, lo[1])), int(hi[0]), int(hi[1])]
        cb, sb = box(Cx, 120), box(Sx, 40)
        out[f'x{g // 100}_y{g % 100}'] = dict(s=sb, c=cb)
    return out


def cmd_sheets(a):
    W = work_dir(a); cfg = load_cfg(W); dots = load_dots(W); dp = cfg['dot_px']; r = dp / 2
    yy, xx = np.mgrid[-dp // 2:dp // 2, -dp // 2:dp // 2] + 0.5; disc = (xx ** 2 + yy ** 2) <= r * r
    stem = os.path.splitext(os.path.basename(cfg['src']))[0]
    cstem = os.path.splitext(os.path.basename(cfg['canvas']))[0]
    for path, key, out in ((cfg['src'], 'src', f'{stem}_dots.png'), (cfg['canvas'], 'canvas', f'{cstem}_dots_{stem}.png')):
        im = Image.open(path); arr = np.array(im.convert('RGBA' if im.mode in ('RGBA', 'LA', 'P') else 'RGB'))
        code = lambda c: (int(c[0]) << 16) | (int(c[1]) << 8) | int(c[2])
        flat = (arr[..., 0].astype(np.int64) << 16) | (arr[..., 1].astype(np.int64) << 8) | arr[..., 2]
        clash = int(np.isin(flat, [code(o['rgb']) for o in dots]).sum())
        ys, xs = np.nonzero(disc)
        for o in dots:
            x, y = o[key]; Y, X = ys + y - dp // 2, xs + x - dp // 2
            ok = (Y >= 0) & (Y < arr.shape[0]) & (X >= 0) & (X < arr.shape[1])
            arr[Y[ok], X[ok], :3] = o['rgb']
            if arr.shape[2] == 4:
                arr[Y[ok], X[ok], 3] = 255
        Image.fromarray(arr).save(os.path.join(W, out))
        chk = np.array(Image.open(os.path.join(W, out)))[..., :3]
        bad = [o['name'] for o in dots if np.all(chk == o['rgb'], axis=2).sum() != disc.sum()]
        print(out, '| original pixels already in a dot colour:', clash, '| dots with wrong pixel count:', bad or 'none')


def cmd_all(a):
    cmd_build(a); cmd_fit(a); cmd_render(a); cmd_sheets(a)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--work')
    sp = ap.add_subparsers(dest='cmd', required=True)
    p = sp.add_parser('init'); p.add_argument('--src', required=True); p.add_argument('--canvas'); p.add_argument('--ora'); p.set_defaults(f=cmd_init)
    p = sp.add_parser('crop'); p.add_argument('which', choices='sc'); [p.add_argument(x, type=int) for x in ('x0', 'y0', 'x1', 'y1')]; p.add_argument('--h', type=int, default=700); p.set_defaults(f=cmd_crop)
    p = sp.add_parser('pair'); [p.add_argument(x, type=int) for x in ('sx0', 'sy0', 'sx1', 'sy1', 'cx0', 'cy0', 'cx1', 'cy1')]; p.add_argument('--h', type=int, default=700); p.set_defaults(f=cmd_pair)
    p = sp.add_parser('tile'); [p.add_argument(x, type=int) for x in ('sx0', 'sy0', 'size')]; p.set_defaults(f=cmd_tile)
    p = sp.add_parser('water'); [p.add_argument(x, type=int) for x in ('x0', 'y0', 'x1', 'y1')]; p.add_argument('--k', type=int, default=4); p.set_defaults(f=cmd_water)
    p = sp.add_parser('set'); p.add_argument('items', nargs='+'); p.add_argument('--note'); p.set_defaults(f=cmd_set)
    p = sp.add_parser('del'); p.add_argument('names', nargs='+'); p.set_defaults(f=cmd_del)
    for nm, f in (('build', cmd_build), ('fit', cmd_fit), ('render', cmd_render), ('sheets', cmd_sheets), ('all', cmd_all)):
        sp.add_parser(nm).set_defaults(f=f)
    a = ap.parse_args()
    if a.cmd == 'init' and a.work is None:
        a.work = None
    a.f(a)


if __name__ == '__main__':
    main()
