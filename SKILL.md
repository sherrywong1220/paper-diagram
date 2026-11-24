---
name: paper-diagram
description: Draw schematic diagrams for CS research papers (architecture overviews, mechanism and control/data-flow figures, step-by-step protocol or fault-handling paths, memory/page layouts, concept illustrations) in one fixed house style — Roboto bold labels, light-blue component boxes, black arrows, circled step numbers, dotted domain boundaries, red/orange highlights for tracked items. It first writes a short English brief of the figure's logic (message, reading order, elements, numbered steps, caption), then draws from it. Output is that brief, an editable draw.io file that the user can keep editing by hand, a vector PDF ready for \includegraphics and a PNG preview, checked by a build-and-lint script. Use for requests like "draw a diagram / overview figure / architecture figure for my paper", "turn this mechanism into a figure", "redraw this figure in our style", "画一个示意图 / 架构图 / 流程图（论文用）". Not for plots of experimental data (bar/line/CDF charts), slide decks, or web/Artifact diagrams.
metadata:
  type: Workflow
  created: 2026-11-16
  revised: 2026-11-16 — moved from TikZ to draw.io so that users can edit figures in a GUI; added the English brief written before drawing, checked by the build
  style-source: two reference figures supplied by the user (page-fault handling paths); the first is reproduced in examples/uffd-fault-path.drawio
---

# Paper Diagram

Produce a diagram that a reader of a systems/architecture paper understands in one pass.
1. First, write down the figure's logic as a short English brief: what it should convey, and in what order the reader takes it in.
2. Then draw it from that brief, in the house style below.

The result is a draw.io file the user can keep editing by hand, and a print-ready vector PDF.

Paths below are relative to this file's directory (`<skill>`).

## Deliverables

For a figure named `<name>` (kebab-case, e.g. `fault-path`), put the files in the user's figure directory if the paper repo has one (`figures/`, `fig/`, …), otherwise in `./diagrams/`:

| File | What it is |
|---|---|
| `<name>.brief.md` | The figure's logic in English, written before any drawing (see "The brief comes first"). The figure is drawn from it and checked against it. Later, it tells the user and the next agent what each part of the figure is for. |
| `<name>.drawio` | The source of record: uncompressed draw.io XML. It opens in the draw.io desktop app, app.diagrams.net or the VS Code draw.io extension. Every later edit, yours or the user's, happens here. |
| `<name>.pdf` | Vector export, cropped, fonts embedded. This is what the paper includes. |
| `<name>.png` | 300-dpi preview. |

If `<name>.drawio` already exists, the user may have edited it by hand. Edit that file in place and keep their changes. Never regenerate it from a script.

In the final reply, give:
- the paths;
- the `\includegraphics` line (the build prints whether to pass `width=`);
- the caption and the assumptions, taken from the brief;
- how to edit: open the `.drawio` in draw.io, then rerun the build command, or use File → Export as → PDF with Crop. New elements keep the house style when they are copied from existing ones, or styled with Copy Style / Paste Style in the Format panel. If an edit changes the figure's logic, update the brief too.

## The brief comes first

Before writing any XML, write `<name>.brief.md` in English, then show it to the user in your message: the whole file if it is short, otherwise at least the Message and the Steps.

Then keep drawing without waiting. Stop and ask only if the mechanism is unclear:
- who triggers what;
- whether a step is sync or async;
- where a component lives;
- what the one takeaway is.

In that case, stop after the brief, ask those questions, and draw once they are answered.

The brief has these sections, in this order. The build checks that each one marked "required" exists and is not empty.

- `## Message` (required). The one sentence a reader should take away. Every element must serve it, and it decides what to leave out.
- `## Reading order` (required). Where the eye enters, which way it travels, and which regions (domains, columns) it crosses. This sets the layout: put the start of the story where reading starts.
- `## Elements` (required). The components and storage, and the highlights: what is red, what is orange, and why.
- `## Steps` (required). A top-level numbered list with one item per badge, written as "who → what → whom (sync|async)". Add the label text if it differs, and any unnumbered arrows that belong to the step. For a figure without steps, write "None". The build checks that these numbers are exactly the figure's badges.
- `## Caption` (required). The caption draft. It also says what the figure deliberately leaves out: things a snapshot can't show, and details that would crowd it.
- `## Assumptions`. Every choice you made where the description was ambiguous, or "None".

`examples/uffd-fault-path.brief.md` is a complete brief. `assets/template.brief.md` goes with the template.

When you change an existing figure:
- If the request changes the message, steps, elements or highlights, update the brief first, then the figure.
- If the user edited the `.drawio` by hand and the build reports that the brief no longer matches, the figure wins. Bring the brief up to date and say so.

## Acceptance criteria

The figure is done when all of these hold:

1. **Brief first, and the figure follows it.**
   - `<name>.brief.md` was written and shown before the drawing started.
   - The build prints `OK brief`.
   - Every box, arrow and highlight in the figure appears in the brief's Elements or Steps.
   - The figure reads in the brief's Reading order.
2. **Lint passes.** `python3 <skill>/scripts/build.py <name>.drawio --width <W>` exits 0.
   - `<W>` is the width the figure occupies in the paper. Common values: ACM `acmart` and USENIX are 3.33in column / 7in full; IEEEtran is 3.5in / 7.16in. Take `\columnwidth` from the paper source when available; otherwise use what the user says, or 3.33in and say so.
   - The script exports page 1 and checks:
     - fonts: Roboto family only, embedded as TrueType;
     - style (read from the XML): Roboto fonts, palette fills, black lines and text, no shadows, gradients or rounded corners;
     - steps: badges numbered 1..N, each used once;
     - brief: `<name>.brief.md` sits next to the `.drawio`, has its required sections, and its Steps are numbered exactly like the badges. A missing brief is a WARN, so the user can still build figures that have none.
     - arrows: no arrowhead on or within 4px of a corner, or on the divider between stacked cells;
     - collisions: no glyph within 1pt of a solid or dashed line, border or bolt;
     - overlaps: no horizontal text on text;
     - size: natural width ≤ 1.05 × `<W>`, smallest text ≥ 7pt.
   - WARN lines do not fail the build: unpinned or unattached arrow ends, a column title outside its column's group, font sizes outside the house set, extra pages. Fix them, or say why they are intended.
3. **Drawn at print size.** draw.io exports 100 px per inch, so 1 px = 0.72pt and a 3.33in column is 333 px wide.
   - Use the build's verdict: either the natural width is 0.95–1.05 × `<W>` and the figure is included with `width=<W>`, or it is narrower and included at natural size.
   - Never scale a figure to fit; its fonts and line weights must match those of the sibling figures.
4. **Editable by hand.** When the user drags any box in draw.io, the figure stays intact:
   - Every arrow is attached to its shapes: `source`/`target` set, with ends pinned by `exitX/exitY/entryX/entryY`.
   - A storage column, including its title, is one group.
   - Each label is real text in its own cell or on its arrow.
   - Cell ids are meaningful (`main`, `vm-2`, `s3`).
   - An arrow ends at a free point only when it points into a region rather than at a shape.
5. **Faithful content.** Every box, arrow and label corresponds to something in the user's description or paper text. Nothing is invented to fill space. Where the description is ambiguous (who triggers what, sync vs. async, where a component lives), ask. If you can't ask, choose, and record the choice under the brief's Assumptions.
6. **Style checklist, verified on the PNG.** Read the PNG after every build. Where arrows converge, zoom in with `pdftoppm -r 900 -png -x X -y Y -W w -H h <name>.pdf zoom`. At 900 dpi one draw.io px is 9 pixels, so X and Y are 9 × the px positions the lint prints, which are measured from the figure's top-left. Check that:
   - Each badge sits next to the arrow it numbers: the badge itself, not just the far end of its label, is within ~15 px of the line and closer to it than to any other arrow. A step drawn as several parallel arrows (e.g. fetch from DRAM *or* CXL) gets one badge beside the group.
   - Components that play the same role are aligned on a shared x or y and have equal widths.
   - Sloped labels don't overlap other text; the lint can't check this.
   - There are at most two accent colours, and a tracked item has the same colour everywhere it appears.
   - There are no legends, in-figure titles or 3D effects. The caption carries the title.
7. **Siblings stay comparable.** Sometimes figures are meant to be compared, such as baseline vs. ours or before vs. after. Then start each one from a copy of the first file, so that the shared skeleton (boundaries, storage columns, common components) has identical coordinates in all of them. Only the parts that differ move.

## Visual language

Distilled from the two reference figures. Use these style strings verbatim, so that the lint and the user's later copy-paste edits stay consistent:

```
box     rounded=0;whiteSpace=wrap;html=1;fillColor=#CAEAFA;strokeColor=#000000;strokeWidth=1.1;fontFamily=Roboto;fontStyle=1;fontSize=11;fontColor=#000000;
label   text;html=1;align=center;verticalAlign=middle;whiteSpace=nowrap;fontFamily=Roboto;fontStyle=1;fontSize=11;fontColor=#000000;
header  text;html=1;align=left;verticalAlign=top;whiteSpace=nowrap;fontFamily=Roboto;fontStyle=1;fontSize=14;fontColor=#000000;
arrow   endArrow=classic;endFill=1;endSize=4;html=1;rounded=0;strokeWidth=1.7;strokeColor=#000000;labelBackgroundColor=none;fontFamily=Roboto;fontStyle=1;fontSize=11;fontColor=#000000;
dashed  <arrow> + dashed=1;dashPattern=3.7 2.3;
curved  <arrow> + curved=1;   with one waypoint; the bulge is about half the waypoint's distance from the chord
dotted  endArrow=none;html=1;dashed=1;dashPattern=1 2;strokeWidth=1;strokeColor=#000000;
cell    rounded=0;html=1;fillColor=#FFFFFF;strokeColor=#000000;strokeWidth=1.1;
rails   shape=partialRectangle;top=0;bottom=0;left=1;right=1;fillColor=none;html=1;strokeColor=#000000;strokeWidth=1.1;
bolt    copy the `bolt` cell from assets/template.drawio (a stencil); aim it with rotation=, flipH=1, flipV=1
code    <font face="Roboto Mono">ioctl()</font>   inside any label
badge   <span style="display:inline-block;box-sizing:border-box;width:12px;height:12px;border:0.75px solid #000;border-radius:50%;font-weight:normal;font-size:10.5px;line-height:11px;text-align:center;vertical-align:-2px">2</span>
```

Palette: `#CAEAFA` blue, `#B5372B` red, `#DF7530` orange, `#E4E4E4` gray, and white. Sizes: body text 11 px (7.9pt), headers 14 px, badge digits 10.5 px (7.6pt, so they stay ≥ 7pt even when a figure 5% too wide is included at `width=<W>`).

- **Layout.** Actors on the left, mechanism in the middle, data/storage on the right (or top → bottom). Generous whitespace: empty space is better than crowding.
- **Domains.** Separate protection domains or machines with a `dotted` line (an edge with `sourcePoint`/`targetPoint`). Give each region a `header`.
  - Vertical boundary between two regions whose widths are within ~1.5× of each other: put the headers flush on both sides of the line, 5–7 px away, as in the references ("Userspace : Kernel"). The left header uses `align=right`.
  - Otherwise put each header above its own region's content.
  - Horizontal boundary (e.g. a Hardware layer): header at the region's top-left, clear of arrows that cross into the band.
  - Three domains (Userspace | Kernel above Hardware): run the horizontal line across the full width, and stop the vertical line where it meets the horizontal one.
  - Nested domain: a dotted rectangle (`rounded=0;fillColor=none;dashed=1;dashPattern=1 2;strokeWidth=1;`).
  - Keep ≥ 8 px between a header and anything below it.
- **Components** (`box`): ≥ 50×34 px, centred bold label of 1–2 short lines ("Main<br>Thread", `<font face="Roboto Mono">my_ctx</font><br>context`). Sub-components sit next to their parent, connected by short arrows (below it when there is room), rather than nested inside it.
- **Storage.** A column of white `cell`s inside a `group` cell, with child coordinates relative to the group. The title is a child of the group too, so a drag moves everything together.
  - Cell ids are `vm-1…vm-N`, top to bottom; the title is `vm-title`.
  - Address space: open column. Add a `rails` cell spanning the group, so the rails run ~13 px past both ends. Cells are about 17×14 px.
  - Physical frames, slots or blocks: closed column, about 40×13 px cells.
  - Title above the column, in two short lines.
- **Colour semantics.**
  - Red: the item the story is about (faulting page, missing block, hot object), in every place it appears, including its copy in another tier. Also the event bolt.
  - Orange: a second, distinct tracked item (source page, prefetched block).
  - There is no gray line. To de-emphasise an arrow, leave it unnumbered and unlabeled, or move it to the caption.
  - Gray: de-emphasis. Use it for an unchanged component, or a cold, stale or evicted cell. It does not count as an accent.
  - Everything else is black on white or blue.
- **Arrows.**
  - Straight lines directly between endpoints; diagonals are welcome. No `edgeStyle=orthogonalEdgeStyle` unless the figure is a pipeline.
  - `arrow` (solid): synchronous call, access or data movement.
  - `dashed`: the hand-off doesn't wait: notifications, queued or deferred work, hardware writing in the background, optional paths. Judge each arrow on its own. A background thread's direct reads and writes are still solid.
  - `curved`: only for an in-place transform, such as a copy within one column.
  - Arrows end on the thing they act on: a cell, not the column title.
  - Data moved between tiers by a component: the component's numbered arrow goes to the cell it acts on, and the transfer is a cell → cell arrow. The example does this: ⑥ Write goes from the handler to its page, then an unnumbered arrow maps it to its frame.
- **Labels.**
  - Keep them short: a verb for actions ("Access", "Write", "Load and register"), Title Case nouns for components, `code` for syscalls and identifiers.
  - Put an arrow's label on the arrow itself (its `value`), placed with `<mxGeometry relative="1" x="…">` (−1 = tail, 0 = middle, 1 = head) plus `<mxPoint y="…" as="offset"/>`. The offset goes to the label's centre: use at least half the label's height + 6 px (13 for one line, 20 for two).
  - Labels are horizontal by default, as in the second reference.
  - Slope a label only for a code identifier riding a long diagonal, as in the first reference. Use a separate `label` cell with `rotation=` set to atan2(dy, dx) in degrees, centred 10–11 px off the line. It won't follow the arrow when moved, so re-place it after layout changes.
- **Steps.** Put the `badge` span before the label text ("`<badge>` Access"). A label that holds only a badge is fine when the arrow needs no words.
  - One badge per event the reader should see.
  - When a step has several actions, draw the minor ones as unnumbered arrows inside the same step, or join them in the label ("Alloc + copy").
  - Anything a single snapshot can't show (freeing a frame, a threshold check) goes in the caption.
- **Events.** A red bolt aimed at the cell where the fault, interrupt or failure happens, with its numbered label nearby.
- **Icons.** At most one small mascot or logo, and only if the user supplies the image (an `image` cell). Never draw clip-art.

## Resources

- `assets/template.drawio` + `template.brief.md` — a starter that uses every primitive: boundary with headers, boxes, a code label, an open column, solid and dashed arrows with badges, and the bolt. Copy both to `<name>.*`, rewrite the brief, then edit the drawing.
- `examples/uffd-fault-path.brief.md` + `.drawio` + `.png` — a faithful reproduction of the first reference: two columns, sloped code labels, a curved copy arrow, eight steps. Read it before your first figure. It is the best answer to "how is X done in this style".
- `scripts/build.py` — export + lint (see the acceptance criteria). Standard-library Python. It needs:
  - **draw.io desktop.** The `drawio` CLI; on macOS, `brew install --cask drawio`. On headless Linux, run it under `xvfb-run`.
  - **Static TrueType Roboto and Roboto Mono, installed as system fonts.** Get the `.ttf` files from the googlefonts/roboto v2.138 release (`roboto-unhinted.zip`) and from googlefonts/RobotoMono `fonts/ttf/`. Copy them to `~/Library/Fonts` on macOS or `~/.local/share/fonts` on Linux.
  - **poppler:** `pdfinfo`, `pdffonts`, `pdftotext`, `pdftoppm`.
- `local/style-refs/*.png` — the original reference figures, if present on this machine (private, not shared). Look at them when unsure about the look.

If draw.io or the fonts can't be installed, stop and tell the user what is missing. Don't switch to another tool or font: the output would no longer match the style, and that is worse than no figure.

## Working method (advice, not a script)

- Draw from the brief:
  - its Reading order decides where things go;
  - its Steps become the badges;
  - its Elements are the complete list of what to draw.

  If the drawing needs another order or an extra step, change the brief first, then the figure.
- Lay out on a coarse px grid at print size. Budget width before placing anything:
  - A 3.33in column is 333 px; 7in is 700 px.
  - Text widths: Roboto Bold 11 px ≈ 5.5–6 px per character; Roboto Mono 11 px = 6.6 px per character; a 14 px header ≈ 7 px per character; a badge plus its gap ≈ 16 px.
- Write the XML directly. Start from the template, with one `mxCell` per line and meaningful ids.
- A throwaway script is fine for arithmetic such as sloped-label positions or long columns. The `.drawio` stays the only source; never keep a generator alongside it.
- Draw the skeleton first, then the flow. Pin arrow ends to shape edges with `exitX/exitY/entryX/entryY`, using 0.15–0.85 to spread several ends along one edge. Later moves then keep every arrow attached.
- Iterate build → look at the PNG → fix; 3–6 rounds is normal. When something doesn't fit, shorten the label, move the arrow, or widen the layout. Never shrink fonts or scale the picture.

## Known pitfalls (all hit while building the example or in test runs)

| Symptom | Cause | Fix |
|---|---|---|
| `fonts` FAIL: Type 3 | Roboto is installed as a variable font (Homebrew `font-roboto`, the default Google Fonts download). Chromium, which draw.io uses for export, embeds variable fonts as Type 3, and submission checkers reject Type 3. | Remove the variable font and install the static `.ttf` files (see Resources). |
| A bare badge on an arrow touches its line | A label's offset is measured to the label's centre. At `y="-11"` the circle's edge reaches a near-horizontal line. | Offset by at least half the label's height + 6 px (see Labels), and more on a slope. |
| Natural width over budget, with blank space at an edge | The crop counts a text cell's whole box, not its ink. A 60 px title box over a 17 px column adds invisible width. | Size each text cell to its text plus ~4 px. On a size FAIL, the build names the cells that set the left and right edges. |
| A column's title stays behind when the user drags the column | The title was a sibling of the group instead of its child | Put the title inside the group (the build warns otherwise). |
| A sloped label collides at both ends | The label is nearly as long as its arrow, so one end meets the arrowhead and the other meets the box | Centre it on the arrow (pos ≈ 0.5), move it 1–2 px further off the line, or shorten it. |
| ① reads as ⑦ | A badge inside a rotated label rotates with it, and a tilted Roboto "1" looks like "7" | Keep only the code text rotated. Put the badge in its own upright `label` cell at the label's start. |
| A label between two arrows leaving one box touches the other arrow | The arrows are only ~16 px apart at the box | Start them ≥ 22 px apart on the box side, and centre the label toward the wide end. |
| A region header collides with a label, column title or box below it | Headers are placed last, near the boundary where other labels also crowd | Reserve a header band at the top (≥ 8 px clear below it) before placing anything else. |
| Arrowheads on one cell are ambiguous (on a corner or divider, or hiding one another) | Several arrows target the same 14 px cell; this is only visible when zoomed in | Spread the ends across the cell's edges (`entryY=0.3` / `0.7`, or the top edge), or make the cell taller, then zoom-check. |

Labels may cross the dotted domain boundary (both references do), so the lint ignores dotted lines. Avoid crossing it anyway when there is room. The lint also removes label backgrounds before checking: a white label background that hides the line under it counts as a collision.
