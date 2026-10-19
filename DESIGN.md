---
name: BacterioScope
description: Plate-review light box for Kirby-Bauer zone measurement, correction and sign-off.
colors:
  felt: "#0b0d0c"
  felt-raise: "#121514"
  felt-sunk: "#070808"
  rule: "#232826"
  rule-strong: "#353b38"
  graticule: "#2c3230"
  ink: "#ece9e1"
  ink-2: "#bdbdb4"
  ink-3: "#8f938b"
  ink-hover: "#fffdf6"
  cat-s: "#4f9e7b"
  cat-i: "#d39a3a"
  cat-sdd: "#d39a3a"
  cat-r: "#d26a61"
  flag: "#b4a259"
typography:
  display:
    fontFamily: "Atkinson Hyperlegible Next, Segoe UI, system-ui, sans-serif"
    fontSize: "2.125rem"
    fontWeight: 700
    lineHeight: 1.1
    letterSpacing: "-0.02em"
  headline:
    fontFamily: "Atkinson Hyperlegible Next, Segoe UI, system-ui, sans-serif"
    fontSize: "1.5rem"
    fontWeight: 700
    lineHeight: 1.25
  title:
    fontFamily: "Atkinson Hyperlegible Next, Segoe UI, system-ui, sans-serif"
    fontSize: "1.125rem"
    fontWeight: 700
    lineHeight: 1.3
  body:
    fontFamily: "Atkinson Hyperlegible Next, Segoe UI, system-ui, sans-serif"
    fontSize: "0.9375rem"
    fontWeight: 400
    lineHeight: 1.5
    fontFeature: "tnum"
  body-sm:
    fontFamily: "Atkinson Hyperlegible Next, Segoe UI, system-ui, sans-serif"
    fontSize: "0.8125rem"
    fontWeight: 400
    lineHeight: 1.5
  label:
    fontFamily: "Atkinson Hyperlegible Next, Segoe UI, system-ui, sans-serif"
    fontSize: "0.75rem"
    fontWeight: 500
    lineHeight: 1.5
    letterSpacing: "0.04em"
  readout:
    fontFamily: "Atkinson Hyperlegible Mono, ui-monospace, Cascadia Mono, Consolas, monospace"
    fontSize: "1.5rem"
    fontWeight: 500
    lineHeight: 1
    letterSpacing: "-0.02em"
  mono:
    fontFamily: "Atkinson Hyperlegible Mono, ui-monospace, Cascadia Mono, Consolas, monospace"
    fontSize: "0.8125rem"
    fontWeight: 400
    lineHeight: 1.4
  mono-tag:
    fontFamily: "Atkinson Hyperlegible Mono, ui-monospace, Cascadia Mono, Consolas, monospace"
    fontSize: "0.75rem"
    fontWeight: 700
    lineHeight: 1.4
rounded:
  hairline: "2px"
  round: "50%"
spacing:
  xxs: "0.125rem"
  xs: "0.25rem"
  sm: "0.5rem"
  md: "0.75rem"
  lg: "1rem"
  xl: "1.25rem"
  gutter: "clamp(1rem, 2.4vw, 2rem)"
  strip: "3.5rem"
components:
  button-primary:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.felt}"
    typography: "{typography.body}"
    rounded: "{rounded.hairline}"
    padding: "0 1rem"
    height: "2.5rem"
  button-primary-hover:
    backgroundColor: "{colors.ink-hover}"
    textColor: "{colors.felt}"
  button-primary-disabled:
    backgroundColor: "transparent"
    textColor: "{colors.ink-3}"
  button-quiet:
    backgroundColor: "transparent"
    textColor: "{colors.ink-2}"
    rounded: "{rounded.hairline}"
    padding: "0 1rem"
    height: "2.5rem"
  button-quiet-hover:
    textColor: "{colors.ink}"
  tool:
    backgroundColor: "transparent"
    textColor: "{colors.ink-2}"
    typography: "{typography.body-sm}"
    rounded: "{rounded.hairline}"
    padding: "0 0.75rem"
    height: "2.25rem"
  tool-pressed:
    textColor: "{colors.ink}"
  field-input:
    backgroundColor: "{colors.felt-sunk}"
    textColor: "{colors.ink}"
    typography: "{typography.body}"
    rounded: "{rounded.hairline}"
    padding: "0 0.625rem"
    height: "2.25rem"
  lang-toggle-active:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.felt}"
    typography: "{typography.mono}"
    height: "2.25rem"
    width: "2.75rem"
  category-s:
    backgroundColor: "{colors.cat-s}"
    textColor: "{colors.felt}"
    typography: "{typography.mono-tag}"
    rounded: "{rounded.hairline}"
    height: "1.75rem"
  category-i:
    backgroundColor: "{colors.cat-i}"
    textColor: "{colors.felt}"
    typography: "{typography.mono-tag}"
    rounded: "{rounded.hairline}"
    height: "1.75rem"
  category-sdd:
    backgroundColor: "transparent"
    textColor: "{colors.cat-sdd}"
    typography: "{typography.mono-tag}"
    rounded: "{rounded.hairline}"
    height: "1.75rem"
  category-r:
    backgroundColor: "{colors.cat-r}"
    textColor: "{colors.felt}"
    typography: "{typography.mono-tag}"
    rounded: "{rounded.hairline}"
    height: "1.75rem"
  zone-tag:
    backgroundColor: "rgba(7, 8, 8, 0.84)"
    textColor: "{colors.ink}"
    typography: "{typography.mono-tag}"
    rounded: "{rounded.hairline}"
    padding: "0.125rem 0.375rem"
  caliper-handle:
    backgroundColor: "{colors.felt}"
    rounded: "{rounded.round}"
    size: "1.125rem"
  loupe:
    backgroundColor: "{colors.felt-sunk}"
    rounded: "{rounded.round}"
    size: "7rem"
---

# Design System: BacterioScope

Scope: the plate-review web app served by FastAPI at `/` (`src/bacterioscope/web/`). The Streamlit demo and the per-plate HTML reports use the separate Clinical Slate tokens in `src/bacterioscope/design/tokens.py` and are not governed by this file.

## Overview

**Creative North Star: "The Light Box" (Caja de luz)**

The screen is the matte black, non-reflective background a microbiologist already reads plates against (CLSI M02). It is not a dark mode chosen for mood; it is the reading surface. There is exactly one theme, declared with `color-scheme: dark`, and there is no light variant to fall back to. The photograph leads: every measurement is drawn on the plate itself, at true scale, in thin porcelain line, and the rest of the interface behaves like an instrument laid beside it.

Density is that of a bench instrument, not a dashboard. Panels are divided by one-pixel rules rather than boxed in cards; nothing floats, nothing casts a shadow. Numbers are always tabular and every millimetre, code and calibration value is set in the monospaced cut, so readings line up and tick cleanly while the user drags. Colour is withheld from the whole interface and spent only on the clinical category and on the system's own distrust of a measurement.

The system explicitly rejects the clinical SaaS dashboard (sidebar, white cards, blue accent) and the neon "AI lab" look.

**Key Characteristics:**
- One deliberate dark theme: matte felt ground, porcelain ink.
- Colour reserved for S / I / SDD / R and an olive quality-flag hatch; everything else is greyscale.
- Atkinson Hyperlegible Next for UI, Atkinson Hyperlegible Mono for every measured value and code.
- Flat: hairline rules and tonal steps instead of cards and shadows.
- Measurements drawn on the photograph at true scale, corrected by direct manipulation.
- Bilingual ES/EN with identical layout in both languages.

## Colors

A near-black, faintly green-warm greyscale carries the interface; four category hues and one olive flag are the only chroma.

### Primary
- **Porcelain Ink** (ink): the colour of disk paper. Primary text, zone contours, caliper jaws, the focus ring, the primary button fill and the active language toggle. It is the "accent" of this system; the interface has no hue-based brand colour.

### Secondary
- **Susceptible Green** (cat-s): fill of the S category chip and the S segment of each ruler.
- **Intermediate Amber** (cat-i): fill of the I category chip and the I segment of each ruler.
- **SDD Amber** (cat-sdd): same amber as I, but SDD is always drawn as an outline chip (amber border and letter, no fill) so the two never read as the same category.
- **Resistant Red** (cat-r): fill of the R category chip, the R ruler segment, and the border of an error toast or the colour of an intake error message.

### Tertiary
- **Olive Flag** (flag): quality flags only. The 45-degree hatch over a distrusted zone, a flagged zone's contour, the flag icon and text in a ruler note, and excluded rows in the results table.

### Neutral
- **Felt** (felt): page ground, strip, bench footer, the hollow centre of caliper handles.
- **Felt Raised** (felt-raise): hover and selected ruler rows, drop-target hover, toasts.
- **Felt Sunk** (felt-sunk): input wells, the loupe well, the evidence column of the review.
- **Rule** (rule): the one-pixel dividers between every panel and row.
- **Rule Strong** (rule-strong): control borders, major graticule lines, scrollbar thumb, the disk segment of each ruler.
- **Graticule** (graticule): minor lines of the millimetre graticule over the plate.
- **Ink 2** (ink-2): secondary text, leader lines, ruler tick marks every 5 mm, quiet controls at rest.
- **Ink 3** (ink-3): tertiary text, labels, plate rim, minor ticks, uncategorised chips.
- **Ink Hover** (ink-hover): the only hover state of the primary button, one step brighter than porcelain.

### Named Rules
**The Category-Only Colour Rule.** S, I, SDD and R hues appear only where a susceptibility category is being stated: category chips and ruler segments. Never use them for decoration, status of the app, or emphasis.

**The Flag Is Not Red Rule.** A quality flag means "the system distrusts this measurement", not "resistant". Flags are olive hatch and olive text, never in the resistant red.

**The Never By Colour Alone Rule.** Every category carries its letter (S, I, SDD, R); every flag carries an icon and a sentence; hatching works without colour vision.

## Typography

**Display Font:** Atkinson Hyperlegible Next (with Segoe UI, system-ui, sans-serif)
**Body Font:** Atkinson Hyperlegible Next
**Label/Mono Font:** Atkinson Hyperlegible Mono (with ui-monospace, Cascadia Mono, Consolas, monospace)

**Character:** A legibility-first humanist sans paired with its own monospaced sibling, so prose and readings share one voice while measured values read as instrument output. Weights in use are 400, 500 and 700 only.

### Hierarchy
- **Display** (700, 2.125rem, 1.1, -0.02em): the review title only.
- **Headline** (700, 1.5rem, 1.25): the intake lead inside the drop ring.
- **Title** (700, 1.125rem, 1.3): the bench heading and the wordmark.
- **Body** (400, 0.9375rem, 1.5, tabular numerals): default text. The agent explanation runs one step larger (1.125rem, 1.6) at a 65ch measure.
- **Body small** (400, 0.8125rem): hints, legends, tool buttons, table cells, status lines.
- **Label** (500, 0.75rem, 0.04em to 0.06em tracking, uppercase): form-field labels, the sample-plates heading, the results-table caption and the evidence-column headings. These are the headings of their own groups, never small lines stacked above a larger headline.
- **Readout** (Mono 500, 1.5rem, 1, -0.02em): the measured diameter at the end of each ruler, with a 0.75rem "mm" unit in ink-3. Category letters beside it match its size.
- **Mono** (Mono 400, 0.8125rem): calibration readout in the strip, ruler position numbers, ES/EN toggle.
- **Mono tag** (Mono 700, 0.75rem): antibiotic codes, zone tags on the plate, category chips. Ruler scale numerals use 0.6875rem.

### Named Rules
**The Every Millimetre Is Mono Rule.** Any measured value, antibiotic code, position number, calibration figure or trace hash is set in Atkinson Hyperlegible Mono. Prose is never set in mono.

## Layout

The light box is a two-column grid under a sticky 3.5rem instrument strip: the stage (about 60 percent, `minmax(0, 1.45fr)`) holds the plate at reading size, and the bench (`minmax(22rem, 1fr)`) holds one ruler per antibiotic and sticks under the strip with its own scroll. The plate frame sizes itself from the photo's aspect ratio and the viewport height so the whole plate is always visible. The review section repeats the same 1.45 : 1 split below: report on the left, evidence on a sunk column on the right. Intake collapses the box to one column with the dashed 90 mm drop ring and a three-up grid of sample plates.

Horizontal padding is a single fluid gutter (`clamp(1rem, 2.4vw, 2rem)`); internal rhythm steps through 0.125, 0.25, 0.5, 0.75, 1 and 1.25rem. Each ruler row is a three-column grid (position, drug and scale, readout) with a note line spanning beneath.

Responsive behaviour: at 960px and below, every split becomes one column, the plate goes full width with the rulers below, the bench loses its sticky position, and the calibration readout gives way to a compact sample badge. At 520px and below the strip drops the wordmark text and the "new plate" label, sample plates go four-up, ruler rows put the drug picker on its own line, readouts drop to 1.125rem, and the loupe is hidden.

## Elevation & Depth

The system is flat. There are no box shadows anywhere. Depth is conveyed by three tonal steps of the felt (sunk, base, raised) and by one-pixel rules; the only translucency is the 84 percent felt-sunk backing behind zone tags and the 55 percent felt veil over the photo outside the plate rim, both there to keep marks legible over the photograph.

### Named Rules
**The Rules Not Cards Rule.** Separate regions with a one-pixel rule (rule) or a tonal step, never with a bordered card, a fill block, or a shadow.

## Shapes

Corners are a 2px hairline radius on every rectangular control, chip, tag, citation and toast: crisp, nearly square, instrument-like. The only other shape is the full circle, reserved for things that are physically round or optical: the plate and its graticule, zone contours, sample plate thumbnails, caliper handles and the loupe. Borders are 1px; the primary button is outlined in its own fill colour. Overlay strokes use `vector-effect: non-scaling-stroke` so a hairline stays a hairline at any plate size.

## Components

### Buttons
Quiet, rectangular, decisive; only one filled button is visible at a time.
- **Shape:** hairline corners (2px), minimum height 2.5rem (2.75rem in the bench footer), 1rem horizontal padding, icon and label 0.5rem apart.
- **Primary:** porcelain fill and border, felt text, weight 700. One per view: "Review with Nemotron" under the rulers, "Choose photo" at intake, "Download" at sign-off.
- **Hover / Focus:** hover brightens to ink-hover; active nudges down 1px; focus is a 2px porcelain outline at 2px offset. Disabled turns transparent with an ink-3 label and rule-strong border. Transitions are 160ms on the shared ease-out.
- **Quiet:** transparent with a rule-strong border and ink-2 label; hover lifts the label to ink and the border to ink-3.
- **Tool:** the quiet button at 2.25rem and body-small, used for plate toggles (graticule, contours). Pressed state (`aria-pressed`) turns label and border porcelain.

### Chips
- **Category chip:** mono 700 letter in a 2px-cornered cell, at least 2.25rem wide. S, I and R are filled in their hue with felt text; SDD is an amber outline; no category is a rule-strong outline in ink-3. At the end of a ruler it grows to the readout size.
- **Near-breakpoint chip:** mono xs in a rule-strong outline, ink-2, beside the drug code.
- **Citation chip:** mono xs in a rule-strong outline; source names switch to the UI face.

### Inputs / Fields
- **Style:** felt-sunk well, 1px rule-strong border, 2px corners, 2.25rem tall, body text; the label sits above in the uppercase label style.
- **Focus / hover:** hover raises the border to ink-3; focus is the global 2px porcelain outline.
- **Drug picker:** a lighter variant inside ruler rows, transparent with a rule border and ink-2 text, 1.75rem tall.

### Navigation
The instrument strip is the only navigation: wordmark and plate-dot mark on the left, the mono calibration readout filling the middle, and on the right the "new plate" quiet button and a segmented ES/EN toggle whose active half is filled porcelain with felt mono text. It is sticky, 3.5rem tall, on felt with a bottom rule.

### Plate Overlay (signature)
Drawn over the photograph at true scale: an optional millimetre graticule calibrated from the 90 mm rim, rim ticks, an origin marker at disk 1 with a clockwise reading-order arc, each zone contour in 1.5px porcelain, a dashed caliper ring, and the disk outline. Flagged zones turn their contour olive and carry a 45-degree olive hatch at 55 percent. Selection adds one fixed 2.5px porcelain focus ring; keyboard focus dashes it. On load, contours and calipers draw in clockwise from 12 o'clock, staggered 70ms per disk over 700ms, with tags and leaders fading in 350ms after their ring.

### Zone Tags
Each disk gets a mono tag (code, mm, category chip, flag icon) on a translucent felt-sunk backing. Tags are placed radially outward from their disk, trying successive angular offsets and scoring each candidate against other tags, so they never collide; a 1px ink-2 hairline leader connects any tag that has moved off its disk.

### Caliper Correction (signature interaction)
A circular handle (1.125rem, felt fill, 2px porcelain border) sits on the right edge of each selected zone; it scales to 1.25 and fills porcelain while dragged, with an east-west resize cursor. Dragging changes the zone diameter (6 to 60 mm): the tag digits, the ruler jaw and the readout update live and the category recomputes against CLSI breakpoints. A corrected zone gets a solid 2px caliper, a ghost marker of the original value on its ruler, a "Corrected, measured N mm" note with a restore link, and a correction note in the bench footer. Any outstanding correction blocks the agent review until restored, because the report cannot yet trace a corrected diameter.

### Antibiotic Ruler
One row per disk: position number, mono drug code, drug picker, then a 0 to 40 mm scale with ticks every millimetre (longer every 5, numbered every 10). R, I or SDD, and S breakpoint segments are drawn in their category colours with their letter above; the first 6 mm is a grey disk segment. A faint porcelain band (8 percent) spans plus or minus 2 mm around the reading, and a porcelain jaw with a triangular head marks the measured value. Hover and selection raise the row to felt-raise.

### Loupe
In the bench footer, a 7rem porcelain-ringed circle magnifies the selected zone's right edge at 3x on a felt-sunk well, redraws the contour and the measured circle, and carries a millimetre diameter scale. A two-line label gives disk number, code, diameter in mm and "edge x3". Hidden below 520px.

## Do's and Don'ts

### Do:
- **Do** keep the single dark felt theme; the black ground is the CLSI M02 reading condition, not a style preference.
- **Do** spend colour only on S / I / SDD / R and the olive flag; everything else stays in the felt and ink greys.
- **Do** pair every category colour with its letter and every flag with an icon and a sentence.
- **Do** set every millimetre, code and calibration value in Atkinson Hyperlegible Mono with tabular numerals.
- **Do** draw measurements on the photograph at true scale with non-scaling hairline strokes.
- **Do** divide regions with 1px rules and felt tonal steps, with 2px corners on rectangles and full circles only for round or optical things.
- **Do** trace every manual correction visibly and block the agent review while one is outstanding.
- **Do** ship every string in both ES and EN, and keep both languages fitting the same layout.
- **Do** set dynamic styles through the CSSOM (`element.style`, custom properties) so the CSP never needs `unsafe-inline`.
- **Do** honour reduced motion: draw-in, fades and transitions collapse to an instant final state.

### Don't:
- **Don't** add a light theme or white cards.
- **Don't** show a quality flag in resistant red, or use any category hue as a brand or status accent.
- **Don't** add box shadows, glows, or floating panels.
- **Don't** introduce a blue accent, a sidebar dashboard, or neon "AI" styling.
- **Don't** add inline `style` attributes or inline `<style>` blocks in the HTML.
- **Don't** stack small uppercase lines above headlines; the uppercase label style belongs only to field labels and group headings.
