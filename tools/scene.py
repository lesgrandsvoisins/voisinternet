"""
Génère l'illustration de l'accueil : une rue de quartier, ses établissements reliés entre eux.
Usage : python tools/scene.py  (réécrit core/templates/core/partials/scene.html)
"""
from pathlib import Path
W, H = 720, 400
SERIF = "\"Lack\", \"Charter\", \"Bitstream Charter\", \"Sitka Text\", Cambria, Georgia, serif"
SERIFFONTWEIGHT = "700"
SERIFFONTSTYLE = "italic"
SANSERIF = "\"Fira Sans\", system-ui, -apple-system, \"Segoe UI\", Roboto, \"Noto Sans\", sans-serif"
out = []
a = out.append

def windows(x, w, top, bottom, cols, rows, lit=(), led=None, ww=14, wh=24):
    """Fenêtres d'étage ; lit = indices allumés ; led = indice de la fenêtre-serveur."""
    gap_x = (w - cols * ww) / (cols + 1)
    gap_y = (bottom - top - rows * wh) / (rows + 1)
    pts = []
    i = 0
    for r in range(rows):
        for c in range(cols):
            wx = x + gap_x + c * (ww + gap_x)
            wy = top + gap_y + r * (wh + gap_y)
            fill = "var(--win-lit)" if i in lit or i == led else "var(--win)"
            a(f'<rect x="{wx:.1f}" y="{wy:.1f}" width="{ww}" height="{wh}" fill="{fill}"/>')
            if i == led:
                pts.append((wx + ww / 2, wy + wh / 2))
            i += 1
    return pts

def mansard(x, w, top, h=28):
    a(f'<polygon points="{x},{top} {x+12},{top-h} {x+w-12},{top-h} {x+w},{top}" fill="var(--zinc)"/>')

def cornice(x, w, top):
    a(f'<rect x="{x-3}" y="{top-6}" width="{w+6}" height="7" fill="var(--zinc)"/>')

def sign(x, w, y, text, size=12, bg="var(--sign-bg)", fg="var(--sun)", h=17):
    a(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="2" fill="{bg}"/>')
    a(f'<text x="{x+w/2}" y="{y+h/2+size*0.36:.1f}" text-anchor="middle" font-family="{SERIF}" '
      f'font-size="{size}" font-weight="{SERIFFONTWEIGHT}" font-style="{SERIFFONTSTYLE}" fill="{fg}">{text}</text>')

def awning(x, w, y, c1, c2, stripes=6):
    a(f'<polygon points="{x+3},{y} {x+w-3},{y} {x+w+3},{y+15} {x-3},{y+15}" fill="{c1}"/>')
    sw = (w + 6) / stripes
    for s in range(1, stripes, 2):
        x0 = x - 3 + s * sw
        a(f'<polygon points="{x0+3-3*(s/stripes):.1f},{y} {x0+sw:.1f},{y} {x0+sw:.1f},{y+15} {x0:.1f},{y+15}" fill="{c2}"/>')

leds = []

# --- soleil et nuage
a('<circle cx="92" cy="70" r="42" fill="var(--sun)"/>')
a('<g class="cloud" fill="var(--cloud)"><circle cx="455" cy="62" r="27"/><circle cx="490" cy="50" r="35"/>'
  '<circle cx="527" cy="66" r="24"/><rect x="428" y="64" width="124" height="26" rx="13"/></g>')

GROUND = 352

# 1. Café
x, w, top = 8, 92, 182
mansard(x, w, top)
a(f'<rect x="{x}" y="{top}" width="{w}" height="{GROUND-top}" fill="var(--stone)"/>')
leds += windows(x, w, top, 268, 3, 2, lit=(0,), led=4)
sign(x+14, w-28, 270, "Café", 13)
awning(x, w, 290, "var(--paper)", "var(--sun)")
a(f'<rect x="{x+8}" y="306" width="{w-16}" height="{GROUND-306}" fill="var(--win)"/>')
for tx in (x+14, x+56):  # terrasse
    a(f'<rect x="{tx}" y="355" width="16" height="3" fill="var(--ink-soft)"/><rect x="{tx+7}" y="357" width="2" height="9" fill="var(--ink-soft)"/>')

# 2. Galerie
x, w, top = 104, 96, 166
cornice(x, w, top)
a(f'<rect x="{x}" y="{top}" width="{w}" height="{GROUND-top}" fill="var(--stone-2)"/>')
leds += windows(x, w, top, 266, 3, 2, lit=(5,), led=1)
sign(x+12, w-24, 270, "Galerie", 12, bg="var(--paper)", fg="var(--ink)")
a(f'<rect x="{x+8}" y="292" width="{w-16}" height="{GROUND-292}" fill="var(--paper)" stroke="var(--zinc)" stroke-width="2"/>')
for fx, col in ((x+16, "var(--sun)"), (x+41, "var(--led)"), (x+66, "var(--zinc)")):
    a(f'<rect x="{fx}" y="306" width="15" height="20" fill="{col}" stroke="var(--ink)" stroke-width="2"/>')

# 3. Théâtre et concerts
x, w, top = 204, 128, 142
a(f'<polygon points="{x-2},{top} {x+w/2},{top-34} {x+w+2},{top}" fill="var(--stone-2)" stroke="var(--zinc)" stroke-width="3"/>')
a(f'<circle cx="{x+w/2}" cy="{top-12}" r="7" fill="var(--zinc)"/>')
a(f'<rect x="{x}" y="{top}" width="{w}" height="{GROUND-top}" fill="var(--stone)"/>')
for i, wx in enumerate((x+18, x+56, x+94)):
    fill = "var(--win-lit)" if i == 1 else "var(--win)"
    a(f'<path d="M{wx} 214 V172 a8 8 0 0 1 16 0 V214 Z" fill="{fill}"/>')
leds.append((x+64, 190))
sign(x+10, w-20, 232, "Théâtre · Concerts", 11, h=19)
for bx in range(x+16, x+w-10, 12):
    a(f'<circle cx="{bx}" cy="258" r="2.2" fill="var(--sun)"/>')
for cx in (x+10, x+w-18):
    a(f'<rect x="{cx}" y="268" width="8" height="{GROUND-268}" fill="var(--stone-2)"/>')
for dx in (x+28, x+56, x+84):
    a(f'<path d="M{dx} {GROUND} V300 a8 8 0 0 1 16 0 V{GROUND} Z" fill="var(--win)"/>')

# 4. Restaurant
x, w, top = 336, 84, 186
mansard(x, w, top)
a(f'<rect x="{x}" y="{top}" width="{w}" height="{GROUND-top}" fill="var(--stone-2)"/>')
leds += windows(x, w, top, 268, 3, 2, lit=(2,), led=3)
sign(x+6, w-12, 270, "Restaurant", 11)
awning(x, w, 290, "var(--led)", "var(--paper)")
a(f'<rect x="{x+8}" y="306" width="{w-16}" height="{GROUND-306}" fill="var(--win-lit)"/>')
a(f'<rect x="{x+34}" y="306" width="16" height="{GROUND-306}" fill="var(--win)"/>')

# 5. Salon de thé
x, w, top = 424, 72, 198
cornice(x, w, top)
a(f'<rect x="{x}" y="{top}" width="{w}" height="{GROUND-top}" fill="var(--stone)"/>')
leds += windows(x, w, top, 232, 2, 1, lit=(0,), led=1, wh=20)
# théière peinte sur la façade
a(f'<g fill="var(--sun)" stroke="var(--ink)" stroke-width="1.5"><ellipse cx="{x+w/2}" cy="252" rx="11" ry="8.5"/>'
  f'<path d="M{x+w/2+10} 250 l8 -7" fill="none"/><path d="M{x+w/2-10} 247 q-7 5 0 10" fill="none"/>'
  f'<circle cx="{x+w/2}" cy="242" r="2.8"/></g>')
sign(x+3, w-6, 270, "Salon de thé", 9.5)
awning(x, w, 290, "var(--paper)", "var(--zinc)", stripes=5)
a(f'<rect x="{x+8}" y="306" width="{w-16}" height="{GROUND-306}" fill="var(--win)"/>')

# 6. Centre social, salle communale
x, w, top = 500, 100, 174
mansard(x, w, top)
a(f'<line x1="{x+w-20}" y1="{top-28}" x2="{x+w-20}" y2="{top-62}" stroke="var(--ink)" stroke-width="2"/>')
a(f'<rect x="{x+w-19}" y="{top-62}" width="8" height="14" fill="#2B4C9B"/>'
  f'<rect x="{x+w-11}" y="{top-62}" width="8" height="14" fill="#FFFFFF"/>'
  f'<rect x="{x+w-3}" y="{top-62}" width="8" height="14" fill="#D23B30"/>')
a(f'<rect x="{x}" y="{top}" width="{w}" height="{GROUND-top}" fill="var(--stone-2)"/>')
leds += windows(x, w, top, 266, 4, 2, lit=(2, 5), led=6, ww=13)
sign(x+10, w-20, 270, "Centre social", 11)
for dx in (x+22, x+54):
    a(f'<rect x="{dx}" y="298" width="24" height="{GROUND-298}" fill="var(--win)"/>')
a(f'<rect x="{x+6}" y="304" width="12" height="18" fill="var(--paper)" stroke="var(--zinc)"/>')

# 7. Atelier d'art
x, w, top = 604, 52, 206
cornice(x, w, top)
a(f'<rect x="{x}" y="{top}" width="{w}" height="{GROUND-top}" fill="var(--stone)"/>')
leds += windows(x, w, top, 264, 2, 1, lit=(), led=1)
sign(x+3, w-6, 270, "Atelier", 10, bg="var(--paper)", fg="var(--ink)")
a(f'<rect x="{x+6}" y="294" width="{w-12}" height="{GROUND-294}" fill="var(--paper)" stroke="var(--zinc)" stroke-width="2"/>')
a(f'<path d="M{x+15} 334 q-6 -10 0 -18 h8 q6 8 0 18 Z" fill="var(--led)"/>'
  f'<path d="M{x+30} 334 q-4 -14 2 -24 h4 q6 10 2 24 Z" fill="var(--sun)"/>')

# 8. Hôpital
x, w, top = 660, 56, 118
cornice(x, w, top)
a(f'<rect x="{x}" y="{top}" width="{w}" height="{GROUND-top}" fill="var(--paper)" stroke="var(--line)"/>')
a(f'<rect x="{x+14}" y="{top+10}" width="28" height="28" rx="4" fill="#2B5FA8"/>'
  f'<text x="{x+28}" y="{top+31}" text-anchor="middle" font-family="{SANSERIF}" font-size="20" font-weight="700" fill="#FFFFFF">H</text>')
leds += windows(x, w, top+44, 292, 2, 4, lit=(1, 4), led=5, ww=12, wh=20)
a(f'<rect x="{x+6}" y="298" width="{w-12}" height="6" fill="var(--zinc)"/>')
a(f'<rect x="{x+14}" y="304" width="28" height="{GROUND-304}" fill="var(--win)"/>')

# --- trottoir et chaussée
a(f'<rect x="0" y="{GROUND}" width="{W}" height="18" fill="var(--stone-2)"/>')
a(f'<rect x="0" y="{GROUND+18}" width="{W}" height="4" fill="var(--zinc)"/>')
a(f'<rect x="0" y="{GROUND+22}" width="{W}" height="{H-GROUND-22}" fill="var(--zinc-dark)"/>')
for lx in range(20, W, 70):
    a(f'<rect x="{lx}" y="386" width="34" height="3" fill="var(--stone-2)" opacity=".6"/>')

# --- passants
for px, col in ((176, "var(--ink-soft)"), (390, "var(--led)"), (575, "var(--zinc)"), (640, "var(--ink-soft)")):
    a(f'<circle cx="{px}" cy="345" r="4.5" fill="{col}"/><rect x="{px-4.5}" y="350" width="9" height="17" rx="4" fill="{col}"/>')

# --- le réseau entre voisins : une fenêtre-serveur par établissement
leds.sort()
poly = " ".join(f"{px:.0f},{py:.0f}" for px, py in leds)
a(f'<polyline class="net" points="{poly}" fill="none" stroke="var(--led)" stroke-width="2.5"/>')
a('<g fill="var(--led)">' + "".join(f'<circle cx="{px:.0f}" cy="{py:.0f}" r="3.8"/>' for px, py in leds) + "</g>")

label = ("Une rue de quartier au soleil : café, galerie, théâtre et salle de concert, restaurant, "
         "salon de thé, centre social, atelier d'art et hôpital, reliés entre eux ; un nuage s'éloigne.")
svg = (f'<svg class="scene" viewBox="0 18 {W} {H-18}" role="img" aria-label="{label}">\n'
       + "\n".join(out) + "\n</svg>\n")
target = Path(__file__).resolve().parent.parent / "core" / "templates" / "core" / "partials" / "scene.html"
target.write_text(svg)
print(len(leds), "établissements reliés;", len(svg), "octets")
