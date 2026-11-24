#!/usr/bin/env python3
"""Export and lint a paper diagram drawn in draw.io.

    python3 build.py FIG.drawio [--width 3.33in] [--outdir DIR] [--dpi 300]

Exports page 1 of FIG.drawio with the draw.io desktop CLI to FIG.pdf (vector,
cropped, fonts embedded) and FIG.png (preview) in --outdir (default: next to
FIG.drawio), then checks:
  fonts       only Roboto / Roboto Mono, embedded as TrueType (never Type 3)
  style       house-style tokens in the XML: fonts, palette, no shadow/rounding/gradient
  steps       step badges are numbered 1..N, each once
  brief       FIG.brief.md (next to FIG.drawio) has its required sections, and
              its numbered Steps are exactly the badges (warning if absent)
  arrows      arrowheads land on an edge, clear of corners and cell dividers
  collisions  no glyph within CLEAR_PT of a solid/dashed line or border
  overlaps    no two horizontal words overlap (text on text)
  size        with --width: natural width <= 1.05 x width, smallest text >= MIN_PT
  groups      (warning) a column title left outside its column's group
Exit status: 0 = every check passes (WARN lines allowed), 1 = export failed,
2 = a check failed.

Geometry: draw.io exports 100 px per inch, so 1 px = 0.72 pt at print size.
Needs the draw.io desktop app (`drawio` on PATH, or the macOS app bundle) and
poppler (pdfinfo, pdffonts, pdftotext, pdftoppm). Standard library only.
"""
import argparse
import base64
import html
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.parse
import xml.etree.ElementTree as ET
import zlib

PT_PER_PX = 0.72
MIN_PT = 7.0           # smallest legible text at print size
CLEAR_PT = 1.0         # required gap between a glyph and a dark line
LINT_DPI = 200
CORNER_PX = 4          # an arrow end closer than this to a corner reads as "on the corner"
PALETTE = {"#CAEAFA", "#B5372B", "#DF7530", "#E4E4E4", "#FFFFFF"}
HOUSE_PX = {10.5, 11, 14}  # badge digit, body, header
FONTS = {"roboto", "roboto mono"}
SENTINEL = "#00FF00"   # dotted boundaries are drawn in this colour for the lint renders
DRAWIO_CANDIDATES = ["drawio", "draw.io", "/Applications/draw.io.app/Contents/MacOS/draw.io"]
UNITS = {"pt": 72 / 72.27, "bp": 1.0, "in": 72.0, "cm": 72 / 2.54, "mm": 72 / 25.4, "px": PT_PER_PX}


def to_bp(s):
    m = re.fullmatch(r"\s*([0-9.]+)\s*(pt|bp|in|cm|mm|px)\s*", s)
    if not m:
        sys.exit(f"--width: cannot parse {s!r}; use e.g. 3.33in, 241pt, 8.5cm")
    return float(m.group(1)) * UNITS[m.group(2)]


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


# ---------------------------------------------------------------- drawio model

class Cell:
    """One mxCell (possibly wrapped in <UserObject>/<object>)."""

    def __init__(self, el, wrapper=None):
        self.el, self.wrapper = el, wrapper
        holder = wrapper if wrapper is not None else el
        self.id = holder.get("id", "")
        self.value = holder.get("label" if wrapper is not None else "value", "") or ""
        self.parent = el.get("parent")
        self.vertex = el.get("vertex") == "1"
        self.edge = el.get("edge") == "1"
        self.source, self.target = el.get("source"), el.get("target")
        self.style = parse_style(el.get("style", ""))
        g = el.find("mxGeometry")
        self.geo = {k: float(g.get(k, 0)) for k in ("x", "y", "width", "height")} if g is not None else None
        self.relative = g is not None and g.get("relative") == "1"

    def get(self, key, default=None):
        return self.style.get(key, default)

    def set(self, key, val):
        self.style[key] = val
        self.el.set("style", ";".join(k if v is None else f"{k}={v}" for k, v in self.style.items()) + ";")

    def text(self):
        return re.sub(r"<[^>]+>", " ", self.value).strip()


def parse_style(s):
    out = {}
    for tok in s.split(";"):
        tok = tok.strip()
        if not tok:
            continue
        k, eq, v = tok.partition("=")
        out[k] = v if eq else None
    return out


def load(path):
    tree = ET.parse(path)
    root = tree.getroot()
    diagrams = root.findall("diagram") if root.tag == "mxfile" else []
    if root.tag == "mxGraphModel":
        model = root
    else:
        if not diagrams:
            sys.exit(f"FAIL export: {path} is not a draw.io file (no <diagram>)")
        d = diagrams[0]
        model = d.find("mxGraphModel")
        if model is None:  # compressed page: base64(deflateRaw(encodeURIComponent(xml)))
            raw = zlib.decompress(base64.b64decode((d.text or "").strip()), -15).decode()
            model = ET.fromstring(urllib.parse.unquote(raw))
            d.text = None
            d.append(model)
        for extra in diagrams[1:]:  # export page 1 only; keep variants small
            root.remove(extra)
    cells = []
    for el in model.find("root"):
        if el.tag == "mxCell":
            cells.append(Cell(el))
        elif el.tag in ("UserObject", "object") and el.find("mxCell") is not None:
            cells.append(Cell(el.find("mxCell"), el))
    return tree, cells, len(diagrams)


def is_dotted(c):
    if c.get("dashed") != "1":
        return False
    pat = (c.get("dashPattern") or "").split()
    return bool(pat) and float(pat[0]) <= 1.5


def badges(c):
    """Step numbers in this cell: inline circle spans, or a small ellipse vertex."""
    nums = re.findall(r"<span[^>]*border-radius:\s*50%[^>]*>\s*(\d+)\s*</span>", c.value)
    if not nums and c.vertex and "ellipse" in c.style and c.geo and c.geo["width"] <= 18 and c.text().isdigit():
        nums = [c.text()]
    return [int(n) for n in nums]


def font_sizes_px(c):
    sizes = []
    if c.text():
        sizes.append(float(c.get("fontSize") or 11))
    sizes += [float(x) for x in re.findall(r"font-size:\s*([\d.]+)px", c.value)]
    return sizes


# ---------------------------------------------------------------- lint variants

def write_variants(path, tmp, stem):
    """Main copy plus three lint renders, all exported in one draw.io run."""
    os.makedirs(os.path.join(tmp, "in"))
    shutil.copy(path, os.path.join(tmp, "in", stem + ".drawio"))

    def variant(suffix, edit):
        tree, cells, _ = load(path)
        ids = {c.id: c for c in cells}
        for c in cells:
            edit(c, ids)
        tree.write(os.path.join(tmp, "in", f"{stem}-{suffix}.drawio"), encoding="unicode")

    def lint(c, ids):
        if c.get("labelBackgroundColor") not in (None, "none"):
            c.set("labelBackgroundColor", "none")
        if c.get("labelBorderColor") not in (None, "none"):
            c.set("labelBorderColor", "none")
        if is_dotted(c):
            c.set("strokeColor", SENTINEL)

    def notext(c, ids):
        lint(c, ids)
        c.set("textOpacity", "0")
        if badges(c) and not c.value.count("<span"):
            c.set("opacity", "0")  # ellipse badge: its ring counts as text

    def rotated(c, ids):
        while c is not None:
            if float(c.get("rotation") or 0) % 360 or c.get("horizontal") == "0":
                return True
            c = ids.get(c.parent)
        return False

    def flat(c, ids):  # hide sloped text, so pdftotext sees only horizontal words
        if rotated(c, ids):
            c.set("textOpacity", "0")

    variant("lint", lint)
    variant("lint-notext", notext)
    variant("flat", flat)


def drawio_bin():
    for c in DRAWIO_CANDIDATES:
        p = shutil.which(c) or (c if os.path.isfile(c) else None)
        if p:
            return p
    sys.exit("FAIL export: draw.io desktop not found. Install it (macOS: brew install --cask drawio; "
             "Linux: the .deb/AppImage from github.com/jgraph/drawio-desktop, run under xvfb-run).")


def export(tmp):
    os.makedirs(os.path.join(tmp, "out"), exist_ok=True)
    r = run([drawio_bin(), "-x", "-f", "pdf", "--crop", "-p", "1", "--theme", "light",
             "-o", os.path.join(tmp, "out"), os.path.join(tmp, "in")], timeout=300)
    noise = re.compile(r"mach_port|shared_memory|sandbox_extension|^\S+ -> \S+$")
    msgs = [l for l in (r.stdout + r.stderr).splitlines() if l.strip() and not noise.search(l)]
    missing = [f for f in os.listdir(os.path.join(tmp, "in"))
               if not os.path.exists(os.path.join(tmp, "out", f[:-len(".drawio")] + ".pdf"))]
    if r.returncode != 0 or missing:
        print(f"FAIL export: draw.io exited {r.returncode}; missing {', '.join(missing) or 'nothing'}")
        print("\n".join(msgs[-30:]))
        sys.exit(1)


# ---------------------------------------------------------------- pixel checks

def read_ppm(path):
    data = open(path, "rb").read()
    tokens, pos = [], 0
    while len(tokens) < 4:
        while data[pos:pos + 1].isspace():
            pos += 1
        if data[pos:pos + 1] == b"#":
            pos = data.index(b"\n", pos)
            continue
        start = pos
        while not data[pos:pos + 1].isspace():
            pos += 1
        tokens.append(data[start:pos])
    assert tokens[0] == b"P6", "expected binary PPM"
    return int(tokens[1]), int(tokens[2]), data[pos + 1:]


def render_ppm(pdf, tmp, stem):
    out = os.path.join(tmp, stem)
    run(["pdftoppm", "-r", str(LINT_DPI), "-singlefile", pdf, out], check=True)
    return read_ppm(out + ".ppm")


def words(pdf):
    out = run(["pdftotext", "-bbox", pdf, "-"]).stdout
    pat = r'<word xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)">(.*?)</word>'
    return [(float(a), float(b), float(c), float(d), t) for a, b, c, d, t in re.findall(pat, out)]


def collisions(full_pdf, bare_pdf, tmp, wordlist):
    w1, h1, full = render_ppm(full_pdf, tmp, "lint-full")
    w2, h2, bare = render_ppm(bare_pdf, tmp, "lint-bare")
    if (w1, h1) != (w2, h2):
        return [f"lint skipped: text-free render has a different size ({w2}x{h2} vs {w1}x{h1})"]
    W, H = w1, h1
    text = bytearray(W * H)
    for i in range(W * H):
        j = 3 * i
        if abs(full[j] - bare[j]) + abs(full[j + 1] - bare[j + 1]) + abs(full[j + 2] - bare[j + 2]) > 90:
            text[i] = 1
    r = max(1, round(CLEAR_PT * LINT_DPI / 72))
    hits = set()
    for i in range(W * H):
        if not text[i]:
            continue
        y, x = divmod(i, W)
        for yy in range(max(0, y - r), min(H, y + r + 1)):
            for xx in range(max(0, x - r), min(W, x + r + 1)):
                k = yy * W + xx
                if not text[k] and max(bare[3 * k], bare[3 * k + 1], bare[3 * k + 2]) < 100:
                    hits.add((xx, yy))
    px2bp = 72 / LINT_DPI
    seen, blobs = set(), []
    for p in sorted(hits):
        if p in seen:
            continue
        stack, blob = [p], []
        seen.add(p)
        while stack:
            cx, cy = stack.pop()
            blob.append((cx, cy))
            for dx in (-2, -1, 0, 1, 2):
                for dy in (-2, -1, 0, 1, 2):
                    q = (cx + dx, cy + dy)
                    if q in hits and q not in seen:
                        seen.add(q)
                        stack.append(q)
        if len(blob) < 3:
            continue
        bx = sum(b[0] for b in blob) / len(blob) * px2bp
        by = sum(b[1] for b in blob) / len(blob) * px2bp
        near = min(wordlist, key=lambda wd: max(wd[0] - bx, 0, bx - wd[2]) + max(wd[1] - by, 0, by - wd[3]),
                   default=None)
        where = f"({bx / PT_PER_PX:.0f}, {by / PT_PER_PX:.0f}) px from the figure's top-left"
        blobs.append(f"text touches a line at {where}" + (f", near {near[4]!r}" if near else ""))
    return blobs


def overlaps(wordlist):
    """Horizontal words whose boxes overlap by more than the ascender/descender
    slack that consecutive lines of one label share (word boxes span the font's
    full ascent + descent, so stacked lines may touch without any ink meeting)."""
    out = []
    for i, a in enumerate(wordlist):
        for b in wordlist[i + 1:]:
            ix = min(a[2], b[2]) - max(a[0], b[0])
            iy = min(a[3], b[3]) - max(a[1], b[1])
            if ix > 0.5 and iy > 0.25 * min(a[3] - a[1], b[3] - b[1]):
                out.append(f"{a[4]!r} and {b[4]!r} overlap near "
                           f"({max(a[0], b[0]) / PT_PER_PX:.0f}, {max(a[1], b[1]) / PT_PER_PX:.0f}) px")
    return out


# ---------------------------------------------------------------- model checks

def style_check(cells):
    probs = []
    for c in cells:
        if c.id in ("0", "1") or "group" in c.style:
            continue
        tag = f"{c.id!r}"
        if c.text():
            fam = (c.get("fontFamily") or "Helvetica").lower()
            if fam not in FONTS:
                probs.append(f"{tag}: fontFamily={c.get('fontFamily') or '(default Helvetica)'}")
        for face in re.findall(r'(?:face="|font-family:\s*)([^";]+)', html.unescape(c.value)):
            if face.strip().strip("'").lower() not in FONTS:
                probs.append(f"{tag}: inline font {face.strip()!r}")
        for key in ("fillColor", "gradientColor"):
            v = c.get(key)
            if v and v.lower() not in ("none", "default") and v.upper() not in PALETTE:
                probs.append(f"{tag}: {key}={v} is not in the palette")
        if c.get("gradientColor") not in (None, "none"):
            probs.append(f"{tag}: gradient")
        for key in ("strokeColor", "fontColor"):
            v = c.get(key)
            if v and v.lower() not in ("none", "default", "#000000", "#000"):
                probs.append(f"{tag}: {key}={v} (lines and text are black)")
        for key in ("shadow", "glass", "sketch"):
            if c.get(key) == "1":
                probs.append(f"{tag}: {key}=1")
        if c.vertex and c.get("rounded") == "1":
            probs.append(f"{tag}: rounded corners")
    return probs


def abs_box(c, ids):
    """(x0, y0, x1, y1) in page px, adding the offsets of enclosing groups; None for edge labels."""
    if c.geo is None or c.relative:
        return None
    x, y = c.geo["x"], c.geo["y"]
    p = ids.get(c.parent)
    while p is not None and p.geo is not None and not p.relative:
        x, y = x + p.geo["x"], y + p.geo["y"]
        p = ids.get(p.parent)
    return x, y, x + c.geo["width"], y + c.geo["height"]


def stranded_titles(cells):
    """Text that sits just above a group (a column title) but is not part of it."""
    ids = {c.id: c for c in cells}
    groups = [(g, abs_box(g, ids)) for g in cells if g.vertex and "group" in g.style]
    out = []
    for t in cells:
        if not (t.vertex and "text" in t.style and t.text()) or "group" in t.style:
            continue
        tb = abs_box(t, ids)
        for g, gb in groups:
            if tb is None or gb is None or t.parent == g.id or ids.get(t.parent) is g:
                continue
            overlap = min(tb[2], gb[2]) - max(tb[0], gb[0])
            if overlap > 0.5 * (tb[2] - tb[0]) and gb[1] - 14 <= tb[3] <= gb[1] + 2:
                out.append(f"{t.id!r} sits on top of group {g.id!r} but is not in it; "
                           f"dragging the column leaves it behind")
    return out


def extents(cells):
    ids = {c.id: c for c in cells}
    boxes = [(c.id, abs_box(c, ids)) for c in cells if c.vertex and "group" not in c.style]
    boxes = [(i, b) for i, b in boxes if b]
    if not boxes:
        return ""
    left = min(boxes, key=lambda ib: ib[1][0])
    right = max(boxes, key=lambda ib: ib[1][2])
    return (f"left edge set by {left[0]!r} (x={left[1][0]:g}), right edge by {right[0]!r} "
            f"(x={right[1][2]:g}); a text cell counts with its whole box, not just its ink")


def steps_check(cells):
    nums = sorted(n for c in cells for n in badges(c))
    if not nums:
        return None, []
    want = list(range(1, nums[-1] + 1))
    probs = []
    dup = sorted({n for n in nums if nums.count(n) > 1})
    gaps = sorted(set(want) - set(nums))
    if dup:
        probs.append("used more than once: " + ", ".join(map(str, dup)))
    if gaps:
        probs.append("missing: " + ", ".join(map(str, gaps)))
    return nums[-1], probs


BRIEF_SECTIONS = ("Message", "Reading order", "Elements", "Steps", "Caption")


def brief_check(path, top):
    """FIG.brief.md: required '## ' sections present and non-empty, and its top-level
    numbered Steps list is exactly 1..top (empty when the figure has no badges)."""
    secs, cur = {}, None
    with open(path, encoding="utf-8") as f:
        for line in f:
            m = re.match(r"##\s+(.+?)\s*$", line)
            if m:
                cur = m.group(1).strip().lower()
                secs[cur] = []
            elif cur is not None:
                secs[cur].append(line.rstrip("\n"))
    probs = [f"section '## {s}' is missing or empty" for s in BRIEF_SECTIONS
             if not "\n".join(secs.get(s.lower(), [])).strip()]
    steps = [int(m.group(1)) for l in secs.get("steps", []) for m in [re.match(r"(\d+)\.\s", l)] if m]
    want = list(range(1, (top or 0) + 1))
    span = lambda xs: "none" if not xs else (f"1..{xs[-1]}" if xs == list(range(1, len(xs) + 1))
                                              else ", ".join(map(str, xs)))
    if steps != want:
        probs.append(f"the brief lists steps {span(steps)} but the figure has badges {span(want)}; "
                     f"bring whichever is out of date in line (after a hand edit, the figure wins)")
    return probs, len(steps)


def arrows_check(cells):
    ids = {c.id: c for c in cells}
    fails, floating, dangling = [], [], []

    def dividers(t):
        """Sides of t that it shares with an abutting sibling (cell dividers)."""
        sides, g = set(), t.geo
        for s in cells:
            if s is t or s.parent != t.parent or not s.vertex or s.geo is None or s.relative:
                continue
            h = s.geo
            xo = min(g["x"] + g["width"], h["x"] + h["width"]) - max(g["x"], h["x"]) > 1
            yo = min(g["y"] + g["height"], h["y"] + h["height"]) - max(g["y"], h["y"]) > 1
            if xo and abs(h["y"] + h["height"] - g["y"]) < 1:
                sides.add("top")
            if xo and abs(g["y"] + g["height"] - h["y"]) < 1:
                sides.add("bottom")
            if yo and abs(h["x"] + h["width"] - g["x"]) < 1:
                sides.add("left")
            if yo and abs(g["x"] + g["width"] - h["x"]) < 1:
                sides.add("right")
        return sides

    for e in cells:
        if not e.edge or e.get("endArrow", "classic") == "none" and e.get("startArrow", "none") == "none":
            continue
        for end, node_id, kx, ky in (("tail", e.source, "exitX", "exitY"), ("head", e.target, "entryX", "entryY")):
            if node_id is None:
                dangling.append(f"{e.id}.{end}")
                continue
            node = ids.get(node_id)
            if e.get(kx) is None or e.get(ky) is None:
                floating.append(f"{e.id}.{end}")
                continue
            x, y = float(e.get(kx)), float(e.get(ky))
            if node is None or node.geo is None:
                continue
            w, h = node.geo["width"], node.geo["height"]
            side = {0.0: "left", 1.0: "right"}.get(x) or {0.0: "top", 1.0: "bottom"}.get(y)
            along = (y * h, (1 - y) * h) if side in ("left", "right") else (x * w, (1 - x) * w)
            if end == "tail":  # a tail may leave from near a corner, just not from the corner point
                if x in (0.0, 1.0) and y in (0.0, 1.0):
                    fails.append(f"{e.id}: tail leaves from a corner of {node_id!r}")
                continue
            if side and min(along) < CORNER_PX:
                fails.append(f"{e.id}: head lands on or within {CORNER_PX}px of a corner of {node_id!r} "
                             f"({kx}={x:g}, {ky}={y:g})")
            elif side and side in dividers(node):
                fails.append(f"{e.id}: {end} lands on the divider at the {side} of {node_id!r}")
    return fails, floating, dangling


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("drawio")
    ap.add_argument("--width", help="width the figure will occupy in the paper, e.g. 3.33in or 7in")
    ap.add_argument("--outdir", help="where FIG.pdf / FIG.png go (default: next to FIG.drawio)")
    ap.add_argument("--dpi", type=int, default=300, help="PNG preview resolution")
    a = ap.parse_args()

    src = os.path.abspath(a.drawio)
    stem = os.path.splitext(os.path.basename(src))[0]
    outdir = os.path.abspath(a.outdir or os.path.dirname(src))
    os.makedirs(outdir, exist_ok=True)
    tmp = tempfile.mkdtemp(prefix="pdbuild-")
    failed = False

    def report(name, probs, ok_msg, fatal=True):
        nonlocal failed
        if probs:
            failed = failed or fatal
            print(f"{'FAIL' if fatal else 'WARN'} {name}: {len(probs)}")
            for p in probs:
                print("  - " + p)
        elif ok_msg:
            print(f"OK   {name}: {ok_msg}")

    try:
        _, cells, npages = load(src)
        write_variants(src, tmp, stem)
        export(tmp)
        out = lambda s: os.path.join(tmp, "out", s + ".pdf")
        pdf = out(stem)
        shutil.copy(pdf, os.path.join(outdir, stem + ".pdf"))
        run(["pdftoppm", "-r", str(a.dpi), "-png", "-singlefile", pdf, os.path.join(outdir, stem)], check=True)

        size = re.search(r"Page size:\s+([\d.]+) x ([\d.]+)", run(["pdfinfo", pdf]).stdout)
        wbp, hbp = float(size.group(1)), float(size.group(2))
        print(f"OK   export: {os.path.join(outdir, stem + '.pdf')}  "
              f"({wbp / 72:.2f}in x {hbp / 72:.2f}in natural size)")
        print(f"     preview: {os.path.join(outdir, stem + '.png')}")
        if npages > 1:
            print(f"WARN pages: the file has {npages} pages; only page 1 was exported and checked")

        fonts = [f for f in run(["pdffonts", pdf]).stdout.splitlines()[2:] if f.strip()]
        names = sorted({f.split()[0].split("+")[-1] for f in fonts})
        t3 = sorted({f.split()[0].split("+")[-1] for f in fonts if "Type 3" in f})
        unemb = [f.split()[0] for f in fonts if " no " in f" {f} " and "Type 3" not in f]
        foreign = [n for n in names if not n.startswith("Roboto")]
        probs = ([f"Type 3 (variable or CFF font installed; install the static TrueType Roboto): "
                  f"{', '.join(t3)}"] if t3 else []) + \
                ([f"not embedded: {', '.join(unemb)}"] if unemb else []) + \
                ([f"not Roboto (font missing on this machine, or a non-house font): {', '.join(foreign)}"]
                 if foreign else [])
        report("fonts", probs, f"{', '.join(names)} (embedded TrueType)")

        report("style", style_check(cells), "fonts, palette and flat styling as in the house style")
        top, probs = steps_check(cells)
        report("steps", probs, f"badges 1..{top}" if top else "no step badges")
        brief = os.path.splitext(src)[0] + ".brief.md"
        if os.path.exists(brief):
            probs, n = brief_check(brief, top)
            report("brief", probs, f"{os.path.basename(brief)}: all sections present, "
                                   f"{n} steps match the badges")
        else:
            print(f"WARN brief: no {os.path.basename(brief)} next to the figure; write it before drawing "
                  f"(message, reading order, elements, steps, caption)")
        fails, floating, dangling = arrows_check(cells)
        report("arrows", fails, "no arrowhead on a corner or cell divider")
        if floating:
            print(f"WARN arrows: end not pinned (no exitX/Y or entryX/Y), so it may land near a corner: "
                  f"{', '.join(floating)}")
        if dangling:
            print(f"WARN arrows: end not attached to a shape (moves won't follow it): {', '.join(dangling)}")
        report("groups", stranded_titles(cells), None, fatal=False)

        wl_all = words(pdf)
        report("collisions", collisions(out(stem + "-lint"), out(stem + "-lint-notext"), tmp, wl_all),
               f"no glyph within {CLEAR_PT}pt of a solid/dashed line or border")
        flat_words = words(out(stem + "-flat"))
        report("overlaps", overlaps(flat_words), "no text on text (sloped labels not checked)")

        px = [s for c in cells for s in font_sizes_px(c)]
        if px:
            odd = sorted({s for s in px if s not in HOUSE_PX})
            if odd:
                print(f"WARN style: font sizes {', '.join(f'{s:g}' for s in odd)} px are outside the house set "
                      f"{sorted(HOUSE_PX)}")
            smallest = min(px) * PT_PER_PX
            if a.width:
                target = to_bp(a.width)
                ratio = wbp / target
                scale = 1.0
                if ratio > 1.05:
                    failed = True
                    print(f"FAIL size: natural width is {ratio:.2f} x {a.width} ({wbp / PT_PER_PX:.0f} px; "
                          f"budget {target / PT_PER_PX:.0f} px). Shrinking it to fit thins every line and "
                          f"font relative to sibling figures -- tighten the layout")
                    print(f"     {extents(cells)}")
                elif ratio >= 0.95:
                    scale = target / wbp
                    print(f"OK   size: natural width {ratio:.2f} x {a.width}; include with width={a.width}")
                else:
                    print(f"INFO size: natural width {ratio:.2f} x {a.width}; include at natural size "
                          f"(\\includegraphics{{{stem}}} without width=), or widen the layout to fill {a.width}")
                if smallest * scale < MIN_PT:
                    failed = True
                    print(f"FAIL size: smallest text {smallest * scale:.2f}pt at print size (min {MIN_PT}pt)")
            else:
                print(f"INFO size: smallest text {smallest:.1f}pt at natural size (pass --width to check)")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    sys.exit(2 if failed else 0)


if __name__ == "__main__":
    main()
