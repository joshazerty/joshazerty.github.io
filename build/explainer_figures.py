#!/usr/bin/env python3
"""Draw the figures on the plain-language pages in explained/.

Every figure is inline SVG written straight into its page, so the site keeps
working with no build step. This script is only the authoring tool: edit a
drawing here, run

    python3 build/explainer_figures.py

and it rewrites the <figure class="ex-fig"> blocks in place, keeping each
page's figcaption. Colours come from the --el-* and figure tokens in
assets/css/site.css, so the drawings follow light and dark mode.
"""

import math
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
EXPLAINED = ROOT / "explained"


def f2(v):
    return f"{v:.1f}".rstrip("0").rstrip(".")


def esc_attr(s):
    return s.replace("&", "&amp;").replace('"', "&quot;")


# --------------------------------------------------------------------------
# Drawing canvas
# --------------------------------------------------------------------------

class Fig:
    def __init__(self, pid, w, h, label):
        self.p, self.w, self.h, self.label = pid, w, h, label
        self.els, self.faces, self.body, self.defs = set(), set(), [], []
        self.uses_shadow = self.uses_glow = self.uses_warmglow = False
        self.mobile = False
        self.cls = "fig-d"

    def add(self, *parts):
        self.body.extend(parts)

    # --- atoms and bonds --------------------------------------------------
    def ball(self, x, y, r, el, cls=""):
        self.els.add(el)
        c = f"b b-{el}" + (f" {cls}" if cls else "")
        self.add(f'<circle cx="{f2(x)}" cy="{f2(y)}" r="{f2(r)}" fill="url(#{self.p}-{el})" class="{c}"/>')

    def stick(self, x1, y1, x2, y2, w=4.2, order=1, cls=""):
        dx, dy = x2 - x1, y2 - y1
        L = math.hypot(dx, dy) or 1
        nx, ny = -dy / L, dx / L
        offs = [0] if order == 1 else ([-1, 1] if order == 2 else [-1.6, 0, 1.6])
        gap = w * 0.95
        for o in offs:
            ox, oy = nx * o * gap, ny * o * gap
            a = f'x1="{f2(x1+ox)}" y1="{f2(y1+oy)}" x2="{f2(x2+ox)}" y2="{f2(y2+oy)}"'
            ww = w if order == 1 else w * 0.75
            self.add(f'<line {a} class="stk-o {cls}" stroke-width="{f2(ww+2)}"/>',
                     f'<line {a} class="stk {cls}" stroke-width="{f2(ww)}"/>')

    def molecule(self, atoms, bonds, w=4.2):
        """atoms: list of (el, x, y, r[, z]); bonds: (i, j[, order]).
        Bonds go behind atoms; atoms are painted back to front by z."""
        for b in bonds:
            i, j = b[0], b[1]
            order = b[2] if len(b) > 2 else 1
            self.stick(atoms[i][1], atoms[i][2], atoms[j][1], atoms[j][2], w=w, order=order)
        for a in sorted(atoms, key=lambda a: a[4] if len(a) > 4 else 0):
            self.ball(a[1], a[2], a[3], a[0])

    def water(self, x, y, s=1.0, ang=-90, z=0):
        """A water molecule, oxygen at (x, y), the H's opening towards ang."""
        out = [("o", x, y, 7.2 * s, z)]
        for d in (-52, 52):
            a = math.radians(ang + d)
            out.append(("h", x + 11 * s * math.cos(a), y + 11 * s * math.sin(a), 4.6 * s, z - 1))
        self.molecule(out, [(0, 1), (0, 2)], w=2.8 * s)

    # --- text ------------------------------------------------------------
    def text(self, x, y, s, cls="ft", anchor="middle", extra=""):
        a = {"middle": "", "start": " ts", "end": " te"}[anchor]
        self.add(f'<text x="{f2(x)}" y="{f2(y)}" class="{cls}{a}"{extra}>{s}</text>')

    def lines(self, x, y, rows, cls="ft", anchor="middle", lh=16):
        for i, s in enumerate(rows):
            self.text(x, y + i * lh, s, cls, anchor)

    def tag(self, x, y, s, cls="ftag", anchor="middle"):
        """A small rounded label chip, centred on (x, y)."""
        w = 7.2 * len(re.sub(r"<[^>]+>", "", s)) + 18
        x0 = {"middle": x - w / 2, "start": x, "end": x - w}[anchor]
        self.add(f'<rect x="{f2(x0)}" y="{f2(y-10)}" width="{f2(w)}" height="20" rx="10" class="{cls}-bg"/>')
        self.text(x0 + w / 2, y + 4, s, cls)

    # --- arrows ----------------------------------------------------------
    def arrow(self, x1, y1, x2, y2, cls="far", head=9, ctrl=None, w=None):
        if ctrl:
            tx, ty = x2 - ctrl[0], y2 - ctrl[1]
        else:
            tx, ty = x2 - x1, y2 - y1
        L = math.hypot(tx, ty) or 1
        ux, uy = tx / L, ty / L
        bx, by = x2 - ux * head * 0.85, y2 - uy * head * 0.85
        sw = f' stroke-width="{f2(w)}"' if w else ""
        if ctrl:
            self.add(f'<path d="M{f2(x1)} {f2(y1)}Q{f2(ctrl[0])} {f2(ctrl[1])} {f2(bx)} {f2(by)}" class="{cls}"{sw}/>')
        else:
            self.add(f'<line x1="{f2(x1)}" y1="{f2(y1)}" x2="{f2(bx)}" y2="{f2(by)}" class="{cls}"{sw}/>')
        px, py = -uy, ux
        hw = head * 0.52
        pts = [(x2, y2), (x2 - ux * head + px * hw, y2 - uy * head + py * hw),
               (x2 - ux * head * 0.72, y2 - uy * head * 0.72),
               (x2 - ux * head - px * hw, y2 - uy * head - py * hw)]
        self.add(f'<path d="M{" L".join(f"{f2(a)} {f2(b)}" for a, b in pts)}Z" class="{cls}-h"/>')

    # --- effects ---------------------------------------------------------
    def shadow(self, x, y, rx, ry=None, op=None):
        self.uses_shadow = True
        o = f' opacity="{op}"' if op else ""
        self.add(f'<ellipse cx="{f2(x)}" cy="{f2(y)}" rx="{f2(rx)}" ry="{f2(ry or rx*0.18)}" class="fshadow" filter="url(#{self.p}-blur)"{o}/>')

    def glow(self, x, y, r, warm=False):
        if warm:
            self.uses_warmglow = True
            self.add(f'<circle cx="{f2(x)}" cy="{f2(y)}" r="{f2(r)}" fill="url(#{self.p}-wglow)"/>')
        else:
            self.uses_glow = True
            self.add(f'<circle cx="{f2(x)}" cy="{f2(y)}" r="{f2(r)}" fill="url(#{self.p}-glow)"/>')

    # --- surfaces --------------------------------------------------------
    def slab(self, x, y, cols, rows, dx, dyr, sh, r, elf, depth=20, face="au", rsc=None):
        """A crystal seen slightly from above. Row 0 is the back row at y;
        each row is dyr lower and shifted sh to the side; alternate rows are
        staggered by half a spacing. elf(row, col) names each atom's element
        (None leaves a hole); rsc(el) scales an element's radius."""
        self.faces.add(face)
        yf = y + (rows - 1) * dyr
        xl_b, xr_b = x - r * 1.2, x + (cols - 1) * dx + dx / 2 + r * 1.2
        xl_f, xr_f = xl_b + (rows - 1) * sh, xr_b + (rows - 1) * sh
        self.add(f'<path d="M{f2(xl_b)} {f2(y-r*0.4)}L{f2(xr_b)} {f2(y-r*0.4)}L{f2(xr_f)} {f2(yf+r*0.5)}L{f2(xl_f)} {f2(yf+r*0.5)}Z" class="slt slt-{face}"/>')
        self.add(f'<rect x="{f2(xl_f)}" y="{f2(yf+r*0.5)}" width="{f2(xr_f-xl_f)}" height="{depth}" fill="url(#{self.p}-face-{face})"/>')
        for row in range(rows):
            for c in range(cols):
                el = elf(row, c)
                if not el:
                    continue
                rr = r * (rsc(el) if rsc else 1)
                self.ball(x + c * dx + (dx / 2 if row % 2 else 0) + row * sh, y + row * dyr, rr, el)
        return yf + r * 0.5

    # --- output ----------------------------------------------------------
    def svg(self):
        d = []
        for el in sorted(self.els):
            d.append(
                f'<radialGradient id="{self.p}-{el}" cx=".36" cy=".3" r=".72">'
                f'<stop offset="0" class="g0-{el}"/><stop offset=".5" class="g1-{el}"/>'
                f'<stop offset="1" class="g2-{el}"/></radialGradient>')
        for face in sorted(self.faces):
            d.append(
                f'<linearGradient id="{self.p}-face-{face}" x1="0" y1="0" x2="0" y2="1">'
                f'<stop offset="0" class="f0-{face}"/><stop offset="1" class="f1-{face}"/></linearGradient>')
        if self.uses_shadow:
            d.append(f'<filter id="{self.p}-blur" x="-50%" y="-200%" width="200%" height="500%"><feGaussianBlur stdDeviation="4"/></filter>')
        if self.uses_glow:
            d.append(f'<radialGradient id="{self.p}-glow"><stop offset="0" class="gl0"/><stop offset="1" class="gl1"/></radialGradient>')
        if self.uses_warmglow:
            d.append(f'<radialGradient id="{self.p}-wglow"><stop offset="0" class="wg0"/><stop offset="1" class="wg1"/></radialGradient>')
        d.extend(self.defs)
        defs = f"<defs>{''.join(d)}</defs>" if d else ""
        return (f'<svg class="{self.cls}" viewBox="0 0 {self.w} {self.h}" role="img" aria-label="{esc_attr(self.label)}">'
                + defs + "".join(self.body) + "</svg>")


def sub(base, s, after=""):
    """Text with a subscript, e.g. sub('H', '2', 'O')."""
    tail = f'<tspan dy="-3.5">{after}</tspan>' if after else ""
    return f'{base}<tspan dy="3.5" font-size="0.74em">{s}</tspan>{tail}'


def panel(F, x, y, w, h, title=None, tagtxt=None):
    F.add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" class="fpanel"/>')
    if title:
        F.text(x + 16, y + 24, title, "fhead", "start")


def gear_text(F, x, y, rows, cls="ft", lh=16):
    F.lines(x, y, rows, cls, "middle", lh)


# --------------------------------------------------------------------------
# Reusable chemical pieces
# --------------------------------------------------------------------------

def ru10(F, cx, base, r=11.5, hi=(), shape="pyramid", hl_cls="hl"):
    """A ten-atom ruthenium cluster in side view, resting on y = base."""
    d = 2 * r * 0.98
    if shape == "pyramid":
        layers = [4, 3, 2, 1]
    elif shape == "flat":
        layers = [5, 3, 2]
    else:  # rounded
        layers = [3, 4, 3]
    pos = []
    for li, n in enumerate(layers):
        for k in range(n):
            x = cx + (k - (n - 1) / 2) * d
            y = base - r - li * d * 0.84
            pos.append((x, y))
    F.shadow(cx, base + 2, len(layers) and max(layers) * r * 1.05, 5)
    for i, (x, y) in enumerate(pos):
        F.ball(x, y, r, "ru", hl_cls if i in hi else "")
    return pos


def tio2(F, x, y, cols, rows=3, dx=21, depth=22, holes=()):
    def elf(row, c):
        if (row, c) in holes:
            return None
        return "o" if (row + c) % 2 == 0 else "ti"
    return F.slab(x, y, cols, rows, dx, 7, -4, 9, elf, depth=depth, face="ti",
                  rsc=lambda e: 0.82 if e == "o" else 1.0)


def gold(F, x, y, cols, rows=3, dx=22, depth=20, r=10.5):
    return F.slab(x, y, cols, rows, dx, 7.5, -5, r, lambda a, b: "au", depth=depth, face="au")


def flame(F, x, y, s=1.0):
    F.add(f'<path d="M{f2(x)} {f2(y+12*s)}c{f2(-9*s)} 0 {f2(-12*s)} {f2(-8*s)} {f2(-7*s)} {f2(-15*s)}c{f2(2*s)} {f2(4*s)} {f2(4*s)} {f2(5*s)} {f2(5*s)} {f2(3*s)}c{f2(-2*s)} {f2(-6*s)} {f2(1*s)} {f2(-11*s)} {f2(6*s)} {f2(-14*s)}c{f2(-1*s)} {f2(6*s)} {f2(8*s)} {f2(9*s)} {f2(8*s)} {f2(16*s)}c0 {f2(6*s)} {f2(-5*s)} {f2(10*s)} {f2(-12*s)} {f2(10*s)}z" class="fflame"/>')


# --------------------------------------------------------------------------
# The figures, page by page
# --------------------------------------------------------------------------

FIGS = {}


def fig(page, n):
    def deco(fn):
        FIGS[(page, n)] = fn
        return fn
    return deco


# ---- Can parking spots help catalysts? ------------------------------------

def catalyst(F, x, y, s=1.0, cls="", dim=False):
    """A catalyst molecule: a metal centre with three ligands."""
    g = ' opacity=".45"' if dim else ""
    if g:
        F.add(f"<g{g}>")
    for k in range(3):
        a = math.radians(-90 + k * 120)
        F.stick(x, y, x + 11 * s * math.cos(a), y + 11 * s * math.sin(a), w=2.6 * s)
        F.ball(x + 11 * s * math.cos(a), y + 11 * s * math.sin(a), 4.2 * s, "c")
    F.ball(x, y, 6.8 * s, "ru", cls)
    if g:
        F.add("</g>")


@fig("can-parking-spots-help-catalysts", 1)
def _(F):
    F.label = ("Two flasks of catalyst molecules. Without a parking spot, the molecules meet, collide and clump "
               "into dead lumps. With a parking spot, some molecules rest in a parked area, so fewer collide.")
    for px, title in ((16, "NO PARKING SPOT"), (328, "WITH A PARKING SPOT")):
        panel(F, px, 16, 296, 270, title)
        F.add(f'<rect x="{px+14}" y="52" width="268" height="190" rx="10" class="fsol"/>')
    # left: collisions
    for x, y in ((80, 110), (178, 86), (250, 130), (110, 200), (230, 214)):
        catalyst(F, x, y)
    for (x1, y1, x2, y2) in ((132, 140, 154, 140), (176, 180, 198, 172)):
        pass
    # a collision in progress
    catalyst(F, 150, 150)
    catalyst(F, 178, 158)
    F.add('<path d="M164 128l3 9 8-5-4 9 9 2-9 3 4 9-8-4-3 9-3-9-8 4 4-9-9-3 9-2-4-9 8 5z" class="fburst"/>')
    # a dead clump
    F.add('<g opacity=".55">')
    for x, y in ((48 + 18, 232), (60 + 18, 222), (72 + 18, 234)):
        F.ball(x, y, 7, "c")
    F.add("</g>")
    F.text(86, 258, "dead clump", "fm")
    F.text(164, 276, "catalysts meet and clump together", "ft")
    # right: parking spot
    F.add('<rect x="508" y="66" width="88" height="162" rx="8" class="fpark"/>')
    F.add('<rect x="540" y="74" width="24" height="24" rx="5" class="fpark-sign"/>')
    F.text(552, 91, "P", "fpark-p")
    for y in (124, 162, 200):
        catalyst(F, 552, y, dim=True)
        F.text(578, y - 6, "z", "fz", "start")
    for x, y in ((392, 100), (460, 132), (404, 186), (470, 214)):
        catalyst(F, x, y)
    F.text(476, 276, "fewer free catalysts, fewer meetings", "ft")


@fig("can-parking-spots-help-catalysts", 2)
def _(F):
    F.label = ("A curve of total product made against the depth of the parking spot. It rises, peaks at a best depth, "
               "then falls when the spot is so deep that the reaction cannot finish in time. Schematic, not data.")
    x0, x1, y0, y1 = 84, 600, 262, 40
    F.defs.append(f'<linearGradient id="{F.p}-area" x1="0" y1="0" x2="0" y2="1"><stop offset="0" class="ga0"/><stop offset="1" class="ga1"/></linearGradient>')
    pts = []
    for i in range(121):
        t = i / 120
        v = (t / 0.42) ** 1.6 * math.exp(1.6 * (1 - t / 0.42)) if t > 0 else 0
        pts.append((x0 + t * (x1 - x0), y0 - 12 - v * 176))
    # sweet-spot band
    F.add(f'<rect x="{f2(x0+0.33*(x1-x0))}" y="{y1}" width="{f2(0.18*(x1-x0))}" height="{y0-y1}" class="fband"/>')
    path = "M" + " L".join(f"{f2(a)} {f2(b)}" for a, b in pts)
    F.add(f'<path d="{path} L{x1} {y0} L{x0} {y0}Z" fill="url(#{F.p}-area)"/>')
    F.add(f'<path d="{path}" class="fcurve"/>')
    F.add(f'<line x1="{x0}" y1="{y0}" x2="{x1+8}" y2="{y0}" class="faxis"/><line x1="{x0}" y1="{y0}" x2="{x0}" y2="{y1-8}" class="faxis"/>')
    F.arrow(x1, y0, x1 + 14, y0, "fax", 8)
    F.arrow(x0, y1, x0, y1 - 14, "fax", 8)
    px = x0 + 0.42 * (x1 - x0)
    py = min(p[1] for p in pts)
    F.glow(px, py, 22)
    F.add(f'<circle cx="{f2(px)}" cy="{f2(py)}" r="6.5" class="fdot"/>')
    F.text(px, py - 16, "best depth", "ftk")
    F.lines(250, 214, ["too shallow:", "catalysts still clump"], "ft", "middle")
    F.lines(536, 182, ["too deep:", "too slow to finish"], "ft", "middle")
    F.text((x0 + x1) / 2, y0 + 28, "deeper parking spot →", "fm")
    F.add(f'<text transform="translate({x0-18} {(y0+y1)/2}) rotate(-90)" class="fm">total product made →</text>')
    F.text(x1, y0 + 48, "SCHEMATIC, NOT DATA", "fm", "end")


# ---- Carbodicarbene coatings on gold ---------------------------------------

def nhc_ring(F, cx, cy, ang, s=1.0, flat=False):
    """A benzimidazole-like NHC unit drawn as a skeletal ring pair."""
    pass


def hexagon(cx, cy, r, rot=0, sy=1.0):
    return [(cx + r * math.cos(math.radians(rot + 60 * k)), cy + r * math.sin(math.radians(rot + 60 * k)) * sy) for k in range(6)]


def ring_atoms(F, pts, els=None, r=6.0, z=0):
    els = els or ["c"] * len(pts)
    atoms = [(e, x, y, r, z) for e, (x, y) in zip(els, pts)]
    bonds = [(i, (i + 1) % len(pts)) for i in range(len(pts))]
    return atoms, bonds


def cdc(F, cx, cy, tilt):
    """Carbodicarbene: a central carbon bound to two NHC wings, each a
    five-membered N-C-N ring fused to a benzene ring. Built flat in local
    coordinates, then either stood up and leaned (tilt) or laid down."""
    local, bonds = [("c", 0, 0, 1)], []

    def wing(sgn):
        # five-membered ring: carbene carbon, N, C, C, N
        c2 = (sgn * 26, -14)
        five = [c2]
        cen = (sgn * 44, -26)
        a0 = math.atan2(c2[1] - cen[1], c2[0] - cen[0])
        R5 = math.hypot(c2[0] - cen[0], c2[1] - cen[1])
        for k in range(1, 5):
            a = a0 + sgn * math.radians(72 * k)
            five.append((cen[0] + R5 * math.cos(a), cen[1] + R5 * math.sin(a)))
        b = len(local)
        for e, (x, y) in zip("cnccn", five):
            local.append((e, x, y, 0))
        for k in range(5):
            bonds.append((b + k, b + (k + 1) % 5))
        bonds.append((0, b))
        # benzene fused on the far C-C edge
        p, q = five[2], five[3]
        mx, my = (p[0] + q[0]) / 2, (p[1] + q[1]) / 2
        ox, oy = mx - cen[0], my - cen[1]
        L = math.hypot(ox, oy)
        side = math.hypot(p[0] - q[0], p[1] - q[1])
        hc = (mx + ox / L * side * 0.866, my + oy / L * side * 0.866)
        ang = math.atan2(p[1] - hc[1], p[0] - hc[0])
        prev = b + 2
        d = 1
        a5 = ang + math.radians(300)
        if math.hypot(hc[0] + side * math.cos(a5) - q[0], hc[1] + side * math.sin(a5) - q[1]) > 1:
            d = -1
        for k in range(1, 5):
            a = ang + d * math.radians(60 * k)
            local.append(("c", hc[0] + side * math.cos(a), hc[1] + side * math.sin(a), 0))
            bonds.append((prev, len(local) - 1))
            prev = len(local) - 1
        bonds.append((prev, b + 3))

    wing(-1)
    wing(1)
    atoms = []
    for e, x, y, _ in local:
        if tilt:
            # stand the molecule up (wings rise from the surface) and lean it
            X, Y = x * 0.6, -abs(x) * 0.85 + y * 0.75
            a = math.radians(-24)
            X, Y = X * math.cos(a) - Y * math.sin(a), X * math.sin(a) + Y * math.cos(a)
            z = -y
        else:
            X, Y = x * 0.95, y * 0.32 - 4
            z = y
        r = 8.5 if (x, y) == (0, 0) else (6.6 if e == "n" else 6.2)
        atoms.append((e, cx + X, cy + Y, r, z))
    F.molecule(atoms, bonds, w=3.2)
    F.glow(cx, cy, 18)
    F.ball(cx, cy, 8.5, "c", "hl")


@fig("carbodicarbene-coatings-on-gold", 1)
def _(F):
    F.label = ("A carbodicarbene molecule on a gold crystal, bound through its central carbon. "
               "At first it stands tilted; after heating it lies flat in the same spot.")
    panel(F, 16, 16, 272, 268, "AS DEPOSITED")
    panel(F, 352, 16, 272, 268, "AFTER HEATING")
    gold(F, 46, 196, 10)
    gold(F, 382, 196, 10)
    cdc(F, 150, 186, True)
    cdc(F, 488, 188, False)
    F.text(152, 268, "stands tilted", "ft")
    F.text(488, 268, "lies flat, without moving away", "ft")
    F.arrow(298, 150, 340, 150, "fark", 10, w=2.4)
    flame(F, 319, 118, 0.9)
    F.text(319, 176, "heat", "ftk")
    F.glow(196, 302, 10)
    F.ball(196, 302, 6.5, "c", "hl")
    F.text(210, 306, "central carbon, bound to gold", "fm", "start")
    for k, (el, name) in enumerate((("n", "nitrogen"), ("au", "gold"))):
        x = 420 + k * 84
        F.ball(x, 302, 6, el)
        F.text(x + 11, 306, name, "fm", "start")


@fig("carbodicarbene-coatings-on-gold", 2)
def _(F):
    F.label = ("Energy needed to pull an electron out of gold, drawn as a climb from the electrons in the metal to "
               "the vacuum level: 4.98 eV for bare gold, up to 1 eV less for coated gold.")
    yv, scale = 56, 40          # vacuum level, px per eV
    yf_bare = yv + 4.98 * scale
    yf_coat = yv + 3.98 * scale
    F.add(f'<line x1="40" y1="{yv}" x2="600" y2="{yv}" class="fvac"/>')
    F.text(600, yv - 10, "VACUUM: ELECTRON IS FREE", "fm", "end")
    for (x, yfl, title, coated) in ((86, yf_bare, "bare gold", False), (356, yf_coat, "coated gold", True)):
        w = 200
        # the metal: electrons fill it up to the Fermi level
        F.add(f'<rect x="{x}" y="{f2(yfl)}" width="{w}" height="{f2(300-yfl)}" class="fsea"/>')
        F.add(f'<line x1="{x}" y1="{f2(yfl)}" x2="{x+w}" y2="{f2(yfl)}" class="ffermi"/>')
        for k in range(9):
            F.add(f'<circle cx="{x+16+k*21}" cy="{f2(yfl+12)}" r="4.2" class="fel"/>')
        if coated:
            for k in range(9):
                xx = x + 16 + k * 21
                F.add(f'<line x1="{xx}" y1="{f2(yfl-4)}" x2="{xx}" y2="{f2(yfl-17)}" class="fcoat"/>')
                F.add(f'<circle cx="{xx}" cy="{f2(yfl-20)}" r="3.6" class="fcoat-h"/>')
        # the climb
        ax = x + w / 2
        top = yv + 4
        bot = yfl - (24 if coated else 6)
        F.arrow(ax, bot, ax, top, "fark" if coated else "far", 10, w=2.4)
        lbl = "3.98 eV" if coated else "4.98 eV"
        F.tag(ax + 48, (top + bot) / 2, lbl, "ftag" if coated else "ftagn")
        F.text(ax, 300 + 22, title, "ftb")
    # the difference
    F.add(f'<line x1="300" y1="{f2(yf_bare)}" x2="356" y2="{f2(yf_bare)}" class="fguide"/>')
    F.add(f'<path d="M330 {f2(yf_coat)}v{f2(yf_bare-yf_coat)}" class="fbrace"/>')
    F.text(324, (yf_coat + yf_bare) / 2 + 4, "up to 1 eV", "ftk", "end")
    F.text(324, (yf_coat + yf_bare) / 2 + 20, "easier", "ft", "end")


# ---- Fluorine count on gold coatings ----------------------------------------

@fig("fluorine-count-on-gold-coatings", 1)
def _(F):
    F.label = ("Five coatings seen from above, each a flat-lying ring molecule on gold carrying one to five fluorine "
               "atoms, all anchored through a carbon atom to a gold atom raised out of the surface.")
    # gold seen from above: a close-packed sheet
    F.add('<rect x="16" y="16" width="608" height="252" rx="12" class="fpanel"/>')
    F.add('<clipPath id="%s-clip"><rect x="16" y="16" width="608" height="252" rx="12"/></clipPath>' % F.p)
    F.add(f'<g clip-path="url(#{F.p}-clip)" class="fgold-top">')
    for row in range(14):
        for c in range(30):
            x = 10 + c * 22 + (11 if row % 2 else 0)
            y = 22 + row * 19
            F.ball(x, y, 10.6, "au")
    F.add("</g>")
    F.add('<rect x="16" y="16" width="608" height="252" rx="12" class="fveil"/>')
    for k in range(5):
        cx, cy = 76 + k * 122, 140
        n = k + 1
        # anchor: gold adatom under the carbene carbon
        F.glow(cx, cy + 34, 18)
        F.ball(cx, cy + 34, 9.5, "au", "hl")
        # NHC ring (five-membered) and a fluorinated benzene wing
        five = [(cx + 13 * math.cos(math.radians(90 + 72 * i)), cy + 16 + 13 * math.sin(math.radians(90 + 72 * i))) for i in range(5)]
        six = hexagon(cx, cy - 34, 16, 30)
        atoms = [("c", *five[0], 6.2, 3)]
        atoms += [("n", *five[1], 6.4, 2), ("c", *five[2], 5.8, 2), ("c", *five[3], 5.8, 2), ("n", *five[4], 6.4, 2)]
        bonds = [(0, 1), (1, 2), (2, 3), (3, 4), (4, 0)]
        # benzyl-type link from one N up to the ring
        base = len(atoms)
        atoms.append(("c", cx + 2, cy - 8, 5.4, 2))
        bonds.append((4, base))
        b6 = len(atoms)
        for (x, y) in six:
            atoms.append(("c", x, y, 5.8, 2))
        for i in range(6):
            bonds.append((b6 + i, b6 + (i + 1) % 6))
        bonds.append((base, b6 + 1))
        # fluorines on the ring, outward
        spots = [2, 3, 4, 5, 0]
        for i in spots[:n]:
            x, y = six[i]
            vx, vy = x - cx, y - (cy - 34)
            L = math.hypot(vx, vy)
            fx, fy = x + vx / L * 13, y + vy / L * 13
            fi = len(atoms)
            atoms.append(("f", fx, fy, 6.4, 4))
            bonds.append((b6 + i, fi))
        F.stick(cx, cy + 34, *five[0], w=3)
        F.molecule(atoms, bonds, w=3)
        F.tag(cx, 246, f"{n} F", "ftag")
    F.text(620, 290, "Au atom pulled out of the surface: the anchor", "fm", "end")
    F.add('<circle cx="296" cy="286" r="5" class="fkey-au"/>')


def droplet(F, cx, base, R, theta_deg, cls_id):
    """A water droplet as a circular cap meeting the surface at theta."""
    th = math.radians(theta_deg)
    half = R * math.sin(th)
    h = R * (1 - math.cos(th))
    yc = base - h + R
    large = 1 if theta_deg > 90 else 0
    d = f"M{f2(cx-half)} {base}A{f2(R)} {f2(R)} 0 {large} 1 {f2(cx+half)} {base}Z"
    F.add(f'<path d="{d}" fill="url(#{F.p}-drop)" class="fdrop"/>')
    # highlight
    F.add(f'<ellipse cx="{f2(cx-half*0.35)}" cy="{f2(base-h*0.62)}" rx="{f2(half*0.16)}" ry="{f2(h*0.14)}" class="fdrop-hi" transform="rotate(-30 {f2(cx-half*0.35)} {f2(base-h*0.62)})"/>')
    # contact angle at the right foot
    x0 = cx + half
    tx, ty = -math.cos(th), -math.sin(th)    # tangent pointing into the drop, up
    F.add(f'<line x1="{f2(x0)}" y1="{base}" x2="{f2(x0+tx*52)}" y2="{f2(base+ty*52)}" class="ftan"/>')
    rr = 30
    F.add(f'<path d="M{f2(x0-rr)} {base}A{rr} {rr} 0 0 1 {f2(x0+tx*rr)} {f2(base+ty*rr)}" class="fang"/>')
    return x0, half, h


@fig("fluorine-count-on-gold-coatings", 2)
def _(F):
    F.label = ("Two water droplets. On bare gold the droplet spreads more; on coated gold it beads up, "
               "with a contact angle 15 to 20 degrees larger.")
    F.defs.append(f'<linearGradient id="{F.p}-drop" x1="0" y1="0" x2="0" y2="1"><stop offset="0" class="gd0"/><stop offset="1" class="gd1"/></linearGradient>')
    for (x0, title, theta, coated) in ((26, "BARE GOLD", 72, False), (334, "COATED GOLD", 90, True)):
        panel(F, x0 - 10, 16, 290, 268, title)
        base = 214
        gold(F, x0 + 18, base + 4, 11, rows=2, dx=21.5, r=10)
        if coated:
            for k in range(22):
                xx = x0 + 16 + k * 11
                F.add(f'<line x1="{xx}" y1="{base+1}" x2="{xx+4}" y2="{base-5}" class="fcoat2"/>')
                F.add(f'<circle cx="{xx+5}" cy="{base-6}" r="2.6" class="fcoat2-f"/>')
        R = 74 if not coated else 64
        x_foot, half, h = droplet(F, x0 + 128, base - (6 if coated else 0), R, theta, "")
        lab = "about 70°" if not coated else "about 85–90°"
        F.text(x_foot + 18, base - 36 - (6 if coated else 0), "θ", "ftb", "start")
        F.text(x0 + 135, 270, "water spreads more" if not coated else "water beads up more", "ft")
    F.tag(479, 58, "+15–20° contact angle", "ftag")
    F.text(620, 300, "ANGLES DRAWN SCHEMATICALLY", "fm", "end")


# ---- Forever-chemical fragment on ice ---------------------------------------

def cf3(F, atoms, bonds, ci, x, y, dirs, z=1):
    i = len(atoms)
    atoms.append(("c", x, y, 8, z))
    bonds.append((ci, i))
    for k, (dx, dy, dz) in enumerate(dirs):
        atoms.append(("f", x + dx, y + dy, 7.4 if dz >= 0 else 6.4, z + dz))
        bonds.append((i, len(atoms) - 1))


def hfa(F, cx, cy, s=1.0, diol=False):
    atoms, bonds = [("c", cx, cy, 9 * s, 2)], []
    if diol:
        for sgn in (-1, 1):
            ox, oy = cx + sgn * 20 * s, cy - 26 * s
            atoms.append(("o", ox, oy, 9 * s, 3))
            bonds.append((0, len(atoms) - 1))
            atoms.append(("h", ox + sgn * 12 * s, oy - 10 * s, 5.5 * s, 3))
            bonds.append((len(atoms) - 2, len(atoms) - 1))
    else:
        atoms.append(("o", cx, cy - 30 * s, 9.5 * s, 3))
        bonds.append((0, 1, 2))
    cf3(F, atoms, bonds, 0, cx - 27 * s, cy + 18 * s,
        [(-18 * s, -6 * s, 1), (-6 * s, 18 * s, 1), (-14 * s, 12 * s, -1)])
    cf3(F, atoms, bonds, 0, cx + 27 * s, cy + 18 * s,
        [(18 * s, -6 * s, 1), (6 * s, 18 * s, 1), (14 * s, 12 * s, -1)])
    F.molecule(atoms, bonds, w=3.6 * s)


@fig("forever-chemical-fragment-on-ice", 1)
def _(F):
    F.label = ("Hexafluoroacetone (HFA) plus water gives the diol, in which water has added across the carbon–oxygen "
               "double bond. On ice this is favoured by at least 29 kJ/mol.")
    hfa(F, 100, 134)
    F.text(100, 236, "HFA", "ftb")
    F.text(100, 254, "C=O double bond", "fm")
    F.text(182, 140, "+", "fplus")
    F.water(232, 136, 1.4, -90)
    F.text(232, 236, sub("H", "2", "O"), "ftb")
    F.text(232, 254, "water", "fm")
    F.arrow(284, 132, 400, 132, "fark", 12, w=2.6)
    # snowflake
    sx, sy = 342, 96
    for k in range(3):
        a = math.radians(k * 60)
        F.add(f'<line x1="{f2(sx-12*math.cos(a))}" y1="{f2(sy-12*math.sin(a))}" x2="{f2(sx+12*math.cos(a))}" y2="{f2(sy+12*math.sin(a))}" class="fsnow"/>')
    F.text(342, 160, "on ice", "ftk")
    F.text(342, 177, "≥ 29 kJ/mol downhill", "fm")
    hfa(F, 512, 140, diol=True)
    F.glow(512, 140, 34)
    hfa(F, 512, 140, diol=True)
    F.text(512, 236, "the diol", "ftb")
    F.text(512, 254, "two OH groups on one carbon", "fm")
    # legend
    for k, (el, name) in enumerate((("c", "carbon"), ("o", "oxygen"), ("f", "fluorine"), ("h", "hydrogen"))):
        x = 182 + k * 84
        F.ball(x, 294, 6, el)
        F.text(x + 11, 298, name, "fm", "start")


@fig("forever-chemical-fragment-on-ice", 2)
def _(F):
    F.label = ("Cross-section of the experiment: a thin film of ice on a platinum crystal in a vacuum chamber. "
               "HFA molecules arrive from above, sink into the ice and react to become the diol.")
    panel(F, 16, 16, 608, 288)
    if not F.mobile:
        F.text(608, 294, "INSIDE A VACUUM CHAMBER", "fhead", "end")
    # platinum crystal
    base = F.slab(84, 228, 18, 3, 23, 8, -6, 10.5, lambda a, b: "pt", depth=30, face="pt")
    F.text(300, base + 21, "platinum crystal", "fonslab")
    # ice film: a block of water molecules
    F.add('<path d="M70 104L520 104L506 214L56 214Z" class="fice"/>')
    import random
    rnd = random.Random(4)
    for row in range(4):
        for c in range(15):
            x = 92 + c * 28 + (14 if row % 2 else 0) - row * 3
            y = 124 + row * 26
            if (row, c) in ((1, 9), (2, 9), (2, 10)):
                continue
            F.water(x, y, 0.75, -90 + rnd.uniform(-50, 50))
    F.text(560, 152, "ice film", "ftb", "start")
    F.text(560, 170, "a few nm", "fm", "start")
    # arriving HFA
    hfa(F, 190, 66, 0.42)
    F.arrow(190, 84, 190, 100, "far", 7)
    F.add('<line x1="190" y1="40" x2="190" y2="52" class="ftrail"/>')
    hfa(F, 330, 62, 0.42)
    F.add('<line x1="330" y1="36" x2="330" y2="48" class="ftrail"/>')
    F.text(260, 62, "HFA arrives", "ft")
    # sunk-in and converted
    F.glow(372, 164, 30)
    hfa(F, 372, 166, 0.5, diol=True)
    if F.mobile:
        return
    F.arrow(456, 72, 392, 140, "fark", 9, ctrl=(452, 128))
    F.lines(462, 64, ["sinks in and", "becomes the diol"], "ftk", "start")


# ---- Graphite support for a CO2 catalyst ------------------------------------

def graphene(F, x0, y0, cols, rows, a=13, sy=0.5):
    """A graphene sheet in perspective: a honeycomb squashed vertically."""
    segs = []
    pts = []
    for r in range(rows):
        for c in range(cols):
            cx = x0 + c * a * 1.732 + (a * 0.866 if r % 2 else 0) - r * 4
            cy = y0 + r * a * 1.5 * sy
            hx = hexagon(cx, cy, a, 30, sy)
            d = "M" + " L".join(f"{f2(x)} {f2(y)}" for x, y in hx) + "Z"
            segs.append(d)
    F.add(f'<path d="{"".join(segs)}" class="fgraph"/>')


@fig("graphite-support-co2-catalyst", 1)
def _(F):
    F.label = ("A nickel–iron complex sitting on a sheet of graphene. Electrons flow back and forth between the sheet "
               "and the complex, and a CO2 molecule binds to the complex.")
    F.defs.append(f'<linearGradient id="{F.p}-sheet" x1="0" y1="0" x2="0" y2="1"><stop offset="0" class="gs0"/><stop offset="1" class="gs1"/></linearGradient>')
    F.add(f'<path d="M64 190L584 190L548 274L28 274Z" fill="url(#{F.p}-sheet)"/>')
    graphene(F, 76, 196, 21, 9, a=12.5, sy=0.48)
    F.text(306, 300, "graphene: a one-atom-thick sheet of carbon", "ft")
    # the complex
    F.shadow(250, 218, 70, 9)
    cx = 250
    lig = [("c", 200, 150), ("n", 214, 112), ("c", 236, 86), ("n", 264, 86), ("c", 290, 106), ("c", 300, 148),
           ("c", 196, 182), ("c", 300, 182), ("c", 248, 192)]
    atoms = [("ni", 228, 140, 15, 4), ("fe", 272, 140, 15, 4)]
    for e, x, y in lig:
        atoms.append((e, x, y, 6.5, 2))
    bonds = [(0, 1), (0, 2), (0, 3), (1, 6), (1, 7), (2, 3), (3, 4), (4, 5), (5, 6), (7, 6), (0, 8), (1, 9), (8, 10), (9, 10), (2, 8), (7, 9)]
    F.molecule(atoms, bonds, w=3.2)
    F.text(228, 144, "Ni", "fel-lbl")
    F.text(272, 144, "Fe", "fel-lbl")
    # electrons hopping
    for (x, up) in ((176, True), (330, False)):
        if up:
            F.arrow(x, 214, x, 156, "fark", 10, w=2.2)
        else:
            F.arrow(x, 156, x, 214, "fark", 10, w=2.2)
        F.glow(x + (10 if up else -10), 186, 11)
        F.add(f'<circle cx="{x + (10 if up else -10)}" cy="186" r="5.5" class="fe-"/>')
    F.text(176 - 14, 186, "e⁻", "ftk", "end")
    if not F.mobile:
        F.text(344, 186, "electrons flow both ways", "ftk", "start")
    # CO2
    F.molecule([("o", 412, 104, 10, 2), ("c", 438, 104, 9, 3), ("o", 464, 104, 10, 2)], [(0, 1, 2), (1, 2, 2)], w=3.2)
    F.text(438, 76, sub("CO", "2"), "ftb")
    if not F.mobile:
        F.arrow(396, 110, 318, 128, "far", 10, ctrl=(352, 108))
        F.text(520, 108, "binds more easily", "ft", "start")


@fig("graphite-support-co2-catalyst", 2)
def _(F):
    F.label = ("Energy diagrams for putting CO2 into the complex, with and without the graphite support. "
               "The climb is smaller on graphite. Schematic, not to scale.")
    yb = 236
    F.add(f'<line x1="56" y1="{yb+30}" x2="600" y2="{yb+30}" class="fgrid"/>')
    for (x, top, title, key) in ((60, 70, "complex alone", False), (330, 136, "on graphite", True)):
        F.add(f'<line x1="{x}" y1="{yb}" x2="{x+60}" y2="{yb}" class="flevel"/>')
        F.add(f'<line x1="{x+100}" y1="{top}" x2="{x+160}" y2="{top}" class="flevel{" flevel--k" if key else ""}"/>')
        F.add(f'<line x1="{x+60}" y1="{yb}" x2="{x+100}" y2="{top}" class="fconn"/>')
        F.arrow(x + 180, yb, x + 180, top + 4, "fark" if key else "far", 10, w=2.2)
        F.add(f'<line x1="{x+164}" y1="{yb}" x2="{x+196}" y2="{yb}" class="fguide"/>')
        F.text(x + 30, yb + 20, "start", "fm")
        F.text(x + 130, top - 12, sub("CO", "2", " inserted"), "fm")
        F.text(x + 90, yb + 54, title, "ftb")
        F.tag(x + 214, (top + yb) / 2, "cost", "ftag" if key else "ftagn")
    F.add('<line x1="220" y1="70" x2="500" y2="70" class="fguide"/>')
    F.add('<path d="M418 76V130" class="fbrace"/>')
    F.text(408, 98, "saved", "ftk", "end")
    F.text(408, 114, "on graphite", "ft", "end")
    F.text(620, 304, "SCHEMATIC, NOT TO SCALE", "fm", "end")


# ---- How tightly molecules stick --------------------------------------------

@fig("how-tightly-molecules-stick", 1)
def _(F):
    F.label = ("Binding strength in kJ/mol, drawn to scale from zero. The shortcut gives 26. The full simulation gives 64: "
               "the same 26, plus 2 from irregular jiggling, plus 36 from sliding, spinning and rocking.")
    x0, s = 150, 6.6
    rows = (("Shortcut", 66, [(26, "fbar")]),
            ("Full simulation", 168, [(26, "fbar"), (2, "fbar2"), (36, "fbark")]))
    for name, y, segs in rows:
        F.text(x0 - 14, y + 5, name, "ftb", "end")
        x = x0
        for k, (v, cls) in enumerate(segs):
            w = v * s - (2 if k < len(segs) - 1 else 0)
            rx = 4
            F.add(f'<rect x="{f2(x)}" y="{y-20}" width="{f2(w)}" height="40" rx="{rx}" class="{cls}"/>')
            x += v * s
        tot = sum(v for v, _ in segs)
        F.text(x + 10, y + 5, f"−{tot}", "fvalue", "start")
    # annotations
    F.add(f'<line x1="{f2(x0+27*s)}" y1="146" x2="{f2(x0+27*s)}" y2="124" class="flead"/>')
    F.text(x0 + 27 * s - 6, 120, "irregular jiggling: 2", "ft", "end")
    F.text(x0 + (28 + 18) * s, 173, "sliding, spinning, rocking: 36", "fonbar")
    F.add(f'<path d="M{f2(x0+26*s)} 202v8h{f2(38*s)}v-8" class="fbrace2"/>')
    F.text(x0 + 45 * s, 230, "what the shortcut misses: 38", "ftk")
    # axis
    for v in range(0, 71, 10):
        xx = x0 + v * s
        F.add(f'<line x1="{f2(xx)}" y1="256" x2="{f2(xx)}" y2="262" class="ftick"/>')
        F.text(xx, 278, f"{'−' if v else ''}{v}", "fm")
    F.add(f'<line x1="{x0}" y1="256" x2="{f2(x0+70*s)}" y2="256" class="faxis"/>')
    F.text(x0 + 35 * s, 300, "BINDING STRENGTH, kJ/mol (LONGER = STICKIER)", "fm")


@fig("how-tightly-molecules-stick", 2)
def _(F):
    F.label = ("Left: the shortcut pictures the stuck molecule as a ball held at the bottom of a bowl. "
               "Right: in reality it is like a puck on an air-hockey table, free to slide, spin and rock.")
    F.defs.append(f'<linearGradient id="{F.p}-bowl" x1="0" y1="0" x2="0" y2="1"><stop offset="0" class="gb0"/><stop offset="1" class="gb1"/></linearGradient>')
    panel(F, 16, 16, 290, 278, "WHAT THE SHORTCUT ASSUMES")
    panel(F, 334, 16, 290, 278, "WHAT REALLY HAPPENS")
    # bowl
    F.add(f'<path d="M56 96C66 250 256 250 266 96Z" fill="url(#{F.p}-bowl)" class="fbowl"/>')
    F.add('<ellipse cx="161" cy="96" rx="105" ry="16" class="fbowl-rim"/>')
    F.shadow(161, 208, 30, 5)
    rhenium_puck(F, 161, 186, 1.0)
    F.add('<path d="M140 222q21 8 42 0" class="fjig"/>')
    F.text(161, 262, "a ball held in a bowl:", "ft")
    F.text(161, 279, "it can only jiggle", "ft")
    # air-hockey table
    F.add('<path d="M372 210L600 210L572 146L400 146Z" class="ftable"/>')
    for k in range(1, 8):
        x = 400 + k * 21.5
        F.add(f'<line x1="{f2(x)}" y1="146" x2="{f2(x-28+k*4)}" y2="210" class="ftable-g"/>')
    for k in range(1, 4):
        y = 146 + k * 16
        F.add(f'<line x1="{f2(400-k*7)}" y1="{y}" x2="{f2(572+k*7)}" y2="{y}" class="ftable-g"/>')
    F.shadow(486, 184, 30, 5)
    rhenium_puck(F, 486, 160, 1.0)
    F.arrow(440, 190, 404, 190, "fark", 9, w=2.2)
    F.arrow(532, 190, 568, 190, "fark", 9, w=2.2)
    F.text(486, 232, "slide", "ftk")
    F.arrow(458, 118, 512, 118, "fark", 9, ctrl=(486, 98), w=2.2)
    F.text(486, 92, "spin", "ftk")
    F.arrow(546, 150, 552, 112, "fark", 8, ctrl=(560, 130), w=2.2)
    F.text(560, 104, "rock", "ftk", "start")
    F.text(479, 262, "a puck on an air-hockey table:", "ft")
    F.text(479, 279, "free to move around", "ft")


def rhenium_puck(F, x, y, s):
    """A small complex: a rhenium centre with a ring of ligands."""
    atoms = [("re", x, y, 11 * s, 3)]
    bonds = []
    for k in range(5):
        a = math.radians(-90 + k * 72)
        atoms.append(("c" if k % 2 else "n", x + 20 * s * math.cos(a), y + 13 * s * math.sin(a), 5.8 * s, 2 + math.sin(a)))
        bonds.append((0, k + 1))
    for k in range(5):
        bonds.append((k + 1, (k + 1) % 5 + 1))
    F.molecule(atoms, bonds, w=2.8 * s)


# ---- Light-driven crowded ethers -------------------------------------------

def bulky(F, x, y, s=1.0, radical=True):
    """A bulky group: a carbon carrying three methyl-like branches."""
    atoms = [("c", x, y, 9 * s, 3)]
    bonds = []
    for k, (dx, dy, z) in enumerate(((-20, -14, 2), (20, -14, 2), (0, 22, 4))):
        atoms.append(("c", x + dx * s, y + dy * s, 8.5 * s, z))
        bonds.append((0, k + 1))
        for j in range(3):
            a = math.atan2(dy, dx) + math.radians((j - 1) * 55)
            atoms.append(("h", x + dx * s + 12 * s * math.cos(a), y + dy * s + 12 * s * math.sin(a), 4.8 * s, z + (1 if j == 1 else -1)))
            bonds.append((k * 4 + 1, len(atoms) - 1))
    F.molecule(atoms, bonds, w=2.8 * s)
    if radical:
        F.add(f'<circle cx="{f2(x+18*s)}" cy="{f2(y+8*s)}" r="3.4" class="frad"/>')


def diketone(F, x, y, s=1.0, bonded_o=False):
    atoms = [("c", x - 14 * s, y, 8.5 * s, 2), ("c", x + 14 * s, y, 8.5 * s, 2),
             ("o", x - 22 * s, y - 26 * s, 9 * s, 3), ("o", x + 22 * s, y - 26 * s, 9 * s, 3),
             ("c", x - 40 * s, y + 12 * s, 8 * s, 1), ("c", x + 40 * s, y + 12 * s, 8 * s, 1)]
    bonds = [(0, 1), (0, 2, 2), (1, 3, 1 if bonded_o else 2), (0, 4), (1, 5)]
    F.molecule(atoms, bonds, w=3.2 * s)
    return atoms


@fig("light-driven-crowded-ethers", 1)
def _(F):
    F.label = ("A bulky radical and a two-carbonyl molecule combine under blue light. The bulky group ends up on one "
               "of the oxygen atoms, forming a crowded ether with a new carbon–oxygen bond.")
    F.defs.append(f'<linearGradient id="{F.p}-beam" x1="0" y1="0" x2="0" y2="1"><stop offset="0" class="gbeam0"/><stop offset="1" class="gbeam1"/></linearGradient>')
    # light from above
    if not F.mobile:
        F.add(f'<path d="M284 36L360 36L392 132L252 132Z" fill="url(#{F.p}-beam)"/>')
        F.add('<rect x="276" y="22" width="92" height="14" rx="4" class="fled"/>')
        F.text(322, 56, "blue light", "ftk")
    bulky(F, 70, 132)
    F.text(70, 214, "bulky group", "ftb")
    F.text(70, 231, "(a radical)", "fm")
    F.text(128, 136, "+", "fplus")
    diketone(F, 200, 146)
    F.text(200, 214, "two-carbonyl molecule", "ftb")
    if not F.mobile:
        F.arrow(266, 148, 372, 148, "fark", 12, w=2.6)
    a = diketone(F, 450, 166)
    ox, oy = a[3][1], a[3][2]
    bx, by = ox + 32, oy - 34
    F.glow((ox + bx) / 2, (oy + by) / 2, 20)
    F.stick(ox, oy, bx, by, w=3.6, cls="stk-new")
    bulky(F, bx + 8, by - 8, 0.85, radical=False)
    F.ball(ox, oy, 9, "o")
    F.text(450, 214, "crowded ether", "ftb")
    F.text(540, 156, "new C–O bond", "ftk", "start")
    F.add(f'<line x1="536" y1="152" x2="{f2((ox+bx)/2+6)}" y2="{f2((oy+by)/2+2)}" class="flead"/>')
    for k, (el, name) in enumerate((("c", "carbon"), ("o", "oxygen"), ("h", "hydrogen"))):
        x = 216 + k * 84
        F.ball(x, 286, 6, el)
        F.text(x + 11, 290, name, "fm", "start")


@fig("light-driven-crowded-ethers", 2)
def _(F):
    F.label = ("Batch versus flow. In a flask, light reaches only the outer layer of the mixture. In a flow reactor "
               "the mixture runs through a thin, transparent coil, so light reaches all of it.")
    F.defs.append(f'<radialGradient id="{F.p}-liq" cx=".05" cy=".5" r="1"><stop offset="0" class="gq0"/><stop offset=".35" class="gq1"/><stop offset="1" class="gq2"/></radialGradient>')
    F.defs.append(f'<linearGradient id="{F.p}-beam" x1="0" y1="0" x2="1" y2="0"><stop offset="0" class="gbeam0"/><stop offset="1" class="gbeam1"/></linearGradient>')
    F.defs.append(f'<linearGradient id="{F.p}-beamv" x1="0" y1="0" x2="0" y2="1"><stop offset="0" class="gbeam0"/><stop offset="1" class="gbeam1"/></linearGradient>')
    panel(F, 16, 16, 290, 278, "BATCH: A FLASK")
    panel(F, 334, 16, 290, 278, "FLOW: A THIN COIL")
    # flask lit from the left
    F.add('<rect x="34" y="120" width="12" height="80" rx="3" class="fled"/>')
    F.add(f'<path d="M46 124L110 136L110 200L46 196Z" fill="url(#{F.p}-beam)"/>')
    F.add(f'<path d="M140 64h26v56l46 82c5 10-2 20-13 20H108c-11 0-18-10-13-20l45-82z" class="fglass"/>')
    F.add(f'<path d="M124 150h60l29 52c5 10-2 20-13 20H108c-11 0-18-10-13-20z" fill="url(#{F.p}-liq)"/>')
    F.add(f'<path d="M140 64h26v56l46 82c5 10-2 20-13 20H108c-11 0-18-10-13-20l45-82z" class="fglass-o"/>')
    F.add('<rect x="134" y="58" width="38" height="8" rx="2" class="fglass-o"/>')
    F.text(178, 204, "dark core", "fm-on")
    F.text(161, 262, "light only reaches the edge", "ft")
    # coil lit from above
    F.add('<rect x="410" y="48" width="140" height="12" rx="4" class="fled"/>')
    F.add(f'<path d="M410 60L550 60L566 176L394 176Z" fill="url(#{F.p}-beamv)"/>')
    coil = "M362 196H392" + "".join(f"C{392+k*34} 120 {392+k*34+34} 120 {392+k*34+34} 196" for k in range(5)) + "H604"
    F.add(f'<path d="{coil}" class="ftube-o"/><path d="{coil}" class="ftube"/><path d="{coil}" class="ftube-flow"/>')
    F.text(370, 216, "in", "fm")
    F.text(596, 216, "out", "fm")
    F.text(479, 262, "light reaches all of it", "ft")


# ---- Missing oxygen atoms reshape clusters -----------------------------------

@fig("missing-oxygen-atoms-reshape-clusters", 1)
def _(F):
    F.label = ("Two ten-atom ruthenium clusters on titanium dioxide. On a perfect surface the cluster sits flat and wide. "
               "Where an oxygen atom is missing beneath it, the cluster sits up in a more rounded shape.")
    panel(F, 16, 16, 296, 268, "PERFECT OXIDE")
    panel(F, 328, 16, 296, 268, "ONE OXYGEN MISSING")
    tio2(F, 40, 196, 12)
    ru10(F, 162, 200, r=11.5, shape="flat")
    F.text(164, 276, "sits flat and wide", "ft")
    tio2(F, 352, 196, 12, holes={(2, 5)})
    # mark the vacancy
    vx, vy = 352 + 5 * 21 + 2 * -4, 196 + 14
    F.add(f'<circle cx="{f2(vx)}" cy="{f2(vy)}" r="8" class="fvac-site"/>')
    ru10(F, 466, 200, r=11.5, shape="round")
    F.add(f'<line x1="{f2(vx+6)}" y1="{f2(vy+8)}" x2="{f2(vx+40)}" y2="246" class="flead"/>')
    F.text(vx + 44, 250, "missing oxygen", "ftk", "start")
    F.text(476, 276, "sits up, more rounded", "ft")
    for k, (el, name) in enumerate((("ru", "ruthenium"), ("ti", "titanium"), ("o", "oxygen"))):
        x = 196 + k * 96
        F.ball(x, 304, 6, el)
        F.text(x + 11, 308, name, "fm", "start")


@fig("missing-oxygen-atoms-reshape-clusters", 2)
def _(F):
    F.label = ("Two cluster shapes. The most stable one is compact and tightly packed. A slightly less stable one has "
               "atoms sticking out with few neighbours, which may make it more reactive.")
    panel(F, 16, 16, 296, 288, "MOST STABLE")
    panel(F, 328, 16, 296, 288, "LESS STABLE, MORE EXPOSED")
    tio2(F, 50, 176, 11, rows=2)
    ru10(F, 164, 180, shape="round")
    tio2(F, 362, 176, 11, rows=2)
    ru10(F, 470, 180, shape="pyramid")
    # two atoms poking out with few neighbours
    for (x, y) in ((470, 84), (526, 132)):
        F.glow(x, y, 24, warm=True)
        F.ball(x, y, 11.5, "ru", "hlw")
    F.text(164, 234, "tightly packed", "ft")
    F.text(476, 234, "atoms with few neighbours", "ftw")
    for (x, stab, react) in ((52, 4, 1), (364, 3, 3)):
        for j, (name, val, on) in enumerate((("stability", stab, "fpip-on"), ("exposed atoms", react, "fpip-w"))):
            y = 262 + j * 20
            F.text(x, y + 4, name, "fm", "start")
            for k in range(4):
                F.add(f'<rect x="{x+120+k*16}" y="{y-5}" width="12" height="10" rx="2" class="{on if k < val else "fpip"}"/>')


# ---- Perrhenate, acid and deoxydehydration ------------------------------------

@fig("perrhenate-acid-deoxydehydration", 1)
def _(F):
    F.label = ("Deoxydehydration: a diol, a carbon chain with OH groups on two neighbouring carbons, loses both as water "
               "and becomes an olefin with a carbon–carbon double bond. The catalyst is perrhenate, a rhenium–oxygen ion.")
    # diol
    cs = [(46, 172), (88, 148), (130, 172), (172, 148)]
    atoms = [("c", x, y, 9, 2) for x, y in cs]
    atoms += [("o", 88, 106, 9.5, 3), ("h", 104, 90, 5.5, 3), ("o", 130, 214, 9.5, 3), ("h", 146, 230, 5.5, 3)]
    bonds = [(0, 1), (1, 2), (2, 3), (1, 4), (4, 5), (2, 6), (6, 7)]
    F.glow(88, 106, 20, warm=True)
    F.glow(130, 214, 20, warm=True)
    F.molecule(atoms, bonds, w=3.6)
    F.text(108, 262, "a diol", "ftb")
    F.text(108, 279, "OH on neighbouring carbons", "fm")
    # catalyst
    if not F.mobile:
        F.arrow(208, 160, 362, 160, "fark", 12, w=2.6)
    rx, ry = 285, 104
    re_atoms = [("re", rx, ry, 13, 3), ("o", rx, ry - 30, 9, 1), ("o", rx - 28, ry + 12, 9, 4),
                ("o", rx + 28, ry + 12, 9, 4), ("o", rx + 6, ry + 18, 8, 0)]
    F.molecule(re_atoms, [(0, 1, 2), (0, 2, 2), (0, 3, 2), (0, 4)], w=3.4)
    F.text(285, 190, "perrhenate", "ftk")
    F.text(285, 207, "+ a little acid", "fm")
    # olefin
    cs2 = [(394, 172), (436, 148), (478, 172), (520, 148)]
    atoms2 = [("c", x, y, 9, 2) for x, y in cs2]
    F.molecule(atoms2, [(0, 1), (1, 2, 2), (2, 3)], w=3.6)
    F.glow(457, 160, 22)
    F.molecule(atoms2, [(0, 1), (1, 2, 2), (2, 3)], w=3.6)
    F.text(456, 262, "an olefin", "ftb")
    F.text(456, 279, "C=C double bond", "fm")
    F.text(566, 112, "+", "fplus")
    F.water(596, 114, 1.2)
    F.text(596, 150, sub("H", "2", "O"), "ftb")


@fig("perrhenate-acid-deoxydehydration", 2)
def _(F):
    F.label = ("Energy along the reaction for two routes. Without acid the hill is tall. With a proton from the acid, "
               "the hill is much lower, which makes the reaction about a hundred million times faster in the model.")
    x0, x1, yb = 70, 600, 236
    F.defs.append(f'<linearGradient id="{F.p}-area" x1="0" y1="0" x2="0" y2="1"><stop offset="0" class="ga0"/><stop offset="1" class="ga1"/></linearGradient>')

    def curve(h, end=14):
        pts = []
        for i in range(101):
            t = i / 100
            y = yb - h * math.exp(-((t - 0.5) / 0.17) ** 2) + end * t
            pts.append((x0 + 30 + t * (x1 - x0 - 60), y))
        return "M" + " L".join(f"{f2(a)} {f2(b)}" for a, b in pts)
    hi, lo = curve(150), curve(84)
    F.add(f'<path d="{lo} L{x1-30} {yb+40} L{x0+30} {yb+40}Z" fill="url(#{F.p}-area)"/>')
    F.add(f'<path d="{hi}" class="fcurve-alt"/>')
    F.add(f'<path d="{lo}" class="fcurve"/>')
    mx = (x0 + x1) / 2
    F.add(f'<line x1="{mx}" y1="{yb-142}" x2="{mx}" y2="{yb-90}" class="fdrop-line"/>')
    F.arrow(mx, yb - 142, mx, yb - 88, "fark", 10, w=2.2)
    F.tag(mx + 146, yb - 128, "≈ 100,000,000× faster", "ftag")
    # legend in the empty top-left corner
    F.add(f'<line x1="{x0+20}" y1="34" x2="{x0+56}" y2="34" class="fcurve-alt"/>')
    F.text(x0 + 66, 38, "without acid: a tall hill", "ft", "start")
    F.add(f'<line x1="{x0+20}" y1="58" x2="{x0+56}" y2="58" class="fcurve"/>')
    F.text(x0 + 66, 62, "with acid (H⁺): a much lower hill", "ftk", "start")
    F.add(f'<line x1="{x0}" y1="{yb+40}" x2="{x1}" y2="{yb+40}" class="faxis"/>')
    F.text(x0 + 36, yb + 22, "start", "fm")
    F.text(x1 - 36, yb + 34, "products", "fm")
    F.text((x0 + x1) / 2, yb + 62, "REACTION PROGRESS →", "fm")
    F.add(f'<text transform="translate({x0-14} {yb-60}) rotate(-90)" class="fm">ENERGY →</text>')


# ---- Quinoxaline drug scaffolds ---------------------------------------------

def quinoxaline(F, cx, cy, a=30, show_labels=True, iodo=True, glow=True):
    """6-amino-5-iodoquinoxaline as a skeletal structure; returns key points."""
    L = hexagon(cx - a * 0.866, cy, a, 30)   # benzo ring (left)
    R = hexagon(cx + a * 0.866, cy, a, 30)   # pyrazine ring (right)
    # vertex order for rot=30: 0 lower-right, 1 bottom, 2 lower-left, 3 upper-left, 4 top, 5 upper-right
    def poly(p):
        return "M" + " L".join(f"{f2(x)} {f2(y)}" for x, y in p) + "Z"
    F.add(f'<path d="{poly(L)}" class="fring"/><path d="{poly(R)}" class="fring"/>')
    # aromatic inner bonds
    def inner(p, i, j, c):
        (x1, y1), (x2, y2) = p[i], p[j]
        k = 0.2
        F.add(f'<line x1="{f2(x1+(c[0]-x1)*k)}" y1="{f2(y1+(c[1]-y1)*k)}" x2="{f2(x2+(c[0]-x2)*k)}" y2="{f2(y2+(c[1]-y2)*k)}" class="fring-in"/>')
    cl, cr = (cx - a * 0.866, cy), (cx + a * 0.866, cy)
    inner(L, 1, 2, cl); inner(L, 3, 4, cl); inner(R, 4, 5, cr); inner(R, 0, 1, cr)
    # nitrogens at the top and bottom of the right ring (positions 1 and 4)
    for i in (4, 1):
        x, y = R[i]
        F.add(f'<circle cx="{f2(x)}" cy="{f2(y)}" r="9" class="fring-bg"/>')
        F.text(x, y + 5, "N", "fatom-n")
    # NH2 on C6 (upper-left vertex of the benzo ring), iodine on C5 (top vertex)
    x6, y6 = L[3]
    x5, y5 = L[4]
    nx, ny = x6 - a * 0.866, y6 - a * 0.5
    F.add(f'<line x1="{f2(x6)}" y1="{f2(y6)}" x2="{f2(nx+6)}" y2="{f2(ny+4)}" class="fring"/>')
    F.text(nx - 2, ny + 3, "NH" + '<tspan dy="4" font-size="0.74em">2</tspan>', "fatom-n", "end")
    ix, iy = x5, y5 - a
    if iodo:
        F.add(f'<line x1="{f2(x5)}" y1="{f2(y5)}" x2="{f2(ix)}" y2="{f2(iy+8)}" class="fring-k"/>')
        if glow:
            F.glow(ix, iy - 6, 26)
        F.ball(ix, iy - 6, 14, "i")
        F.text(ix, iy - 2, "I", "fel-lbl")
    return (x5, y5), (ix, iy - 6), L, R


@fig("quinoxaline-drug-scaffolds", 1)
def _(F):
    F.label = ("The 6-aminoquinoxaline ring system. Iodine attaches at position 5, the ring position right next to "
               "the amine group, giving chemists a handle for building further.")
    (x5, y5), (ix, iy), L, R = quinoxaline(F, 250, 178, a=38)
    if F.mobile:
        F.text(x5 + 14, y5 + 18, "5", "fpos")
        F.text(L[3][0] + 16, L[3][1] + 8, "6", "fpos")
        return
    F.add(f'<line x1="{f2(ix+22)}" y1="{f2(iy-6)}" x2="404" y2="80" class="flead"/>')
    F.lines(410, 76, ["iodine attaches here,", "right next to the amine"], "ftk", "start")
    F.lines(410, 116, ["predicted by a simple", "Hückel calculation"], "fm", "start", lh=15)
    F.text(250, 290, "quinoxaline: a benzene ring fused to a ring with two nitrogens", "ft")
    # position numbers
    F.text(x5 + 14, y5 + 18, "5", "fpos")
    F.text(L[3][0] + 16, L[3][1] + 8, "6", "fpos")


def mini_scaffold(F, cx, cy, kind):
    """A small fused-ring icon: the quinoxaline core with a new
    five-membered ring fused on the edge where the amine and iodine sat."""
    a = 13
    L = hexagon(cx - a * 0.866, cy, a, 30)
    R = hexagon(cx + a * 0.866, cy, a, 30)
    path = lambda p: "M" + " L".join(f"{f2(x)} {f2(y)}" for x, y in p) + "Z"
    # pentagon sharing the edge L[3]-L[4], built outward from the benzo ring
    (x1, y1), (x2, y2) = L[3], L[4]
    mx, my = (x1 + x2) / 2, (y1 + y2) / 2
    ox, oy = mx - (cx - a * 0.866), my - cy
    n = math.hypot(ox, oy)
    ox, oy = ox / n, oy / n
    c5 = (mx + ox * a * 0.688, my + oy * a * 0.688)
    a0 = math.atan2(y1 - c5[1], x1 - c5[0])
    R5 = a * 0.851
    cand = []
    for d in (1, -1):
        pts = [(c5[0] + R5 * math.cos(a0 + d * math.radians(72 * k)), c5[1] + R5 * math.sin(a0 + d * math.radians(72 * k))) for k in range(5)]
        cand.append((math.hypot(pts[1][0] - x2, pts[1][1] - y2), pts))
    pent = min(cand)[1]
    F.add(f'<path d="{path(pent)}" class="fring-sk"/>')
    F.add(f'<path d="{path(L)}" class="fring-s"/><path d="{path(R)}" class="fring-s"/>')
    for i in (4, 1):
        F.add(f'<circle cx="{f2(R[i][0])}" cy="{f2(R[i][1])}" r="4.6" class="fring-bg2"/>')
        F.text(R[i][0], R[i][1] + 3.2, "N", "fatom-s")
    # pent[0], pent[1] are the shared carbons (old amine and iodine sites);
    # the amine nitrogen stays in the new ring next to pent[0]
    labels = {4: "N"}
    if kind != "six":
        labels[2] = "O" if kind == "ox" else "S"
    for i, lbl in labels.items():
        hx, hy = pent[i]
        F.add(f'<circle cx="{f2(hx)}" cy="{f2(hy)}" r="5" class="fring-bg2"/>')
        F.text(hx, hy + 3.2, lbl, "fatom-s")
    if kind == "six":
        # isatin: two C=O groups on the five-membered ring
        for v in (pent[2], pent[3]):
            dx, dy = v[0] - c5[0], v[1] - c5[1]
            m = math.hypot(dx, dy)
            ex, ey = v[0] + dx / m * 10, v[1] + dy / m * 10
            F.stick(v[0], v[1], ex, ey, w=1.4, order=2, cls="stk-thin")
            F.text(ex + dx / m * 5, ey + dy / m * 5 + 3, "O", "fatom-o")


@fig("quinoxaline-drug-scaffolds", 2)
def _(F):
    F.label = ("From one iodinated starting molecule, three families of fused-ring molecules were made: "
               "oxazolo- and thiazolo-quinoxalines and the new pyrazino-isatins. All were tested for fluorescence, "
               "kinase inhibition and effects on cancer cells.")
    F.add('<rect x="216" y="18" width="208" height="92" rx="12" class="fcard-k"/>')
    quinoxaline_small(F, 320, 70)
    F.text(320, 102, "iodinated starting molecule", "fm")
    fams = (("oxazolo-fused", "quinoxalines", "ox"), ("thiazolo-fused", "quinoxalines", "th"), ("pyrazino-isatins", "new in this work", "six"))
    for k, (a, b, kind) in enumerate(fams):
        cx = 110 + k * 210
        F.arrow(320, 112, cx, 150, "fark", 10, ctrl=(cx if k != 1 else 320, 120), w=2)
        F.add(f'<rect x="{cx-92}" y="154" width="184" height="96" rx="12" class="fcard"/>')
        mini_scaffold(F, cx - 2, 186, kind)
        F.text(cx, 228, a, "ftb")
        F.text(cx, 244, b, "ftk" if kind == "six" else "fm")
    chips = ("fluorescence", "kinase inhibition", "cancer cells")
    F.text(70, 290, "TESTED FOR", "fm", "start")
    x = 160
    for c in chips:
        w = 7.2 * len(c) + 18
        F.tag(x + w / 2, 286, c, "ftagn")
        x += w + 10


def quinoxaline_small(F, cx, cy):
    a = 15
    L = hexagon(cx - a * 0.866, cy, a, 30)
    R = hexagon(cx + a * 0.866, cy, a, 30)
    path = lambda p: "M" + " L".join(f"{f2(x)} {f2(y)}" for x, y in p) + "Z"
    F.add(f'<path d="{path(L)}" class="fring-s"/><path d="{path(R)}" class="fring-s"/>')
    for i in (4, 1):
        F.add(f'<circle cx="{f2(R[i][0])}" cy="{f2(R[i][1])}" r="5" class="fring-bg2"/>')
        F.text(R[i][0], R[i][1] + 3.5, "N", "fatom-s")
    x6, y6 = L[3]
    F.add(f'<line x1="{f2(x6)}" y1="{f2(y6)}" x2="{f2(x6-11)}" y2="{f2(y6-6)}" class="fring-s"/>')
    F.text(x6 - 13, y6 - 3, "NH<tspan dy='3' font-size='.74em'>2</tspan>", "fatom-s", "end")
    x5, y5 = L[4]
    F.add(f'<line x1="{f2(x5)}" y1="{f2(y5)}" x2="{f2(x5)}" y2="{f2(y5-10)}" class="fring-s"/>')
    F.ball(x5, y5 - 16, 7, "i")


# ---- Spin-aware reaction discovery ------------------------------------------

@fig("spin-aware-reaction-discovery", 1)
def _(F):
    F.label = ("Energy along a reaction for two spin states, drawn as two curves. Where the curves cross, at the "
               "minimum-energy crossing point, a reacting molecule can switch from one spin state to the other.")
    x0, x1, yb = 70, 600, 262

    def A(t):
        return 40 + 330 * (t - 0.28) ** 2

    def B(t):
        return 58 + 330 * (t - 0.72) ** 2

    def X(t):
        return x0 + 20 + t * (x1 - x0 - 40)

    def path(fn):
        return "M" + " L".join(f"{f2(X(t/100))} {f2(yb - fn(t/100))}" for t in range(101))
    F.defs.append(f'<linearGradient id="{F.p}-a" x1="0" y1="0" x2="0" y2="1"><stop offset="0" class="ga0"/><stop offset="1" class="ga1"/></linearGradient>')
    F.defs.append(f'<linearGradient id="{F.p}-b" x1="0" y1="0" x2="0" y2="1"><stop offset="0" class="gw0"/><stop offset="1" class="gw1"/></linearGradient>')
    # soft wells under each curve's valley
    F.add(f'<path d="{path(A)} L{x1-20} {yb} L{x0+20} {yb}Z" fill="url(#{F.p}-a)" opacity=".7"/>')
    F.add(f'<path d="{path(B)} L{x1-20} {yb} L{x0+20} {yb}Z" fill="url(#{F.p}-b)" opacity=".7"/>')
    F.add(f'<path d="{path(A)}" class="fcurve"/><path d="{path(B)}" class="fcurve-w"/>')
    t = 0.5 + 18 / 330 / 0.88
    cx, cy = X(t), yb - A(t)
    F.glow(cx, cy, 30)
    F.add(f'<circle cx="{f2(cx)}" cy="{f2(cy)}" r="7" class="fdot"/>')
    F.add(f'<line x1="{f2(cx)}" y1="{f2(cy-12)}" x2="{f2(cx)}" y2="96" class="flead"/>')
    F.text(cx, 76, "crossing point:", "ftb")
    F.text(cx, 92, "the molecule can switch here", "ft")

    def spins(x, y, pattern, cls):
        for k, up in enumerate(pattern):
            xx = x + k * 10
            if up:
                F.arrow(xx, y + 8, xx, y - 8, cls, 6, w=1.8)
            else:
                F.arrow(xx, y - 8, xx, y + 8, cls, 6, w=1.8)
    ax = X(0.28)
    F.text(ax, yb - 48 + 24, "spin state A", "ftk")
    spins(ax - 15, yb - 48 + 44 - 74, [1, 0, 1, 0], "fark")
    bx = X(0.72)
    F.text(bx, yb - 58 + 24, "spin state B", "ftw")
    spins(bx - 15, yb - 58 - 30, [1, 1, 1, 1], "farw")
    F.add(f'<line x1="{x0}" y1="{yb}" x2="{x1}" y2="{yb}" class="faxis"/>')
    F.text((x0 + x1) / 2, yb + 26, "REACTION PROGRESS →", "fm")
    F.add(f'<text transform="translate({x0-14} {yb-100}) rotate(-90)" class="fm">ENERGY →</text>')


@fig("spin-aware-reaction-discovery", 2)
def _(F):
    F.label = ("The three iron systems and their outcomes: the iron–ethyl complex gave a reliable result; the "
               "double-bond-shifting iron catalyst gave a crossing whose energy is uncertain; the iron–nitrene system "
               "was flagged by the program as too complex for its simple method.")
    rows = (("good", "Reliable", "Iron–ethyl complex", "crossing found, and it is not the bottleneck"),
            ("warn", "Uncertain", "Iron catalyst that shifts double bonds", "crossing found, but its energy is uncertain"),
            ("bad", "Don’t trust", "Iron–nitrene system", "flagged by the program: too complex to trust"))
    for k, (st, verdict, name, note) in enumerate(rows):
        y = 18 + k * 96
        F.add(f'<rect x="16" y="{y}" width="608" height="84" rx="12" class="fpanel"/>')
        F.add(f'<rect x="16" y="{y}" width="6" height="84" rx="3" class="fst-{st}"/>')
        cx, cy = 66, y + 42
        F.add(f'<circle cx="{cx}" cy="{cy}" r="22" class="fst-{st}-bg"/>')
        if st == "good":
            F.add(f'<path d="M{cx-9} {cy}l6 7 13-14" class="fic fic-{st}"/>')
        elif st == "warn":
            F.add(f'<path d="M{cx} {cy-10}v11" class="fic fic-{st}"/><circle cx="{cx}" cy="{cy+9}" r="2.2" class="fst-{st}"/>')
        else:
            F.add(f'<path d="M{cx-8} {cy-8}l16 16M{cx+8} {cy-8}l-16 16" class="fic fic-{st}"/>')
        F.text(108, y + 36, name, "ftb", "start")
        F.text(108, y + 58, note, "fm2", "start")
        F.tag(600, y + 42, verdict, f"fst-tag-{st}", "end")
        # a tiny iron atom
    F.text(624, 312, "", "fm", "end")


# ---- Water and metathesis catalysts -----------------------------------------

@fig("water-and-metathesis-catalysts", 1)
def _(F):
    F.label = ("Performance kept with 1% water, as a share of performance when dry, drawn to scale. "
               "Fast-starting catalyst 1: 3%. Fast-starting catalyst 2: 10%. Slow-starting iodide catalyst: 56%.")
    x0, W = 230, 360
    rows = (("Fast-starting catalyst 1", 3, False), ("Fast-starting catalyst 2", 10, False), ("Slow-starting iodide catalyst", 56, True))
    for k, (name, v, key) in enumerate(rows):
        y = 70 + k * 66
        F.text(x0 - 16, y + 5, name, "ftb" if key else "ft", "end")
        F.add(f'<rect x="{x0}" y="{y-16}" width="{W}" height="32" rx="4" class="ftrack"/>')
        F.add(f'<rect x="{x0}" y="{y-16}" width="{f2(max(v/100*W, 6))}" height="32" rx="4" class="{"fbark" if key else "fbar"}"/>')
        F.text(x0 + v / 100 * W + 10, y + 5, f"{v}%", "fvalue-k" if key else "fvalue", "start")
    F.add(f'<line x1="{x0+W}" y1="38" x2="{x0+W}" y2="226" class="fref"/>')
    F.text(x0 + W, 30, "100% = AS GOOD AS DRY", "fm", "end")
    for v in (0, 25, 50, 75, 100):
        xx = x0 + v / 100 * W
        F.text(xx, 250, f"{v}%", "fm")
    F.text(x0 + W / 2, 282, "PERFORMANCE KEPT WITH 1% WATER IN THE SOLVENT", "fm")


@fig("water-and-metathesis-catalysts", 2)
def _(F):
    F.label = ("A race. The catalyst starts at the left. One track leads to the finish, making product; the other "
               "leads to the catalyst being decomposed by water. The catalyst must make product before water destroys it.")
    F.add('<path d="M96 160C200 160 250 84 380 76L560 72" class="ftrack-l"/>')
    F.add('<path d="M96 160C200 160 250 236 380 244L520 248" class="ftrack-l"/>')
    F.add('<path d="M96 160C200 160 250 84 380 76L560 72" class="frace"/>')
    F.add('<path d="M96 160C200 160 250 236 380 244L520 248" class="frace-bad"/>')
    F.arrow(540, 72, 566, 72, "fark", 12, w=3)
    F.arrow(500, 248, 526, 248, "farw", 12, w=3)
    # catalyst at the start
    F.glow(78, 160, 30)
    F.shadow(78, 186, 26, 4)
    catalyst(F, 78, 160, 1.6)
    F.text(78, 210, "catalyst", "ftb")
    # finish flag
    fx, fy = 580, 72
    F.add(f'<line x1="{fx}" y1="{fy+20}" x2="{fx}" y2="{fy-34}" class="fpole"/>')
    for r in range(3):
        for c in range(4):
            if (r + c) % 2 == 0:
                F.add(f'<rect x="{fx+c*7}" y="{fy-34+r*7}" width="7" height="7" class="fflag"/>')
    F.add(f'<rect x="{fx}" y="{fy-34}" width="28" height="21" class="fflag-o"/>')
    F.text(570, 112, "makes product", "ftk", "end")
    # water drops and broken catalyst
    for (x, y, s) in ((330, 206, 1), (392, 214, 0.8), (444, 222, 0.9)):
        F.add(f'<path d="M{x} {y-12*s}c{f2(5*s)} {f2(7*s)} {f2(8*s)} {f2(11*s)} {f2(8*s)} {f2(15*s)}a{f2(8*s)} {f2(8*s)} 0 0 1 {f2(-16*s)} 0c0 {f2(-4*s)} {f2(3*s)} {f2(-8*s)} {f2(8*s)} {f2(-15*s)}z" class="fwdrop"/>')
    F.add('<g opacity=".55">')
    F.ball(552, 244, 6.5, "ru")
    F.ball(570, 256, 4.2, "c")
    F.ball(560, 228, 4.2, "c")
    F.ball(578, 236, 4.2, "c")
    F.add("</g>")
    F.text(586, 286, "decomposed by water", "ftw", "end")
    F.water(258, 190, 0.9, -60)
    F.water(292, 214, 0.8, -120)
    F.text(32, 40, "A RACE AGAINST WATER", "fhead", "start")


# ---- Water on ten-atom ruthenium ---------------------------------------------

@fig("water-on-ten-atom-ruthenium", 1)
def _(F):
    F.label = ("Left: on a flat ruthenium surface, the standard calculation tears water into separate oxygen and hydrogen "
               "atoms. Right: on a ten-atom ruthenium cluster on titanium dioxide, water stays as OH groups on the edge atoms.")
    panel(F, 16, 16, 296, 284, "FLAT METAL (THE USUAL MODEL)")
    panel(F, 328, 16, 296, 284, "TEN-ATOM CLUSTER")
    top = F.slab(40, 206, 11, 3, 23, 8, -5, 10.5, lambda a, b: "ru", depth=22, face="ru")
    F.water(164, 82, 1.2)
    F.arrow(164, 102, 164, 160, "far", 10)
    # pieces scattered on the surface
    F.ball(110, 194, 8.5, "o")
    F.ball(170, 192, 5.5, "h")
    F.ball(218, 196, 5.5, "h")
    for x, lbl in ((110, "O"), (170, "H"), (218, "H")):
        F.text(x, 176, lbl, "fpiece")
    F.add('<path d="M126 192h28M184 194h18" class="fsplit"/>')
    F.text(164, 280, "water torn apart: no OH left", "ft")
    tio2(F, 352, 220, 12)
    pos = ru10(F, 470, 222, r=12)
    # OH groups on edge atoms
    for (ax, ay), sgn in ((pos[0], -1), (pos[3], 1), (pos[9], 0)):
        if sgn == 0:
            ox, oy = ax, ay - 26
            hx, hy = ax + 10, ay - 40
        else:
            ox, oy = ax + sgn * 22, ay - 16
            hx, hy = ox + sgn * 12, oy - 10
        F.glow(ox, oy, 16)
        F.molecule([("o", ox, oy, 8.5, 5), ("h", hx, hy, 5.2, 5)], [(0, 1)], w=3)
        F.stick(ax, ay, ox, oy, w=3)
        F.ball(ox, oy, 8.5, "o")
        F.ball(hx, hy, 5.2, "h")
    F.text(398, 160, "OH", "ftk")
    F.text(546, 160, "OH", "ftk")
    F.text(476, 280, "water stays as OH at the edge", "ft")


@fig("water-on-ten-atom-ruthenium", 2)
def _(F):
    F.label = ("A ten-atom ruthenium cluster on titanium dioxide surrounded by about six water molecules, the state "
               "predicted between about 400 and 530 kelvin. The cluster's edge atoms, where the chemistry happens, are highlighted.")
    tio2(F, 120, 246, 18, rows=3)
    pos = ru10(F, 316, 250, r=13)
    edge = [0, 3, 4, 6, 7, 9]
    for i in edge:
        F.glow(pos[i][0], pos[i][1], 20)
    for i, (x, y) in enumerate(pos):
        F.ball(x, y, 13, "ru", "hl" if i in edge else "")
    for (x, y, a) in ((228, 214, -40), (240, 148, -120), (290, 92, -60), (352, 94, -110), (402, 152, -70), (414, 216, -150)):
        F.water(x, y, 1.15, a)
    if F.mobile:
        F.text(316, 312, "about six water molecules at working temperature", "ft")
        return
    F.add('<line x1="368" y1="226" x2="488" y2="176" class="flead"/>')
    F.lines(494, 168, ["edge atoms:", "where the chemistry", "happens"], "ftk", "start")
    # thermometer badge
    tx, ty = 70, 76
    F.add(f'<rect x="{tx-6}" y="{ty-50}" width="12" height="70" rx="6" class="ftherm"/>')
    F.add(f'<circle cx="{tx}" cy="{ty+26}" r="11" class="ftherm-b"/>')
    F.add(f'<rect x="{tx-2.5}" y="{ty-30}" width="5" height="54" rx="2.5" class="ftherm-f"/>')
    F.lines(92, 52, ["400–530 K", "working temperature"], "fm", "start", lh=15)
    F.add('<path d="M92 72h0" />')
    F.text(316, 312, "about six water molecules at working temperature", "ft")


# --------------------------------------------------------------------------
# Phone layouts
#
# Below 560px the page swaps each figure for a narrow version, 360 units
# wide, so labels stay readable. Most are recomposed from the desktop
# drawing: crop() cuts out a region (a panel, a molecule, a label) and
# places it in a vertical stack, so the chemistry is drawn only once. Charts
# and energy curves, which cannot be cut up, get their own narrow drawing.
# --------------------------------------------------------------------------

M = 360
MOBILE = {}


def mob(page, n):
    def deco(fn):
        MOBILE[(page, n)] = fn
        return fn
    return deco


def crop(x, y, w, h, s=None, tx=None):
    return ("crop", x, y, w, h, s, tx)


def draw(h, fn):
    return ("draw", h, fn)


def text(rows, cls="ft", lh=17):
    return ("text", rows, cls, lh)


def gap(h):
    return ("gap", h)


def legend(entries):
    """Element key, wrapped two to a row."""
    rows = (len(entries) + 1) // 2

    def fn(F):
        for k, e in enumerate(entries):
            el, name = e[0], e[1]
            x, y = 70 + (k % 2) * 140, 12 + (k // 2) * 22
            if len(e) > 2:
                F.glow(x, y, 10)
            F.ball(x, y, 6.5, el, e[2] if len(e) > 2 else "")
            F.text(x + 12, y + 4, name, "fm", "start")
    return draw(rows * 22 + 4, fn)


def down_arrow(label=None, sub_label=None, h=70, deco=None):
    def fn(F):
        F.arrow(M / 2, 6, M / 2, h - 8, "fark", 11, w=2.4)
        if label:
            F.text(M / 2 + 16, h / 2 + 1, label, "ftk", "start")
        if sub_label:
            F.text(M / 2 + 16, h / 2 + 17, sub_label, "fm", "start")
        if deco:
            deco(F)
    return draw(h, fn)


def stack(F, desktop_body, items):
    y = 10
    for k, it in enumerate(items):
        kind = it[0]
        if kind == "crop":
            _, x, y0, w, h, s, tx = it
            s = s or min(M / w, 1.15)
            tx = (M - w * s) / 2 if tx is None else tx
            cid = f"{F.p}-c{k}"
            F.defs.append(f'<clipPath id="{cid}"><rect x="{f2(x)}" y="{f2(y0)}" width="{f2(w)}" height="{f2(h)}"/></clipPath>')
            F.add(f'<g transform="translate({f2(tx)} {f2(y)}) scale({s:.4f}) translate({f2(-x)} {f2(-y0)})">'
                  f'<g clip-path="url(#{cid})">{desktop_body}</g></g>')
            y += h * s + 8
        elif kind == "draw":
            F.add(f'<g transform="translate(0 {f2(y)})">')
            it[2](F)
            F.add("</g>")
            y += it[1] + 6
        elif kind == "text":
            _, rows, cls, lh = it
            F.lines(M / 2, y + 13, rows, cls, "middle", lh)
            y += len(rows) * lh + 6
        else:
            y += it[1]
    F.w, F.h = M, int(y + 6)


# ---- stacked versions of the desktop drawings ------------------------------

PANELS = {
    ("can-parking-spots-help-catalysts", 1): [crop(16, 16, 296, 270), crop(328, 16, 296, 270)],
    ("fluorine-count-on-gold-coatings", 2): [crop(16, 16, 290, 268), crop(324, 16, 290, 268), crop(420, 288, 210, 20, 1.0)],
    ("how-tightly-molecules-stick", 2): [crop(16, 16, 290, 278), crop(334, 16, 290, 278)],
    ("light-driven-crowded-ethers", 2): [crop(16, 16, 290, 278), crop(334, 16, 290, 278)],
    ("missing-oxygen-atoms-reshape-clusters", 2): [crop(16, 16, 296, 288), crop(328, 16, 296, 288)],
    ("water-on-ten-atom-ruthenium", 1): [crop(16, 16, 296, 284), crop(328, 16, 296, 284)],
}
for _k, _items in PANELS.items():
    MOBILE[_k] = (lambda items: lambda F: items)(_items)


@mob("carbodicarbene-coatings-on-gold", 1)
def _(F):
    def heat(F):
        flame(F, M / 2 - 34, 30, 0.8)
    return [crop(16, 16, 272, 268), down_arrow("heat", h=64, deco=heat), crop(352, 16, 272, 268),
            legend([("c", "central carbon", "hl"), ("n", "nitrogen"), ("au", "gold")])]


@mob("fluorine-count-on-gold-coatings", 1)
def _(F):
    return [crop(16, 16, 366, 252, 0.98), crop(381, 16, 243, 252, 0.98),
            draw(30, lambda F: (F.add('<circle cx="58" cy="14" r="5" class="fkey-au"/>'),
                                F.text(70, 18, "Au atom pulled out of the surface: the anchor", "fm", "start")))]


@mob("forever-chemical-fragment-on-ice", 1)
def _(F):
    def snow(F):
        sx, sy = M / 2 - 40, 34
        for k in range(3):
            a = math.radians(k * 60)
            F.add(f'<line x1="{f2(sx-11*math.cos(a))}" y1="{f2(sy-11*math.sin(a))}" x2="{f2(sx+11*math.cos(a))}" y2="{f2(sy+11*math.sin(a))}" class="fsnow"/>')
    return [crop(36, 44, 234, 222), down_arrow("on ice", "≥ 29 kJ/mol downhill", h=74, deco=snow),
            crop(420, 84, 190, 182),
            legend([("c", "carbon"), ("o", "oxygen"), ("f", "fluorine"), ("h", "hydrogen")])]


@mob("forever-chemical-fragment-on-ice", 2)
def _(F):
    return [crop(176, 34, 310, 262),
            text(["HFA sinks into the ice", "and becomes the diol (glowing)"], "ftk"),
            text(["ICE FILM A FEW NM THICK, ON PLATINUM,", "INSIDE A VACUUM CHAMBER"], "fm", 15)]


@mob("graphite-support-co2-catalyst", 1)
def _(F):
    return [crop(396, 62, 84, 58, 1.15),
            down_arrow("binds more easily", h=60),
            crop(140, 74, 240, 214),
            text(["electrons flow both ways"], "ftk"),
            text(["graphene: a one-atom-thick", "sheet of carbon"], "ft")]


@mob("light-driven-crowded-ethers", 1)
def _(F):
    def lamp(F):
        F.defs.append(f'<linearGradient id="{F.p}-mbeam" x1="1" y1="0" x2="0" y2="0"><stop offset="0" class="gbeam0"/><stop offset="1" class="gbeam1"/></linearGradient>')
        F.add(f'<rect x="{M/2-78}" y="8" width="10" height="56" rx="3" class="fled"/>')
        F.add(f'<path d="M{M/2-68} 12L{M/2-8} 2L{M/2-8} 70L{M/2-68} 60Z" fill="url(#{F.p}-mbeam)"/>')
    return [crop(20, 96, 268, 144), down_arrow("blue light", h=74, deco=lamp), crop(398, 64, 242, 160),
            legend([("c", "carbon"), ("o", "oxygen"), ("h", "hydrogen")])]


@mob("missing-oxygen-atoms-reshape-clusters", 1)
def _(F):
    return [crop(16, 16, 296, 268), crop(328, 16, 296, 268),
            legend([("ru", "ruthenium"), ("ti", "titanium"), ("o", "oxygen")])]


@mob("perrhenate-acid-deoxydehydration", 1)
def _(F):
    def cat(F):
        F.arrow(110, 6, 110, 120, "fark", 11, w=2.4)
    return [crop(20, 78, 182, 210), ("draw", 0, cat), crop(236, 60, 98, 154, 1.0, 140),
            crop(380, 92, 252, 198)]


@mob("quinoxaline-drug-scaffolds", 1)
def _(F):
    return [crop(108, 70, 236, 166, 1.3),
            text(["iodine attaches here,", "right next to the amine"], "ftk"),
            text(["PREDICTED BY A SIMPLE HÜCKEL CALCULATION"], "fm"),
            gap(6),
            text(["quinoxaline: a benzene ring fused", "to a ring with two nitrogens"], "ft")]


@mob("water-on-ten-atom-ruthenium", 2)
def _(F):
    def therm(F):
        tx, ty = 104, 30
        F.add(f'<rect x="{tx-5}" y="{ty-22}" width="10" height="40" rx="5" class="ftherm"/>')
        F.add(f'<circle cx="{tx}" cy="{ty+20}" r="9" class="ftherm-b"/>')
        F.add(f'<rect x="{tx-2}" y="{ty-12}" width="4" height="30" rx="2" class="ftherm-f"/>')
        F.lines(124, 28, ["400–530 K", "WORKING TEMPERATURE"], "fm", "start", lh=15)
    return [crop(150, 66, 330, 256), gap(4),
            text(["edge atoms (ringed): where", "the chemistry happens"], "ftk"),
            draw(58, therm)]


# ---- narrow drawings for charts and curves ---------------------------------

CUSTOM = {}


def mcustom(page, n, h):
    def deco(fn):
        CUSTOM[(page, n)] = (fn, h)
        return fn
    return deco


@mcustom("can-parking-spots-help-catalysts", 2, 318)
def _(F):
    x0, x1, y0, y1 = 44, 340, 254, 40
    F.defs.append(f'<linearGradient id="{F.p}-area" x1="0" y1="0" x2="0" y2="1"><stop offset="0" class="ga0"/><stop offset="1" class="ga1"/></linearGradient>')
    pts = []
    for i in range(121):
        t = i / 120
        v = (t / 0.42) ** 1.6 * math.exp(1.6 * (1 - t / 0.42)) if t > 0 else 0
        pts.append((x0 + t * (x1 - x0), y0 - 12 - v * 170))
    F.add(f'<rect x="{f2(x0+0.33*(x1-x0))}" y="{y1}" width="{f2(0.18*(x1-x0))}" height="{y0-y1}" class="fband"/>')
    path = "M" + " L".join(f"{f2(a)} {f2(b)}" for a, b in pts)
    F.add(f'<path d="{path} L{x1} {y0} L{x0} {y0}Z" fill="url(#{F.p}-area)"/>')
    F.add(f'<path d="{path}" class="fcurve"/>')
    F.add(f'<line x1="{x0}" y1="{y0}" x2="{x1+6}" y2="{y0}" class="faxis"/><line x1="{x0}" y1="{y0}" x2="{x0}" y2="{y1-6}" class="faxis"/>')
    F.arrow(x1, y0, x1 + 12, y0, "fax", 8)
    F.arrow(x0, y1, x0, y1 - 12, "fax", 8)
    px = x0 + 0.42 * (x1 - x0)
    py = min(p[1] for p in pts)
    F.glow(px, py, 20)
    F.add(f'<circle cx="{f2(px)}" cy="{f2(py)}" r="6" class="fdot"/>')
    F.text(px, py - 14, "best depth", "ftk")
    F.lines(150, 206, ["too shallow:", "catalysts still clump"], "ft")
    F.lines(346, 204, ["too deep:", "too slow to finish"], "ft", "end")
    F.text((x0 + x1) / 2, y0 + 26, "DEEPER PARKING SPOT →", "fm")
    F.add(f'<text transform="translate({x0-16} {(y0+y1)/2+40}) rotate(-90)" class="fm">TOTAL PRODUCT MADE →</text>')
    F.text(x1 + 6, y0 + 48, "SCHEMATIC, NOT DATA", "fm", "end")


@mcustom("carbodicarbene-coatings-on-gold", 2, 344)
def _(F):
    yv, scale = 56, 40
    yf_bare, yf_coat = yv + 4.98 * scale, yv + 3.98 * scale
    F.add(f'<line x1="12" y1="{yv}" x2="348" y2="{yv}" class="fvac"/>')
    F.text(348, yv - 10, "VACUUM: ELECTRON IS FREE", "fm", "end")
    for (x, yfl, title, coated) in ((22, yf_bare, "bare gold", False), (198, yf_coat, "coated gold", True)):
        w = 140
        F.add(f'<rect x="{x}" y="{f2(yfl)}" width="{w}" height="{f2(300-yfl)}" class="fsea"/>')
        F.add(f'<line x1="{x}" y1="{f2(yfl)}" x2="{x+w}" y2="{f2(yfl)}" class="ffermi"/>')
        for k in range(7):
            F.add(f'<circle cx="{x+13+k*19}" cy="{f2(yfl+12)}" r="4" class="fel"/>')
            if coated:
                xx = x + 13 + k * 19
                F.add(f'<line x1="{xx}" y1="{f2(yfl-4)}" x2="{xx}" y2="{f2(yfl-17)}" class="fcoat"/>')
                F.add(f'<circle cx="{xx}" cy="{f2(yfl-20)}" r="3.6" class="fcoat-h"/>')
        ax = x + 40
        bot = yfl - (24 if coated else 6)
        F.arrow(ax, bot, ax, yv + 4, "fark" if coated else "far", 10, w=2.4)
        F.tag(ax + 50, (yv + bot) / 2, "3.98 eV" if coated else "4.98 eV", "ftag" if coated else "ftagn")
        F.text(x + w / 2, 322, title, "ftb")
    F.add(f'<path d="M180 {f2(yf_coat)}v{f2(yf_bare-yf_coat)}" class="fbrace"/>')
    F.text(174, yf_bare - 54, "up to 1 eV", "ftk", "end")
    F.text(174, yf_bare - 38, "easier", "ft", "end")


@mcustom("graphite-support-co2-catalyst", 2, 316)
def _(F):
    yb = 236
    F.add(f'<line x1="8" y1="{yb+30}" x2="352" y2="{yb+30}" class="fgrid"/>')
    for (x, top, title, key) in ((10, 70, "complex alone", False), (188, 136, "on graphite", True)):
        F.add(f'<line x1="{x}" y1="{yb}" x2="{x+36}" y2="{yb}" class="flevel"/>')
        F.add(f'<line x1="{x+60}" y1="{top}" x2="{x+100}" y2="{top}" class="flevel{" flevel--k" if key else ""}"/>')
        F.add(f'<line x1="{x+36}" y1="{yb}" x2="{x+60}" y2="{top}" class="fconn"/>')
        F.arrow(x + 116, yb, x + 116, top + 4, "fark" if key else "far", 10, w=2.2)
        F.add(f'<line x1="{x+104}" y1="{yb}" x2="{x+128}" y2="{yb}" class="fguide"/>')
        F.text(x + 18, yb + 20, "start", "fm")
        F.text(x + 80, top - 12, sub("CO", "2", " in"), "fm")
        F.text(x + 70, yb + 54, title, "ftb")
        F.tag(x + 142, (top + yb) / 2, "cost", "ftag" if key else "ftagn")
    F.add('<line x1="110" y1="70" x2="300" y2="70" class="fguide"/>')
    F.add('<path d="M240 76V128" class="fbrace"/>')
    F.text(232, 98, "saved", "ftk", "end")
    F.text(232, 114, "on graphite", "ft", "end")
    F.text(352, 306, "SCHEMATIC, NOT TO SCALE", "fm", "end")


@mcustom("how-tightly-molecules-stick", 1, 300)
def _(F):
    x0, s = 20, 4.6
    rows = (("Shortcut", 46, [(26, "fbar")]),
            ("Full simulation", 132, [(26, "fbar"), (2, "fbar2"), (36, "fbark")]))
    for name, y, segs in rows:
        F.text(x0, y - 26, name, "ftb", "start")
        x = x0
        for k, (v, cls) in enumerate(segs):
            w = v * s - (2 if k < len(segs) - 1 else 0)
            F.add(f'<rect x="{f2(x)}" y="{y-18}" width="{f2(w)}" height="36" rx="4" class="{cls}"/>')
            x += v * s
        F.text(x + 6, y + 5, f"−{sum(v for v, _ in segs)}", "fvalue", "start")
    F.text(x0 + 46 * s, 137, "slide, spin, rock: 36", "fonbar")
    F.add(f'<line x1="{f2(x0+27*s)}" y1="112" x2="{f2(x0+27*s)}" y2="100" class="flead"/>')
    F.text(x0 + 27 * s + 6, 100, "irregular jiggling: 2", "ft", "start")
    F.add(f'<path d="M{f2(x0+26*s)} 158v8h{f2(38*s)}v-8" class="fbrace2"/>')
    F.text(x0 + 45 * s, 186, "what the shortcut misses: 38", "ftk")
    for v in range(0, 71, 10):
        xx = x0 + v * s
        F.add(f'<line x1="{f2(xx)}" y1="214" x2="{f2(xx)}" y2="220" class="ftick"/>')
        F.text(xx, 236, f"−{v}" if v else "0", "fm")
    F.add(f'<line x1="{x0}" y1="214" x2="{f2(x0+70*s)}" y2="214" class="faxis"/>')
    F.lines(M / 2, 264, ["BINDING STRENGTH, kJ/mol", "LONGER BAR = STICKIER"], "fm", "middle", 15)


@mcustom("perrhenate-acid-deoxydehydration", 2, 316)
def _(F):
    x0, x1, yb = 36, 344, 236
    F.defs.append(f'<linearGradient id="{F.p}-area" x1="0" y1="0" x2="0" y2="1"><stop offset="0" class="ga0"/><stop offset="1" class="ga1"/></linearGradient>')

    def curve(h, end=14):
        pts = []
        for i in range(101):
            t = i / 100
            pts.append((x0 + 14 + t * (x1 - x0 - 28), yb - h * math.exp(-((t - 0.5) / 0.17) ** 2) + end * t))
        return "M" + " L".join(f"{f2(a)} {f2(b)}" for a, b in pts)
    hi, lo = curve(140), curve(80)
    F.add(f'<path d="{lo} L{x1-14} {yb+40} L{x0+14} {yb+40}Z" fill="url(#{F.p}-area)"/>')
    F.add(f'<path d="{hi}" class="fcurve-alt"/><path d="{lo}" class="fcurve"/>')
    mx = (x0 + x1) / 2
    F.arrow(mx, yb - 132, mx, yb - 84, "fark", 10, w=2.2)
    F.tag(292, yb - 112, "100 million\u00d7", "ftag")
    F.text(292, yb - 86, "faster", "ftk")
    F.add(f'<line x1="{x0}" y1="28" x2="{x0+30}" y2="28" class="fcurve-alt"/>')
    F.text(x0 + 40, 32, "without acid: a tall hill", "ft", "start")
    F.add(f'<line x1="{x0}" y1="52" x2="{x0+30}" y2="52" class="fcurve"/>')
    F.text(x0 + 40, 56, "with acid (H⁺): a much lower hill", "ftk", "start")
    F.add(f'<line x1="{x0}" y1="{yb+40}" x2="{x1}" y2="{yb+40}" class="faxis"/>')
    F.text(x0 + 22, yb + 22, "start", "fm")
    F.text(x1 - 28, yb + 34, "products", "fm")
    F.text(mx, yb + 62, "REACTION PROGRESS →", "fm")


@mcustom("spin-aware-reaction-discovery", 1, 306)
def _(F):
    x0, x1, yb = 36, 344, 262

    def A(t):
        return 40 + 330 * (t - 0.28) ** 2

    def B(t):
        return 58 + 330 * (t - 0.72) ** 2

    def X(t):
        return x0 + 14 + t * (x1 - x0 - 28)

    def path(fn):
        return "M" + " L".join(f"{f2(X(t/100))} {f2(yb - fn(t/100))}" for t in range(101))
    F.defs.append(f'<linearGradient id="{F.p}-a" x1="0" y1="0" x2="0" y2="1"><stop offset="0" class="ga0"/><stop offset="1" class="ga1"/></linearGradient>')
    F.defs.append(f'<linearGradient id="{F.p}-b" x1="0" y1="0" x2="0" y2="1"><stop offset="0" class="gw0"/><stop offset="1" class="gw1"/></linearGradient>')
    F.add(f'<path d="{path(A)} L{x1-14} {yb} L{x0+14} {yb}Z" fill="url(#{F.p}-a)" opacity=".7"/>')
    F.add(f'<path d="{path(B)} L{x1-14} {yb} L{x0+14} {yb}Z" fill="url(#{F.p}-b)" opacity=".7"/>')
    F.add(f'<path d="{path(A)}" class="fcurve"/><path d="{path(B)}" class="fcurve-w"/>')
    t = 0.5 + 18 / 330 / 0.88
    cx, cy = X(t), yb - A(t)
    F.glow(cx, cy, 26)
    F.add(f'<circle cx="{f2(cx)}" cy="{f2(cy)}" r="6.5" class="fdot"/>')
    F.add(f'<line x1="{f2(cx)}" y1="{f2(cy-12)}" x2="{f2(cx)}" y2="80" class="flead"/>')
    F.text(cx, 52, "crossing point:", "ftb")
    F.text(cx, 68, "the molecule can switch here", "ft")

    def spins(x, y, pattern, cls):
        for k, up in enumerate(pattern):
            xx = x + k * 10
            F.arrow(xx, y + 8 if up else y - 8, xx, y - 8 if up else y + 8, cls, 6, w=1.8)
    F.text(X(0.28), yb - 24, "spin state A", "ftk")
    spins(X(0.28) - 15, yb - 78, [1, 0, 1, 0], "fark")
    F.text(X(0.72), yb - 34, "spin state B", "ftw")
    spins(X(0.72) - 15, yb - 88, [1, 1, 1, 1], "farw")
    F.add(f'<line x1="{x0}" y1="{yb}" x2="{x1}" y2="{yb}" class="faxis"/>')
    F.text((x0 + x1) / 2, yb + 26, "REACTION PROGRESS →", "fm")
    F.add(f'<text transform="translate({x0-14} {yb-90}) rotate(-90)" class="fm">ENERGY →</text>')


@mcustom("spin-aware-reaction-discovery", 2, 340)
def _(F):
    rows = (("good", "Reliable", ["Iron\u2013ethyl complex"], ["crossing found, and it is", "not the bottleneck"]),
            ("warn", "Uncertain", ["Iron catalyst that", "shifts double bonds"], ["crossing found, but its", "energy is uncertain"]),
            ("bad", "Don\u2019t trust", ["Iron\u2013nitrene system"], ["flagged by the program:", "too complex to trust"]))
    y = 8
    for st, verdict, name, note in rows:
        h = 82 + 17 * (len(name) - 1)
        F.add(f'<rect x="8" y="{y}" width="344" height="{h}" rx="12" class="fpanel"/>')
        F.add(f'<rect x="8" y="{y}" width="6" height="{h}" rx="3" class="fst-{st}"/>')
        cx, cy = 42, y + 32
        F.add(f'<circle cx="{cx}" cy="{cy}" r="16" class="fst-{st}-bg"/>')
        if st == "good":
            F.add(f'<path d="M{cx-7} {cy}l5 6 10-11" class="fic fic-{st}"/>')
        elif st == "warn":
            F.add(f'<path d="M{cx} {cy-8}v9" class="fic fic-{st}"/><circle cx="{cx}" cy="{cy+7}" r="2" class="fst-{st}"/>')
        else:
            F.add(f'<path d="M{cx-6} {cy-6}l12 12M{cx+6} {cy-6}l-12 12" class="fic fic-{st}"/>')
        F.lines(70, y + 30, name, "ftb", "start", 17)
        F.tag(342, y + 25, verdict, f"fst-tag-{st}", "end")
        F.lines(70, y + 50 + 17 * (len(name) - 1), note, "fm2", "start", 15)
        y += h + 10
    F.h = y


@mcustom("quinoxaline-drug-scaffolds", 2, 452)
def _(F):
    F.add('<rect x="80" y="8" width="200" height="92" rx="12" class="fcard-k"/>')
    quinoxaline_small(F, 180, 60)
    F.text(180, 92, "iodinated starting molecule", "fm")
    F.add('<path d="M50 54V318" class="ftrunk"/><path d="M80 54H50" class="ftrunk"/>')
    fams = (("oxazolo-fused", "quinoxalines", "ox"), ("thiazolo-fused", "quinoxalines", "th"), ("pyrazino-isatins", "new in this work", "six"))
    for k, (a, b, kind) in enumerate(fams):
        y = 116 + k * 92
        F.arrow(50, y + 40, 84, y + 40, "fark", 9, w=2)
        F.add(f'<rect x="90" y="{y}" width="262" height="80" rx="12" class="fcard"/>')
        mini_scaffold(F, 140, y + 44, kind)
        F.text(196, y + 36, a, "ftb", "start")
        F.text(196, y + 54, b, "ftk" if kind == "six" else "fm", "start")
    F.text(M / 2, 406, "TESTED FOR", "fm")
    F.tag(102, 430, "fluorescence", "ftagn")
    F.tag(244, 430, "kinase inhibition", "ftagn")
    F.tag(M / 2, 458, "cancer cells", "ftagn")
    F.h = 474


@mcustom("water-and-metathesis-catalysts", 1, 290)
def _(F):
    x0, W = 20, 280
    rows = (("Fast-starting catalyst 1", 3, False), ("Fast-starting catalyst 2", 10, False), ("Slow-starting iodide catalyst", 56, True))
    for k, (name, v, key) in enumerate(rows):
        y = 66 + k * 70
        F.text(x0, y - 22, name, "ftb" if key else "ft", "start")
        F.add(f'<rect x="{x0}" y="{y-14}" width="{W}" height="28" rx="4" class="ftrack"/>')
        F.add(f'<rect x="{x0}" y="{y-14}" width="{f2(max(v/100*W, 6))}" height="28" rx="4" class="{"fbark" if key else "fbar"}"/>')
        F.text(x0 + max(v / 100 * W, 6) + 8, y + 5, f"{v}%", "fvalue-k" if key else "fvalue", "start")
    F.add(f'<line x1="{x0+W}" y1="30" x2="{x0+W}" y2="222" class="fref"/>')
    F.text(x0 + W + 4, 22, "100% = AS GOOD AS DRY", "fm", "end")
    for v in (0, 50, 100):
        F.text(x0 + v / 100 * W, 244, f"{v}%", "fm")
    F.lines(M / 2, 270, ["PERFORMANCE KEPT WITH 1% WATER"], "fm")


@mcustom("water-and-metathesis-catalysts", 2, 300)
def _(F):
    top = "M64 150C120 150 150 86 220 78L300 74"
    bot = "M64 150C120 150 150 214 220 222L284 226"
    F.add(f'<path d="{top}" class="ftrack-l"/><path d="{bot}" class="ftrack-l"/>')
    F.add(f'<path d="{top}" class="frace"/><path d="{bot}" class="frace-bad"/>')
    F.arrow(290, 74, 312, 74, "fark", 11, w=3)
    F.arrow(276, 226, 298, 226, "farw", 11, w=3)
    F.glow(48, 150, 26)
    F.shadow(48, 174, 22, 4)
    catalyst(F, 48, 150, 1.4)
    F.text(48, 196, "catalyst", "ftb")
    fx, fy = 324, 74
    F.add(f'<line x1="{fx}" y1="{fy+18}" x2="{fx}" y2="{fy-30}" class="fpole"/>')
    for r in range(3):
        for c in range(4):
            if (r + c) % 2 == 0:
                F.add(f'<rect x="{fx+c*6}" y="{fy-30+r*6}" width="6" height="6" class="fflag"/>')
    F.add(f'<rect x="{fx}" y="{fy-30}" width="24" height="18" class="fflag-o"/>')
    F.text(330, 112, "makes product", "ftk", "end")
    for (x, y, s) in ((176, 192, 0.9), (220, 200, 0.75), (256, 204, 0.8)):
        F.add(f'<path d="M{x} {y-12*s}c{f2(5*s)} {f2(7*s)} {f2(8*s)} {f2(11*s)} {f2(8*s)} {f2(15*s)}a{f2(8*s)} {f2(8*s)} 0 0 1 {f2(-16*s)} 0c0 {f2(-4*s)} {f2(3*s)} {f2(-8*s)} {f2(8*s)} {f2(-15*s)}z" class="fwdrop"/>')
    F.water(134, 196, 0.8, -60)
    F.add('<g opacity=".55">')
    F.ball(316, 222, 6, "ru")
    F.ball(332, 232, 4, "c")
    F.ball(322, 206, 4, "c")
    F.ball(338, 214, 4, "c")
    F.add("</g>")
    F.text(344, 266, "decomposed by water", "ftw", "end")
    F.text(16, 30, "A RACE AGAINST WATER", "fhead", "start")


# --------------------------------------------------------------------------
# Writing the figures into the pages
# --------------------------------------------------------------------------

SIZES = {
    ("can-parking-spots-help-catalysts", 1): (640, 300),
    ("can-parking-spots-help-catalysts", 2): (640, 320),
    ("carbodicarbene-coatings-on-gold", 1): (640, 318),
    ("carbodicarbene-coatings-on-gold", 2): (640, 336),
    ("fluorine-count-on-gold-coatings", 1): (640, 300),
    ("fluorine-count-on-gold-coatings", 2): (640, 310),
    ("forever-chemical-fragment-on-ice", 1): (640, 310),
    ("forever-chemical-fragment-on-ice", 2): (640, 320),
    ("graphite-support-co2-catalyst", 1): (640, 310),
    ("graphite-support-co2-catalyst", 2): (640, 316),
    ("how-tightly-molecules-stick", 1): (640, 314),
    ("how-tightly-molecules-stick", 2): (640, 310),
    ("light-driven-crowded-ethers", 1): (640, 304),
    ("light-driven-crowded-ethers", 2): (640, 310),
    ("missing-oxygen-atoms-reshape-clusters", 1): (640, 318),
    ("missing-oxygen-atoms-reshape-clusters", 2): (640, 320),
    ("perrhenate-acid-deoxydehydration", 1): (640, 296),
    ("perrhenate-acid-deoxydehydration", 2): (640, 316),
    ("quinoxaline-drug-scaffolds", 1): (640, 306),
    ("quinoxaline-drug-scaffolds", 2): (640, 306),
    ("spin-aware-reaction-discovery", 1): (640, 306),
    ("spin-aware-reaction-discovery", 2): (640, 306),
    ("water-and-metathesis-catalysts", 1): (640, 298),
    ("water-and-metathesis-catalysts", 2): (640, 300),
    ("water-on-ten-atom-ruthenium", 1): (640, 316),
    ("water-on-ten-atom-ruthenium", 2): (640, 326),
}

FIG_RE = re.compile(r'<figure class="(?:dir-fig|ex-fig)">\s*<svg.*?</svg>\s*(?:<svg.*?</svg>\s*)?<figcaption>(?:<span class="ex-fig__n">.*?</span>)?(.*?)</figcaption>\s*</figure>', re.S)


def mobile_svg(key, pid, label):
    F = Fig(pid, M, 0, label)
    F.mobile, F.cls = True, "fig-m"
    if key in CUSTOM:
        fn, h = CUSTOM[key]
        F.h = h
        fn(F)
    else:
        w, h = SIZES[key]
        F.w, F.h = w, h
        FIGS[key](F)
        F.label = label
        body = "".join(F.body)
        F.body = []
        stack(F, body, MOBILE[key](F))
    F.label = label
    return F.svg()


def build():
    counter = 0
    for page in sorted({p for p, _ in FIGS}):
        path = EXPLAINED / f"{page}.html"
        html = path.read_text()
        n = 0

        def repl(m):
            nonlocal n, counter
            n += 1
            counter += 1
            w, h = SIZES[(page, n)]
            F = Fig(f"x{counter}", w, h, "")
            FIGS[(page, n)](F)
            cap = m.group(1).strip()
            return (f'<figure class="ex-fig">\n{F.svg()}\n{mobile_svg((page, n), f"x{counter}m", F.label)}\n'
                    f'<figcaption><span class="ex-fig__n">Fig. {n}</span>{cap}</figcaption>\n</figure>')

        new = FIG_RE.sub(repl, html)
        if n != 2:
            raise SystemExit(f"{page}: expected 2 figures, found {n}")
        path.write_text(new)
        print(f"wrote {page}.html")


if __name__ == "__main__":
    build()
