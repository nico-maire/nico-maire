"""Builds the animated SVGs of the profile README (assets/readme/*.svg).

Text is converted to vector paths with the VT323 font of the portfolio, so the SVGs do not depend on
fonts installed on the visitor's machine. Animations use SMIL, which GitHub keeps when an SVG is shown
as an image.

    pip install fonttools brotli
    python3 tools/build_svgs.py [path/to/nico-maire.github.io]
"""
import re
import sys
from pathlib import Path

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parent.parent
PORTFOLIO = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT.parent / 'nico-maire.github.io'
OUT = ROOT / 'assets' / 'readme'

FONT = TTFont(PORTFOLIO / 'assets' / 'fonts' / 'vt323-latin.woff2')
GLYPHS = FONT.getGlyphSet()
CMAP = FONT.getBestCmap()
UPM = FONT['head'].unitsPerEm
ADV = 400 / UPM  # VT323 is monospaced: every glyph advances 0.4 em

PH = '#3cff7a'
PH_HI = '#b9ffd0'
PH_DIM = '#27a653'
PH_DARK = '#0d4220'
BG = '#020a04'
AMBER = '#ffb22e'
SITE = 'nico-maire.github.io'


def num(v):
    return f'{v:.1f}'.rstrip('0').rstrip('.')


def text_path(s, x, y, size):
    """Vector outline of `s` with its baseline at (x, y)."""
    pen = SVGPathPen(GLYPHS, ntos=num)
    k = size / UPM
    for i, ch in enumerate(s):
        name = CMAP.get(ord(ch))
        if name is None:
            raise ValueError(f'VT323 has no glyph for {ch!r}')
        GLYPHS[name].draw(TransformPen(pen, (k, 0, 0, -k, x + i * ADV * size, y)))
    return pen.getCommands()


def width(s, size):
    return len(s) * ADV * size


def pixel_icon(name):
    """Reads a 16x16 bitmap from the portfolio's js/core/icons.js."""
    src = (PORTFOLIO / 'js' / 'core' / 'icons.js').read_text()
    block = re.search(rf"\n  {name}: \[(.*?)\],", src, re.S).group(1)
    return re.findall(r"'([.#+]{16})'", block)


def icon_paths(rows, x, y, px):
    full, dim = [], []
    for j, row in enumerate(rows):
        i = 0
        while i < 16:
            ch = row[i]
            if ch == '.':
                i += 1
                continue
            end = i + 1
            while end < 16 and row[end] == ch:
                end += 1
            seg = f'M{num(x + i * px)} {num(y + j * px)}h{num((end - i) * px)}v{num(px)}h{num(-(end - i) * px)}z'
            (full if ch == '#' else dim).append(seg)
            i = end
    return ''.join(full), ''.join(dim)


def steps(n, unit):
    return ';'.join(num(i * unit) for i in range(n + 1))


GLOW = '''<filter id="glow" x="-10%" y="-30%" width="120%" height="160%">
      <feGaussianBlur stdDeviation="{d}" result="b"/>
      <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>'''

SCANLINES = '''<pattern id="scan" width="4" height="3" patternUnits="userSpaceOnUse">
      <rect width="4" height="1" fill="#000" opacity=".38"/>
    </pattern>'''


# --------------------------------------------------------------------------------------------- hero
def hero():
    W, H = 1000, 400
    sx, sy, sw, sh = 30, 26, 940, 312
    left = 64
    T = []  # timeline items appended as SVG strings
    cursor = []  # (time, x, baseline, size): where the block cursor sits from `time` on

    def instant(s, x, y, size, t, fill=PH, extra=''):
        T.append(f'<path d="{text_path(s, x, y, size)}" fill="{fill}" opacity="0"{extra}>'
                 f'<set attributeName="opacity" to="1" begin="{t}s" fill="freeze"/></path>')

    def typed(s, x, y, size, t, per, fill=PH, cid=None):
        cid = cid or f'c{len(T)}'
        unit = ADV * size
        dur = per * (len(s) + 1)
        T.append(
            f'<clipPath id="{cid}"><rect x="{num(x)}" y="{num(y - size)}" height="{num(size * 1.3)}" width="0">'
            f'<animate attributeName="width" values="{steps(len(s), unit)}" calcMode="discrete" '
            f'dur="{dur:.2f}s" begin="{t}s" fill="freeze"/></rect></clipPath>'
            f'<path d="{text_path(s, x, y, size)}" fill="{fill}" clip-path="url(#{cid})"/>')
        for i in range(len(s) + 1):
            cursor.append((t + per * i, x + unit * i, y, size))
        return t + dur

    # BIOS header and status
    instant('NicBIOS v2.6   (C) 1987-2026 Maire Bravo Technologies', left, 68, 19, 0.2, PH_DIM)
    status = 'OPEN TO WORK'
    sx_status = sx + sw - 34 - width(status, 19)
    instant(status, sx_status, 68, 19, 0.2, AMBER)
    T.append(f'<rect x="{num(sx_status - 18)}" y="56" width="10" height="10" fill="{AMBER}" opacity="0">'
             f'<set attributeName="opacity" to="1" begin="0.2s" fill="freeze"/>'
             f'<animate attributeName="fill-opacity" values="1;.15;1" dur="1.6s" begin="0.2s" repeatCount="indefinite"/></rect>')

    prompt = 'C:\\> '
    p = width(prompt, 24)
    instant(prompt, left, 108, 24, 0.5)
    cursor.append((0.0, left, 108, 24))
    t = typed('whoami', left + p, 108, 24, 0.75, 0.09)
    t = typed('Nicolás Maire Bravo', left, 166, 60, t + 0.2, 0.045, PH_HI)
    t += 0.15
    instant('CS @ UC3M · AI & Cybersecurity · Full-stack · Founder of CitaSalon', left, 204, 24, t, PH)
    t += 0.35
    instant(prompt, left, 246, 24, t)
    cursor.append((t, left + p, 246, 24))
    t = typed('boot nicos.exe', left + p, 246, 24, t + 0.25, 0.07)

    # Loading bar: 24 blocks filled in steps
    bx, by, blocks, bw = left + width('LOADING ', 24), 230, 24, 13
    instant('LOADING', left, 280, 24, t + 0.1, PH_DIM)
    T.append(f'<rect x="{num(bx)}" y="{by + 30}" width="{blocks * bw + 6}" height="24" fill="none" stroke="{PH_DIM}" stroke-width="2" opacity="0">'
             f'<set attributeName="opacity" to="1" begin="{t + 0.1:.2f}s" fill="freeze"/></rect>')
    T.append(f'<clipPath id="bar"><rect x="{num(bx)}" y="{by + 30}" height="24" width="0">'
             f'<animate attributeName="width" values="{steps(blocks, bw)}" calcMode="discrete" dur="1.1s" begin="{t + 0.15:.2f}s" fill="freeze"/></rect></clipPath>')
    T.append(f'<g clip-path="url(#bar)" fill="{PH}">' + ''.join(
        f'<rect x="{num(bx + 4 + i * bw)}" y="{by + 34}" width="{bw - 3}" height="16"/>' for i in range(blocks)) + '</g>')
    t += 0.15 + 1.1
    instant('100%  OK', bx + blocks * bw + 18, 280, 24, t, PH)
    cursor.append((t, -100, 280, 24))  # hide the cursor while the bar loads

    # Call to action
    t += 0.3
    cta = 'This profile is a 1980s computer. Click to power it on'
    arrow_x, arrow_y = left, 324
    T.append(f'<path d="M{left} {arrow_y - 20}l16 10l-16 10z" fill="{PH_HI}" opacity="0">'
             f'<set attributeName="opacity" to="1" begin="{t:.2f}s" fill="freeze"/></path>')
    t_end = typed(cta, left + 28, arrow_y, 30, t, 0.03, PH_HI)

    # Big pulsing power symbol on the right
    rows = pixel_icon('power')
    full, dim = icon_paths(rows, 0, 0, 7)
    T.append(f'<g transform="translate({sx + sw - 34 - 112} 96)">'
             f'<g filter="url(#glow2)"><path d="{dim}" fill="{PH}" opacity=".38"/><path d="{full}" fill="{PH}"/></g>'
             f'<animate attributeName="opacity" values=".45;1;.45" dur="1.8s" begin="{t_end:.2f}s" repeatCount="indefinite"/>'
             f'<set attributeName="opacity" to=".35" begin="0s"/></g>')

    # Block cursor following the typing, blinking forever
    cursor.sort(key=lambda c: c[0])
    total = t_end + 0.01
    times = [c[0] / total for c in cursor] + [1]
    xs = [c[1] for c in cursor] + [left + 28 + width(cta, 30)]
    ys = [c[2] - c[3] * 0.62 for c in cursor] + [arrow_y - 30 * 0.62]
    hs = [c[3] * 0.72 for c in cursor] + [30 * 0.72]
    ws = [c[3] * ADV for c in cursor] + [30 * ADV]
    kt = ';'.join(f'{v:.4f}' for v in times)
    anim = ''.join(
        f'<animate attributeName="{a}" values="{";".join(num(v) for v in vals)}" keyTimes="{kt}" calcMode="discrete" dur="{total:.2f}s" fill="freeze"/>'
        for a, vals in (('x', xs), ('y', ys), ('height', hs), ('width', ws)))
    T.append(f'<rect x="{num(xs[0])}" y="{num(ys[0])}" width="{num(ws[0])}" height="{num(hs[0])}" fill="{PH}">{anim}'
             f'<animate attributeName="opacity" values="1;0" dur="1s" calcMode="discrete" repeatCount="indefinite"/></rect>')

    led = f'''<circle cx="{W - 62}" cy="370" r="6" fill="#1aff5e">
      <animate attributeName="opacity" values="1;.35;1" dur="2.4s" repeatCount="indefinite"/></circle>
    <circle cx="{W - 62}" cy="370" r="13" fill="#1aff5e" opacity=".18"/>'''
    label = text_path('NicOS', 54, 382, 30)
    model = text_path('"Your idea. Your code. Your reality."', 150, 379, 19)

    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-labelledby="t d">
  <title id="t">NicOS · Nicolás Maire Bravo</title>
  <desc id="d">A retro computer screen: Nicolás Maire Bravo, Computer Science student at UC3M, AI and cybersecurity, full-stack developer and founder of CitaSalon. Open to work. Click to power on the interactive portfolio.</desc>
  <defs>
    <linearGradient id="case" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#e6dcc0"/><stop offset=".55" stop-color="#d6caa6"/><stop offset="1" stop-color="#bcae86"/>
    </linearGradient>
    <radialGradient id="glass" cx=".5" cy=".45" r=".75">
      <stop offset="0" stop-color="#0b2414"/><stop offset=".7" stop-color="#04110a"/><stop offset="1" stop-color="#010503"/>
    </radialGradient>
    <radialGradient id="vignette" cx=".5" cy=".5" r=".72">
      <stop offset=".62" stop-color="#000" stop-opacity="0"/><stop offset="1" stop-color="#000" stop-opacity=".65"/>
    </radialGradient>
    <linearGradient id="band" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="{PH}" stop-opacity="0"/><stop offset=".5" stop-color="{PH}" stop-opacity=".07"/><stop offset="1" stop-color="{PH}" stop-opacity="0"/>
    </linearGradient>
    <clipPath id="screen"><rect x="{sx}" y="{sy}" width="{sw}" height="{sh}" rx="24"/></clipPath>
    {SCANLINES}
    {GLOW.format(d=2.2)}
    {GLOW.replace('id="glow"', 'id="glow2"').format(d=6)}
  </defs>
  <rect width="{W}" height="{H}" rx="28" fill="url(#case)"/>
  <rect x="2" y="2" width="{W - 4}" height="{H - 4}" rx="26" fill="none" stroke="#f4ecd6" stroke-opacity=".7" stroke-width="2"/>
  <rect x="{sx - 10}" y="{sy - 10}" width="{sw + 20}" height="{sh + 20}" rx="32" fill="#8f835f"/>
  <rect x="{sx - 6}" y="{sy - 6}" width="{sw + 12}" height="{sh + 12}" rx="28" fill="#1c1a14"/>
  <g clip-path="url(#screen)">
    <rect x="{sx}" y="{sy}" width="{sw}" height="{sh}" fill="url(#glass)"/>
    <g filter="url(#glow)">
      <animate attributeName="opacity" values="1;1;.86;1;1;.93;1" keyTimes="0;.42;.43;.45;.8;.81;1" dur="7s" repeatCount="indefinite"/>
      {''.join(T)}
    </g>
    <rect x="{sx}" y="{sy}" width="{sw}" height="80" fill="url(#band)">
      <animate attributeName="y" values="{sy - 80};{sy + sh}" dur="6s" repeatCount="indefinite"/>
    </rect>
    <rect x="{sx}" y="{sy}" width="{sw}" height="{sh}" fill="url(#scan)"/>
    <rect x="{sx}" y="{sy}" width="{sw}" height="{sh}" fill="url(#vignette)"/>
  </g>
  <path d="{label}" fill="#7d7152"/>
  <path d="{model}" fill="#8f835f"/>
  <g fill="#a99b74">{''.join(f'<rect x="{W - 300 + i * 14}" y="362" width="8" height="18" rx="2"/>' for i in range(12))}</g>
  {led}
</svg>
'''


# ------------------------------------------------------------------------------------- boot button
def button():
    W, H = 600, 132
    title = 'PRESS POWER  >  ENTER NicOS'
    size = 36
    tx = 128
    full, dim = icon_paths(pixel_icon('power'), 30, 30, 4.5)
    tw = width(title, size)
    sub = f'{SITE} · desktop & mobile · 5 languages'
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-labelledby="t">
  <title id="t">Press power: enter NicOS at {SITE}</title>
  <defs>
    {SCANLINES}
    {GLOW.format(d=2)}
    <filter id="halo" x="-20%" y="-40%" width="140%" height="180%"><feGaussianBlur stdDeviation="7"/></filter>
  </defs>
  <rect x="8" y="8" width="{W - 16}" height="{H - 16}" rx="14" fill="{PH}" filter="url(#halo)" opacity=".35">
    <animate attributeName="opacity" values=".12;.5;.12" dur="1.8s" repeatCount="indefinite"/>
  </rect>
  <rect x="8" y="8" width="{W - 16}" height="{H - 16}" rx="14" fill="{BG}"/>
  <rect x="8" y="8" width="{W - 16}" height="{H - 16}" rx="14" fill="none" stroke="{PH}" stroke-width="3"/>
  <rect x="16" y="16" width="{W - 32}" height="{H - 32}" rx="9" fill="none" stroke="{PH_DIM}" stroke-width="1.5"/>
  <g filter="url(#glow)">
    <g><path d="{dim}" fill="{PH}" opacity=".38"/><path d="{full}" fill="{PH}"/>
      <animate attributeName="opacity" values="1;.35;1" dur="1.8s" repeatCount="indefinite"/></g>
    <path d="{text_path(title, tx, 70, size)}" fill="{PH_HI}"/>
    <rect x="{num(tx + tw + 4)}" y="{num(70 - size * .62)}" width="{num(size * ADV)}" height="{num(size * .72)}" fill="{PH}">
      <animate attributeName="opacity" values="1;0" dur="1s" calcMode="discrete" repeatCount="indefinite"/></rect>
    <path d="{text_path(sub, tx, 102, 19)}" fill="{PH_DIM}"/>
  </g>
  <rect x="16" y="16" width="{W - 32}" height="{H - 32}" rx="9" fill="url(#scan)"/>
</svg>
'''


# ------------------------------------------------------------------------------------ desktop icons
TILES = [
    ('projects', 'folder', 'PROJECTS'),
    ('skills', 'chip', 'SKILLS'),
    ('terminal', 'terminal', 'TERMINAL.EXE'),
    ('cv', 'disk', 'CV.PDF'),
    ('contact', 'mail', 'CONTACT.EXE'),
]


def tile(icon, label, delay):
    W, H = 132, 128
    full, dim = icon_paths(pixel_icon(icon), (W - 64) / 2, 16, 4)
    size = 21
    lx = (W - width(label, size)) / 2
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-labelledby="t">
  <title id="t">{label}</title>
  <defs>{SCANLINES}{GLOW.format(d=1.6)}</defs>
  <rect x="3" y="3" width="{W - 6}" height="{H - 6}" rx="12" fill="{BG}" stroke="{PH_DARK}" stroke-width="2"/>
  <g filter="url(#glow)">
    <path d="{dim}" fill="{PH}" opacity=".38"/><path d="{full}" fill="{PH}"/>
    <path d="{text_path(label, lx, 106, size)}" fill="{PH}"/>
  </g>
  <g opacity="0">
    <animate attributeName="opacity" values="0;0;1;1;0;0" keyTimes="0;{delay:.2f};{delay + .01:.2f};{delay + .14:.2f};{delay + .15:.2f};1" dur="7s" repeatCount="indefinite"/>
    <rect x="{num(lx - 5)}" y="88" width="{num(width(label, size) + 10)}" height="24" fill="{PH}"/>
    <path d="{text_path(label, lx, 106, size)}" fill="{BG}"/>
  </g>
  <rect x="3" y="3" width="{W - 6}" height="{H - 6}" rx="12" fill="url(#scan)"/>
</svg>
'''


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'hero.svg').write_text(hero())
    (OUT / 'boot-button.svg').write_text(button())
    for i, (node, icon, label) in enumerate(TILES):
        (OUT / f'icon-{node}.svg').write_text(tile(icon, label, 0.05 + i * 0.17))
    for f in sorted(OUT.glob('*.svg')):
        print(f'{f.name:22} {f.stat().st_size / 1024:6.1f} KB')


if __name__ == '__main__':
    main()
