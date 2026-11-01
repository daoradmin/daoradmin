#!/usr/bin/env python3
"""Build the SVG cards in assets/ that make up the profile README.

GitHub strips CSS from READMEs, so the look of danielorelius.dk lives in
SVGs instead. Text is measured with the site's real fonts, which are
subset and embedded per card, so wrapping and highlights line up.

    pip install -r scripts/requirements.txt
    python3 scripts/build.py

Change the copy in the data section below and rebuild.
"""

from __future__ import annotations

import base64
import io
from pathlib import Path
from xml.sax.saxutils import escape

from fontTools import subset
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

ROOT = Path(__file__).resolve().parent
OUT = ROOT.parent / 'assets'

# ── data ─────────────────────────────────────────────────────────────────────

NAME = 'Daniel Orelius'
TITLE = 'Co-Founder & CEO'
COMPANY = 'Entria ApS'
LOCATION = 'Esbjerg, DK'

HEADLINE = ['I take the', 'manual work', 'out of the cloud.']
HIGHLIGHT_LINE = 1
INTRO = (
    'I started as an IT support apprentice in 2017. Ever since, I’ve been doing the same '
    'thing at a bigger scale: taking the manual work out of operations. First in the data '
    'centre, then in Azure, and now in a company of our own.'
)

# ── tokens (danielorelius.dk/src/styles/tokens.css) ─────────────────────────────

PAPER = '#fefefe'
INK = '#1e1e1e'
INK_SOFT = '#3d3d3d'
MUTED = '#666664'
MUTED_ON_INK = '#a8a8a4'
LINE_SOFT = 'rgb(30 30 30 / 0.07)'
ACCENT = '#f386a1'
SIGNAL = '#03aa5c'

W = 840
PAD = 32

FONTS = {
    'sans': ('Schibsted Grotesk', ROOT / 'fonts/schibsted-grotesk-latin-wght-normal.woff2',
             "'Helvetica Neue', Arial, sans-serif"),
    'mono': ('JetBrains Mono', ROOT / 'fonts/jetbrains-mono-wght-normal.woff2',
             "ui-monospace, Menlo, monospace"),
}

# ── fonts ────────────────────────────────────────────────────────────────────

_metrics: dict[tuple[str, int], tuple[dict, dict, int]] = {}


def _instance(family: str, weight: int):
    key = (family, weight)
    if key not in _metrics:
        font = instantiateVariableFont(TTFont(FONTS[family][1]), {'wght': weight})
        _metrics[key] = (font.getBestCmap(), font['hmtx'].metrics, font['head'].unitsPerEm)
    return _metrics[key]


def measure(text: str, family: str, size: float, weight: int = 400, tracking: float = 0) -> float:
    cmap, hmtx, upm = _instance(family, weight)
    units = 0
    for ch in text:
        if ord(ch) not in cmap:
            raise ValueError(f'{FONTS[family][0]} has no glyph for {ch!r}')
        units += hmtx[cmap[ord(ch)]][0]
    return units / upm * size + tracking * size * len(text)


def wrap(text: str, width: float, family: str, size: float, weight: int = 400, tracking: float = 0) -> list[str]:
    lines, line = [], ''
    for word in text.split():
        candidate = f'{line} {word}'.strip()
        if line and measure(candidate, family, size, weight, tracking) > width:
            lines.append(line)
            line = word
        else:
            line = candidate
    return lines + [line] if line else lines


def embedded_font(family: str, chars: set[str]) -> str:
    font = TTFont(FONTS[family][1])
    options = subset.Options()
    options.flavor = 'woff2'
    options.layout_features = ['*']
    subsetter = subset.Subsetter(options)
    subsetter.populate(unicodes={ord(c) for c in chars | {' '}})
    subsetter.subset(font)
    buf = io.BytesIO()
    subset.save_font(font, buf, options)
    data = base64.b64encode(buf.getvalue()).decode()
    return (f"@font-face{{font-family:'{FONTS[family][0]}';font-weight:100 900;"
            f"src:url(data:font/woff2;base64,{data}) format('woff2')}}")


# ── svg ──────────────────────────────────────────────────────────────────────

class Svg:
    def __init__(self, title: str):
        self.title = title
        self.parts: list[str] = []
        self.css: list[str] = []
        self.defs: list[str] = []
        self.chars: dict[str, set[str]] = {'sans': set(), 'mono': set()}

    def add(self, markup: str):
        self.parts.append(markup)

    def text(self, x, y, s, family='sans', size=16, weight=400, fill=INK, tracking=0.0,
             anchor='start', cls='', runs=None):
        """Draw a line of text. `runs` is a list of (text, weight, fill) for mixed styling."""
        runs = runs or [(s, weight, fill)]
        for chunk, _, _ in runs:
            measure(chunk, family, size)  # fails early on a missing glyph
            self.chars[family].update(chunk)
        spans = ''.join(
            f'<tspan font-weight="{w}" fill="{f}">{escape(chunk)}</tspan>' for chunk, w, f in runs
        ) if len(runs) > 1 else escape(runs[0][0])
        attrs = f'class="{(family[0] + " " + cls).strip()}"'
        ls = f' letter-spacing="{tracking * size:.2f}"' if tracking else ''
        self.add(f'<text xml:space="preserve" x="{x:.1f}" y="{y:.1f}" {attrs} font-size="{size}" font-weight="{weight}" '
                 f'fill="{fill}" text-anchor="{anchor}"{ls}>{spans}</text>')

    def label(self, x, y, s, fill=MUTED, anchor='start', runs=None, size=11.5):
        self.text(x, y, s, 'mono', size, 500, fill, 0.05, anchor, runs=runs)

    def render(self, height: float) -> str:
        fonts = ''.join(embedded_font(f, c) for f, c in self.chars.items() if c)
        families = ''.join(
            f".{key[0]}{{font-family:'{name}',{fallback};font-feature-settings:'ss01','cv11'}}"
            for key, (name, _, fallback) in FONTS.items()
        )
        css = fonts + families + ''.join(self.css) + (
            '@media (prefers-reduced-motion:reduce){*{animation:none!important}}'
        )
        h = round(height)
        return (f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
                f'width="{W}" height="{h}" viewBox="0 0 {W} {h}" role="img" aria-label="{escape(self.title)}">'
                f'<title>{escape(self.title)}</title><defs><style>{css}</style>{"".join(self.defs)}</defs>'
                f'{"".join(self.parts)}</svg>\n')


def card(svg: Svg, x, y, w, h, tone='paper'):
    """A window-like surface with the site's hard offset shadow."""
    fill, stroke, shadow = (PAPER, INK, INK) if tone == 'paper' else (INK, PAPER, ACCENT)
    svg.add(f'<rect x="{x + 3.5}" y="{y + 3.5}" width="{w}" height="{h}" fill="{shadow}"/>')
    svg.add(f'<rect x="{x + 0.5}" y="{y + 0.5}" width="{w}" height="{h}" fill="{fill}" stroke="{stroke}"/>')


def window(svg: Svg, x, y, w, h, title, version='1.0', tone='paper'):
    card(svg, x, y, w, h, tone)
    fg, muted = (INK, MUTED) if tone == 'paper' else (PAPER, MUTED_ON_INK)
    svg.add(f'<line x1="{x + 0.5}" y1="{y + 28.5}" x2="{x + w + 0.5}" y2="{y + 28.5}" stroke="{fg}"/>')
    svg.label(x + 12, y + 19, '', runs=[(f'{title} ', 500, fg), (version, 500, muted)])
    for i in range(3):
        cx = x + w - 12 - 9 - (2 - i) * 14
        fill = fg if i == 2 else 'none'
        svg.add(f'<rect x="{cx + 0.5}" y="{y + 10.5}" width="9" height="9" fill="{fill}" stroke="{fg}"/>')
    return y + 29


def highlight(svg: Svg, x, baseline, width, size):
    """The site's .hl marker band, sitting behind a line of display text."""
    svg.add(f'<rect x="{x - 0.08 * size:.1f}" y="{baseline - 0.74 * size:.1f}" '
            f'width="{width + 0.16 * size:.1f}" height="{0.86 * size:.1f}" fill="{ACCENT}"/>')


def display(svg: Svg, x, y, lines, size, fill=INK, highlight_line=None, leading=0.92):
    """Large lowercase-style headline. `y` is the top of the first line; returns the last baseline."""
    tracking = -0.04
    baseline = y + 0.78 * size
    for i, line in enumerate(lines):
        if i == highlight_line:
            highlight(svg, x, baseline, measure(line, 'sans', size, 500, tracking), size)
        svg.text(x, baseline, line, 'sans', size, 500, fill, tracking)
        if i < len(lines) - 1:
            baseline += leading * size
    return baseline


def paragraph(svg: Svg, x, y, text, width, size, fill, leading=1.5, family='sans', weight=400):
    """Wrapped body copy. `y` is the first baseline; returns the y below the block."""
    lines = wrap(text, width, family, size, weight)
    for i, line in enumerate(lines):
        svg.text(x, y + i * size * leading, line, family, size, weight, fill)
    return y + (len(lines) - 1) * size * leading


def grid(svg: Svg, h):
    svg.defs.append(
        f'<pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">'
        f'<path d="M40 0H0V40" fill="none" stroke="{LINE_SOFT}"/></pattern>'
    )
    svg.add(f'<rect x="1" y="1" width="{W - 5}" height="{h - 5}" fill="url(#grid)"/>')


# ── cards ────────────────────────────────────────────────────────────────────

def hero() -> str:
    svg = Svg(f'{NAME} — {TITLE}, {COMPANY}. {" ".join(HEADLINE)} {INTRO}')
    body: list[str] = []
    svg.parts, outer = body, svg.parts  # draw content first, wrap in the card once height is known

    svg.label(PAD, 46, '[00] orelius os 2.0 — github profile')
    svg.label(W - PAD - 4, 46, '', anchor='end',
              runs=[(TITLE, 600, INK), (f' · {COMPANY} · {LOCATION}', 500, INK)])

    # Headline across the full width, then intro on the left and the status window on the right.
    # No portrait: GitHub already shows the avatar right next to the README.
    widest = max(measure(line, 'sans', 1, 500, -0.04) for line in HEADLINE)
    size = min(100, (W - 2 * PAD - 4) / widest)
    last = display(svg, PAD, 84, HEADLINE, size, highlight_line=HIGHLIGHT_LINE)

    y = last + 60
    svg.label(PAD, y, f'Hi, I’m {NAME}.', fill=INK_SOFT, size=12)
    y = paragraph(svg, PAD, y + 32, INTRO, 420, 16.5, INK_SOFT, 1.5)

    sw = 276
    sx, sy = W - PAD - 4 - sw, last + 44
    top = window(svg, sx, sy, sw, 118, 'Status', '1.1')
    svg.label(sx + 14, top + 22, 'europe/copenhagen')
    word = 'building entria'
    svg.text(sx + 14, top + 56, word, 'sans', 30, 500, INK, -0.03)
    cx = sx + 14 + measure(word, 'sans', 30, 500, -0.03) + 5
    svg.css.append('.blink{animation:blink 1.1s steps(1) infinite}@keyframes blink{50%{opacity:0}}')
    svg.add(f'<rect class="blink" x="{cx:.1f}" y="{top + 34}" width="13" height="27" fill="{ACCENT}"/>')
    svg.css.append('.pulse{animation:pulse 2.4s ease-in-out infinite;transform-box:fill-box;transform-origin:center}'
                   '@keyframes pulse{50%{opacity:.35;transform:scale(.7)}}')
    svg.add(f'<circle class="pulse" cx="{sx + 18}" cy="{top + 76}" r="4" fill="{SIGNAL}"/>')
    svg.label(sx + 28, top + 80, 'status: online', fill=INK)

    h = max(y, sy + 118) + 64
    svg.label(W - PAD - 4, h - 30, '↗ full story at danielorelius.dk', anchor='end')

    svg.parts = outer
    card(svg, 0, 0, W - 4, h - 4)
    grid(svg, h)
    svg.parts += body
    return svg.render(h)


def button(text: str, primary=False) -> str:
    svg = Svg(text)
    size = 12.5
    w = measure(text, 'mono', size, 500, 0.02) + 34
    global W
    width, W = W, round(w + 5)
    try:
        card(svg, 0, 0, w, 40, 'paper')
        if primary:
            svg.add(f'<rect x="1" y="1" width="{w - 1}" height="39" fill="{ACCENT}"/>')
        svg.text(17, 25, text, 'mono', size, 500, INK, 0.02)
        return svg.render(45)
    finally:
        W = width


def main():
    OUT.mkdir(exist_ok=True)
    cards = {
        'hero.svg': hero(),
        'btn-linkedin.svg': button('Connect on LinkedIn ↗', primary=True),
        'btn-email.svg': button('Email Daniel'),
        'btn-site.svg': button('danielorelius.dk ↗'),
        'btn-entria.svg': button('entria.io ↗'),
    }
    for name, markup in cards.items():
        (OUT / name).write_text(markup, encoding='utf-8')
        print(f'{name:18} {len(markup.encode()) / 1024:6.1f} KB')


if __name__ == '__main__':
    main()
