# Colour tokens (feature 005, T521)

The re-derived palette. Written by `product-designer`; the values here are applied **verbatim** by
T521's implementer into `packages/design-system/tokens/color.json`, who invents nothing. Where this
file states a hex, that hex ships; where it states a ratio, that ratio is what T526 must measure.

**The task this closes**, recorded so a later reader does not have to reconstruct it:

> Dispatch `product-designer` to re-derive `packages/design-system/tokens/color.json` (FR-001a,
> FR-005, SC-001a, research D6). Every token ends with a record of either its derivation or the
> reason for retaining it — silence is not a third option — and every semantic role declares the
> surfaces it may be painted on, because a role used on a surface it does not declare is a defect
> whether or not the pair passes. Excluded and recorded as retained: the eight `player-*` fills and
> their `-contrast` inks. The brief is the art direction the spec fixes — warm parchment, stone,
> muted gold, restrained — and the method is one lightness ramp decided across the whole ramp, not
> eight more per-token darkenings.

**Scope.** Colour only. Typography (`font.json`, the typeface question, research D6a) is T523 and is
not decided here. No key is added and none removed: `link` / `link-hover` / `link-visited` are
T522's, and they enter the table the same way, against the surfaces they declare.

Measured ratios and the gap-register closures live in [`README.md`](./README.md) — the project's
ledger for both — and are **referenced, not restated**, once T526 carries them there. Until T526
runs, section 7 below is the only place the new numbers exist; it is the source T526 transcribes.

---

## 1. What was wrong, in one paragraph

The register's own history is the evidence. Three separate contrast defects (DS-1, DS-2, T038a,
T034c) were each fixed by darkening one colour inside its own hue until it cleared a floor. The
result is recorded in `README.md` in one sentence: _"the dark theme is comfortable and the light
theme is tight."_ Light `warning` on `surface-raised` cleared 4.5:1 by **two hundredths**. Light
`border` on `surface` measured **1.6:1** and was usable only as decoration. And DS-10 —
`focus-ring` on `accent`, 1.38:1 light and 1.21:1 dark — exists because `focus-ring` was derived
against page surfaces and never against the accent-filled controls it also paints on. Four defects,
one cause: **there was no ramp.** Each token was a local answer to a local complaint.

This re-derivation makes one lightness decision per theme, across the whole ramp, and lets every
token fall out of it. The character does not move (spec Risk 10: values are re-derived, the
character is not); the margins do.

---

## 2. The brief, unchanged

Warm parchment, stone, muted gold. Restrained rather than ornamental. Every neutral carries a warm
cast (hue 35–45°); the palette's only cool notes are `info` and `focus-ring`, and they are cool on
purpose — see §3.4. Nothing here reuses a Microsoft asset (constitution X); the eight canonical
player colours are licensed and recorded by feature 004 and are **excluded** from the re-derivation
(§8).

And the constraint that outranks atmosphere: **this is a data tool.** Number legibility and
information density come before decoration. Where the ramp had a choice between a prettier parchment
and a legible one, it chose the legible one — most visibly in `border`, whose real job is separating
rows of ratings in `MatchRow`'s table, not decorating a card.

---

## 3. Method — one ramp per theme, three bands

Each theme is a ramp with **stated CIE L\* steps**, derived once and then measured. Three bands, and
every token sits on one of them:

| Band          | What it holds                                                                   |
| ------------- | ------------------------------------------------------------------------------- |
| **Surfaces**  | `surface-sunken`, `background`, `surface`, `surface-raised`                     |
| **Inks**      | `text-primary`, `text-secondary`, `text-disabled`, and the two line roles       |
| **Chromatic** | `accent` (+ hover/active), `success`, `warning`, `danger`, `info`, `focus-ring` |

L\* below is CIE lightness computed from the same WCAG relative luminance the contrast formula uses,
so the two are the same measurement expressed twice — the ramp is not a separate opinion about the
values.

### 3.1 The surface ramp

**One rule, both themes**: `surface-sunken` → `background` → `surface` → `surface-raised` is a
monotonic ramp of _lift_, moving away from the page's base tone toward the theme's own light pole.
Sunken is always the darkest surface; raised is always the lightest.

| Surface          | Light L\* | Light hex | Dark L\* | Dark hex  | Step means                                          |
| ---------------- | --------- | --------- | -------- | --------- | --------------------------------------------------- |
| `surface-raised` | **98.7**  | `#fffbf2` | **16.7** | `#31281b` | lifted off the page — panel, callout, menu, tooltip |
| `surface`        | **96.0**  | `#faf3e4` | **11.8** | `#251e14` | the default bounded surface — card, row, input      |
| `background`     | **91.5**  | `#f0e6d0` | **7.6**  | `#1b160e` | the page itself                                     |
| `surface-sunken` | **85.3**  | `#e1d4b8` | **4.2**  | `#120e08` | recessed — well, track, disabled fill, hover row    |

Light steps: −2.7 / −4.5 / −6.2 L\*. Dark steps: −4.9 / −4.2 / −3.4 L\*. Both widen as they leave the
page, which is what makes `surface-sunken` a readable hover state on a row and `surface-raised` a
readable lift without a heavy shadow.

**The one ordering change, and it is the whole re-derivation in one move.** Today the light theme is
not a ramp at all: `surface` (`#fffaf0`) is _lighter_ than `surface-raised` (`#fff4dc`), which is
lighter than `background`. So the lifted surface was the theme's second-darkest, and every ink
painted on it — which is every `Callout` heading, every `Badge` tone, every `Menu` item, every
`Tooltip` — paid for that with its margin. That is why the four callout-heading pairs were the
tightest in the system and why `warning` cleared its floor by two hundredths. Making `surface-raised`
the lightest light surface returns that margin to every one of them at once, without moving a single
hue. It is also what makes light and dark the same rule instead of two.

**What it costs, stated.** A `Callout` and a `Menu` panel are now very slightly _lighter_ than the
card they sit near rather than slightly darker (98.7 vs 96.0 — 2.7 L\*). Every raised surface in this
system already carries a border, a stripe or a shadow (`Callout` `border-l-2`, `Menu` `border-border`

- `shadow-overlay`, `Tooltip` `border-border`, `SignInScreen` `shadow-raised`), so none of them
  depends on the fill alone to be read as a bounded unit. This is checked as an acceptance criterion in
  §9.

### 3.2 The ink ramp

Three inks per theme, at stated distances from each other so that "primary / secondary / inactive" is
a hierarchy a reader can see rather than three colours that happen to differ.

| Ink              | Light L\* | Light hex | Dark L\* | Dark hex  | Floor it owes                                      |
| ---------------- | --------- | --------- | -------- | --------- | -------------------------------------------------- |
| `text-primary`   | **10.2**  | `#241a0e` | **91.9** | `#f2e7ce` | 4.5:1 on all four surfaces (gets ≥11)              |
| `text-secondary` | **32.7**  | `#5c4a30` | **74.3** | `#c6b593` | 4.5:1 on all four surfaces                         |
| `text-disabled`  | **49.6**  | `#847459` | **51.3** | `#8a7859` | exempt (WCAG 1.4.3, inactive) — held to 3:1 anyway |

Light spacing: 22.5 then 16.9 L\*. Dark spacing: 17.6 then 23.0 L\*. Deliberately symmetric: the two
themes now put the same perceptual distance between the same two roles, which is what "the light
theme resembles the dark theme" means concretely.

**`text-disabled` is held to 3:1 even though it is exempt.** WCAG lets an inactive control's label
fail; a data tool should still let a reader _read_ the label of the button they cannot press, because
in this product a disabled control is frequently the one carrying the explanation (`ArchivalControl`,
`AccountErasurePanel`). Light 3.10:1 on `surface-sunken` (its real fill), dark 4.50:1. It remains
unmistakably weaker than `text-secondary` (5.78 / 9.55 on the same surface), so the hierarchy still
reads. This raises it from today's 2.6:1.

**The two line roles**, on the same band because a line is an ink:

| Role            | Light L\* | Light hex | Dark L\* | Dark hex  | Floor it owes                               |
| --------------- | --------- | --------- | -------- | --------- | ------------------------------------------- |
| `border`        | **61.6**  | `#a89268` | **40.1** | `#6e5c3b` | none (decorative) — held to ≥2.4 everywhere |
| `border-strong` | **45.2**  | `#7d6934` | **57.4** | `#9e8757` | 3:1 non-text (WCAG 1.4.11)                  |

`border` is where the data-tool constraint bites hardest, so it is derived against its _hardest_ real
background rather than its most flattering one: `background`, because that is what `MatchRow`'s 1280
table paints its row separators on, and a row separator in a ratings table is load-bearing, not
decoration. Setting it at 2.43:1 there yields 2.72:1 on `surface` — the headline number, up from
1.6:1 — and 2.05:1 on `surface-sunken` (the disabled control's boundary, the only place it is allowed
to be faint, because a disabled boundary _should_ recede).

`border-strong` is derived against `surface-sunken`, its tightest adjacency (`PlayerAvatar`'s frame,
`PlayerColourSwatch`'s neutral chip, a `Button` at `active:`), so it clears 3:1 on all four surfaces
rather than on three of them.

### 3.3 The chromatic band — one lightness, hue is the only free variable

This is the decision that replaces eight per-token darkenings. **Every chromatic role in a theme sits
in one narrow L\* band.** Its lightness is fixed by the band; only its hue distinguishes it.

| Theme     | Band          | Members, by L\*                                                                                   |
| --------- | ------------- | ------------------------------------------------------------------------------------------------- |
| **Light** | **L\* 33–41** | `focus-ring` 33.2 · `info` 35.8 · `success` 36.0 · `danger` 36.2 · `warning` 36.7 · `accent` 40.8 |
| **Dark**  | **L\* 65–71** | `focus-ring` 64.9 · `info` 67.8 · `danger` 68.1 · `warning` 69.0 · `success` 69.2 · `accent` 70.9 |

The band is chosen so that its _lower_ edge clears 4.5:1 against the theme's tightest declared
surface for any member of it. Light: 4.5:1 against `surface-sunken` (L\* 85.3) requires L\* ≤ ~41, and
the band's top member (`accent`, 40.8) is exactly there. Dark: 4.5:1 against `surface-raised`
(L\* 16.7) requires L\* ≥ ~48, and the band sits well above it, which is why the dark theme has always
been comfortable and stays so.

**One band means one place to look when a floor moves.** If `surface-raised` ever changes, the whole
chromatic band moves together by the same amount — which is the property the old palette did not
have, and the reason three defects were fixed three separate times.

Hues, stated so a later reader can extend the band without collapsing two roles onto each other:

| Role         | Hue (light / dark) | Character                                        |
| ------------ | ------------------ | ------------------------------------------------ |
| `danger`     | 7° / 11°           | iron oxide — the palette's red, never a pure red |
| `warning`    | 28° / 26°          | burnt amber — deliberately redder than `accent`  |
| `accent`     | 38° / 39°          | muted gold/bronze — the product's emphasis       |
| `success`    | 118° / 105°        | moss, desaturated — never a signal green         |
| `info`       | 187° / 191°        | slate teal — calm, informational                 |
| `focus-ring` | 214° / 213°        | azure, the most saturated value in the system    |

`warning` and `accent` are 10° apart and were 8° apart before; they are now separated by lightness as
well (36.7 vs 40.8 light; 69.0 vs 70.9 dark) and by chroma, and they never occupy the same role —
`accent` is an emphasis fill and a link ink, `warning` is a `Callout` stripe and heading with a text
label beside it. Rule 4 in `README.md` (colour is never the only carrier of meaning) is what makes
that adjacency safe, and it holds unchanged.

### 3.4 The two cool roles, and why they are two

`info` and `focus-ring` are the same value today — `#2f5f73` light, `#6fa8c0` dark — in both themes.
That is one value under two names, and this repository's stated law is that a fact written twice goes
stale in one copy: changing `info` because a callout reads poorly would silently move every focus
ring in the product. **They are separated here.** `focus-ring` becomes the system's most saturated
value (azure, 214°) because a focus ring is the one mark that must never be mistaken for decoration;
`info` becomes a calmer slate teal (187°). They are 27° apart and differ in chroma, so they do not
read as a mistake, and neither can now drag the other.

### 3.5 The interaction steps on `accent`

Three distinct fills, never collapsed onto one another (this is DS-1's closure and it is kept):

| Step            | Light L\* | Dark L\* | Rule                                                                        |
| --------------- | --------- | -------- | --------------------------------------------------------------------------- |
| `accent`        | 40.8      | 70.9     | rest                                                                        |
| `accent-hover`  | 34.6      | 78.3     | one step (~6–7 L\*) **away from the page**, in the theme's own direction    |
| `accent-active` | 27.8      | 63.6     | **darker than rest in both themes** — a press is ink going into the surface |

Hover follows the theme (darker on parchment, lighter on a dark page: the control comes toward the
reader). Active is darker in _both_, which is the one place the two themes deliberately differ in
direction. The alternative — active continuing past hover, so the dark theme's pressed state is
lighter than its hover state — reads as _more_ lifted rather than pressed, which is the opposite of
what a press means. Stated here so it is not read as an oversight.

### 3.6 One light ink and one dark ink per theme

Every `-contrast` token — the ink placed _on_ a filled role — resolves to one of exactly two values
per theme: the theme's lightest surface, or the theme's page tone. It is not a per-hue decision.

- **Light**: the light ink is `#fffbf2` (= `surface-raised`). Every light `-contrast` uses it, and
  every one clears **≥ 6:1** on its own fill.
- **Dark**: the dark ink is `#1b160e` (= `background`). Every dark `-contrast` uses it, and every one
  clears **≥ 6.3:1** on its own fill.

This retires four hand-tinted near-blacks (`#241a08`, `#12190f`, `#101a1e`, and light `#f4ecd8`) that
were four separate decisions with no measurable benefit — all four already cleared their floors by a
wide margin, and four values is four things to keep true. It also fixes a live defect the register
already flagged: light `warning-contrast` on `warning` measured **3.47:1**, under even the 3:1
non-text floor, with `README.md`'s note that it "must be re-derived before anything is built against
it." It is now **7.06:1**.

---

## 4. The complete `color.json`

This is the file, in full. Transcribe it. Key order is preserved from the current file; no key is
added and none removed.

```json
{
  "$comment": "Semantic colour tokens. Re-derived by feature 005 T521 as one lightness ramp per theme — surfaces, inks, and a single chromatic band whose members differ only in hue. The full derivation, the per-token record, and each role's declared surfaces are in packages/design-system/specs/color-tokens.md; $rationale below carries the one-line form. Same names in both themes — a component never knows which is active (design-system skill, 'Tokens'). Warm parchment/bronze palette evoking the era without reusing any Microsoft asset (constitution X); the eight player-* fills and their -contrast inks are canonical game colours, theme-invariant, and are retained unchanged (packages/design-system/specs/game-asset-tokens.md). Edit here, then run `pnpm --filter design-system tokens:build`.",
  "light": {
    "background": "#f0e6d0",
    "surface": "#faf3e4",
    "surface-raised": "#fffbf2",
    "surface-sunken": "#e1d4b8",
    "border": "#a89268",
    "border-strong": "#7d6934",
    "text-primary": "#241a0e",
    "text-secondary": "#5c4a30",
    "text-disabled": "#847459",
    "text-inverse": "#f0e6d0",
    "accent": "#7d5a1c",
    "accent-hover": "#6a4c15",
    "accent-active": "#573d0f",
    "accent-contrast": "#fffbf2",
    "success": "#365e33",
    "success-contrast": "#fffbf2",
    "warning": "#85460e",
    "warning-contrast": "#fffbf2",
    "danger": "#93372a",
    "danger-contrast": "#fffbf2",
    "info": "#245c63",
    "info-contrast": "#fffbf2",
    "focus-ring": "#1f4e8c",
    "overlay": "rgb(36 26 14 / 55%)",
    "player-1": "#405BFF",
    "player-1-contrast": "#fffaf0",
    "player-2": "#FF0000",
    "player-2-contrast": "#000000",
    "player-3": "#00FF00",
    "player-3-contrast": "#000000",
    "player-4": "#FFFF00",
    "player-4-contrast": "#000000",
    "player-5": "#00FFFF",
    "player-5-contrast": "#000000",
    "player-6": "#FF57B3",
    "player-6-contrast": "#000000",
    "player-7": "#797979",
    "player-7-contrast": "#000000",
    "player-8": "#FF9600",
    "player-8-contrast": "#000000"
  },
  "dark": {
    "background": "#1b160e",
    "surface": "#251e14",
    "surface-raised": "#31281b",
    "surface-sunken": "#120e08",
    "border": "#6e5c3b",
    "border-strong": "#9e8757",
    "text-primary": "#f2e7ce",
    "text-secondary": "#c6b593",
    "text-disabled": "#8a7859",
    "text-inverse": "#1b160e",
    "accent": "#d6a64c",
    "accent-hover": "#e5bc6c",
    "accent-active": "#c4913a",
    "accent-contrast": "#1b160e",
    "success": "#84b673",
    "success-contrast": "#1b160e",
    "warning": "#e89555",
    "warning-contrast": "#1b160e",
    "danger": "#e5907e",
    "danger-contrast": "#1b160e",
    "info": "#74aebe",
    "info-contrast": "#1b160e",
    "focus-ring": "#6fa0e0",
    "overlay": "rgb(0 0 0 / 65%)",
    "player-1": "#405BFF",
    "player-1-contrast": "#fffaf0",
    "player-2": "#FF0000",
    "player-2-contrast": "#000000",
    "player-3": "#00FF00",
    "player-3-contrast": "#000000",
    "player-4": "#FFFF00",
    "player-4-contrast": "#000000",
    "player-5": "#00FFFF",
    "player-5-contrast": "#000000",
    "player-6": "#FF57B3",
    "player-6-contrast": "#000000",
    "player-7": "#797979",
    "player-7-contrast": "#000000",
    "player-8": "#FF9600",
    "player-8-contrast": "#000000"
  }
}
```

### 4a. The per-token record inside the JSON, and where it may go

FR-001a and SC-001a require every token to carry a record. **It cannot go inside the `light` / `dark`
blocks.** `build-tokens.mjs`'s `readJson` strips `$`-prefixed keys **at the top level only**
(`build-tokens.mjs` lines 40–45), and `colorVars` then iterates `color[theme]` directly (line 92) — so
a `$comment` key inside a theme block would be emitted as a real CSS custom property. Two safe
routes, and the second is the one to take:

1. Change `colorVars` to filter `$`-prefixed keys as well. Rejected: it changes the generator to
   accommodate documentation, and every other family would then need the same treatment.
2. **Add a top-level `$rationale` object**, keyed `light` / `dark`, one line per token. `readJson`
   already strips it, so no generator change is needed, and it is the same shape as
   `elevation.json`'s `$meaning`, whose one-line form sits in the JSON while the full reasoning lives
   in `README.md`. That precedent is already recorded in `README.md`'s Elevation section.

Take route 2. The implementer adds this block **after** `$comment` and **before** `light`. Its lines
are the one-line record; this file is the derivation, and the two do not restate each other's
numbers.

```json
  "$rationale": {
    "$comment": "One line per token, FR-001a/SC-001a: derived (with its ramp step) or retained (with the reason). The full derivation, the measured ratios and each role's declared surfaces are in packages/design-system/specs/color-tokens.md. Stripped by build-tokens.mjs's top-level $-filter; never emitted as a variable.",
    "light": {
      "background": "derived: surface ramp L* 91.5, the page tone; warm parchment at hue 42.",
      "surface": "derived: surface ramp L* 96.0, one lift step above the page.",
      "surface-raised": "derived: surface ramp L* 98.7, the lightest surface. Reordered above `surface` — this is the single move that returns margin to every ink painted on a raised surface.",
      "surface-sunken": "derived: surface ramp L* 85.3, one step below the page; well, track, disabled fill, row hover.",
      "border": "derived: ink band, L* 61.6. Set against `background` at 2.4:1 because a MatchRow table separator is load-bearing in a data tool; yields 2.7:1 on `surface`, up from 1.6:1.",
      "border-strong": "derived: ink band, L* 45.2. Set against `surface-sunken`, its tightest adjacency, so it clears the 3:1 non-text floor on all four surfaces (3.6-5.2:1).",
      "text-primary": "derived: ink ramp L* 10.2; >=11.6:1 on every declared surface.",
      "text-secondary": "derived: ink ramp L* 32.7, 22.5 below primary; 5.8:1 on surface-sunken, up from 4.7:1.",
      "text-disabled": "derived: ink ramp L* 49.6. Exempt from AA (WCAG 1.4.3, inactive) but held to 3:1 on its real fill, because a disabled control here often carries the explanation.",
      "text-inverse": "derived: the page tone, reused as the ink for a `text-primary`-filled region. No call site today; see color-tokens.md section 6 for the standing obligation.",
      "accent": "derived: chromatic band L* 40.8, hue 38 — muted gold. Band top, so it is the member that fixes the band's ceiling.",
      "accent-hover": "derived: one interaction step (-6.2 L*) away from the page.",
      "accent-active": "derived: two interaction steps (-13.0 L*); a press reads as ink into the surface, in both themes.",
      "accent-contrast": "derived: the light theme's one light ink (= surface-raised); 6.1:1 on accent, 9.8:1 on accent-active.",
      "success": "derived: chromatic band L* 36.0, hue 118 — moss, desaturated; never a signal green.",
      "success-contrast": "derived: the light theme's one light ink; 7.3:1 on success.",
      "warning": "derived: chromatic band L* 36.7, hue 28 — burnt amber, redder than accent. 7.1:1 on surface-raised, against a 4.5 floor it previously cleared by two hundredths.",
      "warning-contrast": "derived: the light theme's one light ink; 7.1:1 on warning, replacing a 3.47:1 pair the register flagged as unbuildable.",
      "danger": "derived: chromatic band L* 36.2, hue 7 — iron oxide, never a pure red.",
      "danger-contrast": "derived: the light theme's one light ink; 7.2:1 on danger.",
      "info": "derived: chromatic band L* 35.8, hue 187 — slate teal. Separated from focus-ring, which it used to equal value-for-value.",
      "info-contrast": "derived: the light theme's one light ink; 7.3:1 on info.",
      "focus-ring": "derived: chromatic band L* 33.2, hue 214 — the system's most saturated value, because a ring must never read as decoration. Clears 3:1 on all four surfaces (5.7-8.2:1). Does NOT declare accent: see color-tokens.md section 5.",
      "overlay": "derived: text-primary at 55%. A scrim carries no foreground and owes no pair; what it owes is that the dialog above it reads (research D9).",
      "player-1": "retained: canonical game colour, color_id 1, theme-invariant (game-asset-tokens.md).",
      "player-1-contrast": "retained: measured 4.8:1 ink on Blue; the one fill needing the light ink.",
      "player-2": "retained: canonical game colour, color_id 2, theme-invariant.",
      "player-2-contrast": "retained: measured 5.2:1 ink on Red.",
      "player-3": "retained: canonical game colour, color_id 3, theme-invariant.",
      "player-3-contrast": "retained: measured 15.3:1 ink on Green.",
      "player-4": "retained: canonical game colour, color_id 4, theme-invariant.",
      "player-4-contrast": "retained: measured 19.5:1 ink on Yellow.",
      "player-5": "retained: canonical game colour, color_id 5, theme-invariant.",
      "player-5-contrast": "retained: measured 16.7:1 ink on Teal.",
      "player-6": "retained: canonical game colour, color_id 6, theme-invariant.",
      "player-6-contrast": "retained: measured 7.2:1 ink on Purple.",
      "player-7": "retained: canonical game colour, color_id 7, theme-invariant.",
      "player-7-contrast": "retained: measured 4.8:1 ink on Grey, the tightest fill.",
      "player-8": "retained: canonical game colour, color_id 8, theme-invariant.",
      "player-8-contrast": "retained: measured 9.6:1 ink on Orange."
    },
    "dark": {
      "background": "derived: surface ramp L* 7.6, the page tone.",
      "surface": "derived: surface ramp L* 11.8, one lift step above the page.",
      "surface-raised": "derived: surface ramp L* 16.7, the lightest surface; the theme's tightest ink backdrop, so it sets the chromatic band's floor.",
      "surface-sunken": "derived: surface ramp L* 4.2, one step below the page.",
      "border": "derived: ink band L* 40.1, set to match the light theme's separator strength (2.6:1 on surface, against light's 2.7:1).",
      "border-strong": "derived: ink band L* 57.4; 4.2-5.6:1 across the four surfaces, clearing the 3:1 non-text floor on all of them.",
      "text-primary": "derived: ink ramp L* 91.9; >=11.8:1 on every declared surface.",
      "text-secondary": "derived: ink ramp L* 74.3, 17.6 below primary; 8.9:1 on `background`, the pair ProfileSummary draws and the table never carried.",
      "text-disabled": "derived: ink ramp L* 51.3; 3.4:1 on surface-raised, 4.5:1 on surface-sunken. Exempt from AA, held to 3:1 anyway.",
      "text-inverse": "derived: the page tone, reused as the ink for a `text-primary`-filled region. No call site today.",
      "accent": "derived: chromatic band L* 70.9, hue 39 — muted gold.",
      "accent-hover": "derived: one interaction step (+7.4 L*) away from the page.",
      "accent-active": "derived: darker than rest (-7.3 L*), the one place the two themes differ in direction; a press reads as pressed, not more lifted.",
      "accent-contrast": "derived: the dark theme's one dark ink (= background); 8.1:1 on accent, 6.4:1 on accent-active.",
      "success": "derived: chromatic band L* 69.2, hue 105 — moss.",
      "success-contrast": "derived: the dark theme's one dark ink; 8.2:1 on success.",
      "warning": "derived: chromatic band L* 69.0, hue 26 — burnt amber, moved off gold so it no longer reads as accent.",
      "warning-contrast": "derived: the dark theme's one dark ink; 7.6:1 on warning.",
      "danger": "derived: chromatic band L* 68.1, hue 11; 6.0:1 on surface-raised, up from the 4.6:1 the register flagged as the tightest dark pair.",
      "danger-contrast": "derived: the dark theme's one dark ink; 7.4:1 on danger.",
      "info": "derived: chromatic band L* 67.8, hue 191 — slate teal.",
      "info-contrast": "derived: the dark theme's one dark ink; 7.3:1 on info.",
      "focus-ring": "derived: chromatic band L* 64.9, hue 213; clears 3:1 on all four surfaces (5.4-7.1:1). Does NOT declare accent: see color-tokens.md section 5.",
      "overlay": "retained: rgb(0 0 0 / 65%). The dark theme's own tones are too close to the page to darken it; a scrim must remove the page, so this is the one place the palette uses absolute black — the same reasoning game-asset-tokens.md used for the seven black player inks.",
      "player-1": "retained: canonical game colour, color_id 1, theme-invariant (game-asset-tokens.md).",
      "player-1-contrast": "retained: measured 4.8:1 ink on Blue; the one fill needing the light ink.",
      "player-2": "retained: canonical game colour, color_id 2, theme-invariant.",
      "player-2-contrast": "retained: measured 5.2:1 ink on Red.",
      "player-3": "retained: canonical game colour, color_id 3, theme-invariant.",
      "player-3-contrast": "retained: measured 15.3:1 ink on Green.",
      "player-4": "retained: canonical game colour, color_id 4, theme-invariant.",
      "player-4-contrast": "retained: measured 19.5:1 ink on Yellow.",
      "player-5": "retained: canonical game colour, color_id 5, theme-invariant.",
      "player-5-contrast": "retained: measured 16.7:1 ink on Teal.",
      "player-6": "retained: canonical game colour, color_id 6, theme-invariant.",
      "player-6-contrast": "retained: measured 7.2:1 ink on Purple.",
      "player-7": "retained: canonical game colour, color_id 7, theme-invariant.",
      "player-7-contrast": "retained: measured 4.8:1 ink on Grey, the tightest fill.",
      "player-8": "retained: canonical game colour, color_id 8, theme-invariant.",
      "player-8-contrast": "retained: measured 9.6:1 ink on Orange."
    }
  }
```

---

## 5. DS-10 — the focus ring, and the thing that turned out to be impossible

**The gap.** `focus-ring` on `accent` measures 1.38:1 light and 1.21:1 dark, both under WCAG 1.4.11's
3:1 non-text floor. `Button`'s `primary` variant and `DataExportPanel`'s download link both fill with
`accent` and ring with `focus-ring`. `tests/visual/focus-ring.spec.ts` measures the ring against the
focused element's **own** background (its `backgroundColor` walk, lines 339–359), so `accent` is the
surface as far as the gate is concerned, and four cases carry `test.fail()` waiting on this task.

**I could not fix it by choosing a better value, and this is provable rather than a matter of taste.**

In the light theme the ring must clear 3:1 against `surface-raised` (relative luminance 0.9666) and
against `accent` (0.1176). Writing `Lf` for the ring's relative luminance:

- against `surface-raised`, the ring must be darker: `(0.9666 + 0.05) / (Lf + 0.05) ≥ 3` → **`Lf ≤ 0.289`**
- against `accent`, the ring must be lighter: `(Lf + 0.05) / (0.1176 + 0.05) ≥ 3` → **`Lf ≥ 0.453`**

No value satisfies both. Going the other way — a ring _darker_ than `accent` — needs `Lf ≤ 0.006`,
essentially absolute black, and it then measures **1.86:1** against `accent-active`, so it fails on
the pressed state instead. The dark theme gives the same contradiction: `Lf ≥ 0.276` against
`surface-raised`, `Lf ≤ 0.107` against `accent`.

The cause is structural, not accidental: **in a light theme, `accent` must be dark enough to be legible
as text on parchment (4.5:1), which puts it deep in the ink band — and one ring colour cannot bridge a
near-white surface and a near-ink fill.** Making `accent` light enough to be bridged would make it
fail as an ink, which would break every `text-accent` call site and change what `accent` means.

**So the conclusion is the second one the brief allows: a per-surface reconsideration.**

> **`focus-ring` declares the four page surfaces and nothing else. An `accent`-filled control does
> not paint `focus-ring`; it rings _inward_ in `accent-contrast`, the ink it already carries.**

- `accent-contrast` on `accent` = **6.07:1 light / 8.07:1 dark**, on `accent-hover` 7.65 / 10.06, on
  `accent-active` 9.78 / 6.39. All far above the 3:1 non-text floor, in both themes, at rest, on hover
  and on press.
- The ring must be **inward** (`-outline-offset-2`, the shape `MatchRow`, `PlayerResultRow`,
  `FavouritesList` and `Menu`'s item already use), so that both of its adjacent colours are the accent
  fill. Drawn outward, a near-parchment ring would sit on the page at ~1.05:1 and be invisible — the
  same defect in a new direction.
- DS-10 then ceases to exist because the pair ceases to be drawn. That is exactly the mechanism FR-005
  asks for: a role declares its surfaces, and `accent` is not one of `focus-ring`'s.

**This is a values decision plus one component rule, and the rule is not optional.** If the
implementer applies the hexes and leaves `Button`'s `primary` and `DataExportPanel`'s download link
ringing with `outline-focus-ring outline-offset-2`, DS-10 survives the re-derivation. Two class
strings change:

| File                                                              | From                                                                   | To                                                                 |
| ----------------------------------------------------------------- | ---------------------------------------------------------------------- | ------------------------------------------------------------------ |
| `packages/design-system/src/components/Button/index.tsx`          | `primary` shares the shared `outline-focus-ring outline-offset-2` ring | `primary` overrides to `outline-accent-contrast -outline-offset-2` |
| `packages/design-system/src/components/DataExportPanel/index.tsx` | `focus-visible:outline-focus-ring` + `outline-offset-2`                | `focus-visible:outline-accent-contrast` + `-outline-offset-2`      |

**The other rings are unaffected.** The package's non-test source carries **fourteen**
`outline-focus-ring` declarations. Twelve are untouched. The thirteenth is `Button`'s shared ring,
which keeps `focus-ring` for `secondary`, `ghost` and `destructive` and is overridden only for
`primary`; the fourteenth is `DataExportPanel`'s, replaced outright. Every ring that still paints
`focus-ring` sits on a page surface, where it now clears 3:1 with 5.4–8.2:1 of margin in both themes.

**What T526 owes**, stated so the handoff is unambiguous: add `accent-contrast` on
`accent` / `accent-hover` / `accent-active` as the focus-indicator rows (they are already in the table
as the _ink_ rows and the numbers move, so re-measure rather than add); add `focus-ring` against all
four page surfaces in both themes; **remove the `focus-ring`-on-`accent` rows entirely** rather than
updating them, because no component paints that pair any more; delete `knownContrastFailure` from the
two `Control` entries in `tests/visual/focus-ring.spec.ts` together with the `test.fail()` it drives;
and close DS-10 in the gap register naming this section as the decision.

---

## 6. Role → declared surfaces

FR-005: a role painted on a surface it does not declare is a defect **whether or not the pair passes
contrast**. This table is the declaration. It is derived by the pairing convention already written in
`README.md` — _"a row names a foreground and the background the component that carries it actually
paints behind it"_ — by reading each component, per file, not by assuming which surface is
conventionally "the" one for a token.

**A role's declared surfaces are one list, valid in both themes.** Components are theme-blind
(rule 6), so a surface a role may paint on in dark but not in light is not a surface it declares. The
tighter theme decides, and it is always light. `accent` is the case: legible on `surface-sunken` in
dark (8.63:1) and not in light (4.27:1), so `surface-sunken` is not declared.

`S` = `surface`, `SR` = `surface-raised`, `SS` = `surface-sunken`, `BG` = `background`.

| Role               | Means                                            | Declared surfaces                                          | Floor              | Real call sites that fix the list                                                                                                                                                                                                      |
| ------------------ | ------------------------------------------------ | ---------------------------------------------------------- | ------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `text-primary`     | the reader's primary text                        | `BG` `S` `SR` `SS`                                         | 4.5                | headings on route `bg-background`; `Callout` body on `SR`; `Button` secondary label on `S`; `Button` `active:bg-surface-sunken`                                                                                                        |
| `text-secondary`   | supporting and explanatory text                  | `BG` `S` `SR` `SS`                                         | 4.5                | `ProfileSummary` id/freshness on `BG`; `MatchRow` metadata on `S`; `Tooltip` on `SR`; `Badge` neutral on `SS`                                                                                                                          |
| `text-disabled`    | the label of an inactive control                 | `BG` `S` `SR` `SS`                                         | exempt (held to 3) | `Button` disabled on `SS`; `Menu` disabled item on `SR`; `Menu` disabled trigger on `S`                                                                                                                                                |
| `text-inverse`     | ink for a `text-primary`-filled region           | `text-primary` as fill                                     | 4.5                | **none today** — see the note below                                                                                                                                                                                                    |
| `border`           | a decorative separator or an inactive boundary   | `BG` `S` `SR` `SS`                                         | none               | `MatchRow` table `border-b` on `BG`; `Footer` `border-t` on `BG`; `Menu` panel and `Tooltip` on `SR`; `Button` `disabled:border-border` on `SS`                                                                                        |
| `border-strong`    | the boundary of an interactive control or a mark | `BG` `S` `SR` `SS`                                         | 3                  | `ConsentStep` decline control on `BG`; `Menu` trigger and `Button` secondary on `S`; secondary `Button` inside a `Callout` on `SR`; `PlayerAvatar` / `PlayerColourSwatch` frame around `SS`                                            |
| `accent`           | the product's emphasis, as fill or ink           | `BG` `S` `SR`                                              | 4.5                | `SiteHeader` current-tab rule on `S`; `Badge` accent tone on `SR`; inline links on `BG`/`S`. **Not `SS`**: 4.27:1 in light                                                                                                             |
| `accent-hover`     | that emphasis, hovered                           | `BG` `S` `SR`                                              | 4.5                | `Footer` and `PrivacyNotice` link hover on `BG`; as a fill under `accent-contrast`                                                                                                                                                     |
| `accent-active`    | that emphasis, pressed                           | `BG` `S` `SR`                                              | 4.5                | `Badge` accent tone (light) on `SR`; link active on `BG`; as a fill under `accent-contrast`                                                                                                                                            |
| `accent-contrast`  | ink on an accent fill, **and its focus ring**    | `accent` `accent-hover` `accent-active`                    | 4.5                | `Button` primary label; `DataExportPanel` download link label; the inward focus ring on both (§5)                                                                                                                                      |
| `success`          | a favourable outcome                             | `BG` `S` `SR` `SS`                                         | 4.5                | `MatchRow` win text on `S` and on `SS` (row hover); `ProfileSummary` delta on `BG`; `Callout`/`Badge` on `SR`; the win bar fill over the `SS` track                                                                                    |
| `success-contrast` | ink on a success fill                            | `success`                                                  | 4.5                | none today; derived so the fill is buildable                                                                                                                                                                                           |
| `warning`          | a caution the reader should act on               | `SR`                                                       | 4.5                | `Callout` stripe + heading and `Badge` warning tone, both unconditionally `bg-surface-raised`                                                                                                                                          |
| `warning-contrast` | ink on a warning fill                            | `warning`                                                  | 4.5                | none today; derived so the fill is buildable (it was not: 3.47:1)                                                                                                                                                                      |
| `danger`           | a destructive action or an unfavourable outcome  | `BG` `S` `SR` `SS`                                         | 4.5                | `MatchRow` loss text on `S` and `SS`; `ProfileSummary` delta on `BG`; `Callout`/`Badge` on `SR`; `Button` destructive `border-danger` and `ThirdPartyObjectionForm`'s error border, both on `S`; the loss bar fill over the `SS` track |
| `danger-contrast`  | ink on a danger fill                             | `danger`                                                   | 4.5                | none today; derived so the fill is buildable                                                                                                                                                                                           |
| `info`             | a neutral statement of fact                      | `SR`                                                       | 4.5                | `Callout` stripe + heading and `Badge` info tone, both unconditionally `bg-surface-raised`                                                                                                                                             |
| `info-contrast`    | ink on an info fill                              | `info`                                                     | 4.5                | none today; derived so the fill is buildable                                                                                                                                                                                           |
| `focus-ring`       | where keyboard focus is                          | `BG` `S` `SR` `SS`                                         | 3                  | the twelve untouched `outline-focus-ring` declarations plus `Button`'s ring for its non-primary variants, all on a page surface; `UploadControl`'s drag-over `border-focus-ring` around an `SS` fill. **Not `accent`** — §5            |
| `overlay`          | a scrim that removes the page beneath a modal    | painted **over** `BG` `S` `SR` `SS`; carries no foreground | none               | `Dialog` backdrop, `Menu`'s mobile backdrop. Owes no pair: nothing is read against a scrim, and what it owes is that the dialog above it reads — `text-primary` on `surface`, already measured (research D9)                           |
| `player-1..8`      | a player's in-game colour                        | any surface, inside a `border-strong` frame                | —                  | exempt from this table: a canonical fill, not a pairing role (§8)                                                                                                                                                                      |

**Three notes this table would otherwise leave implied.**

1. **`text-inverse` has no call site.** It is retained rather than derived-into-use: the palette needs
   a name for "ink on an inverted block" and removing a token is a breaking change that belongs to
   `GOVERNANCE.md`'s deprecation procedure, not to a re-derivation. Its declared surface is a
   `text-primary` fill (13.8:1 light, 14.6:1 dark). **Standing obligation**: if it still has no call
   site when feature 005 closes, it is a removal candidate and `GOVERNANCE.md`'s deprecation procedure
   decides it. It must not acquire a call site without that pair entering the measured table first
   (admission test step 5).
2. **`warning` and `info` declare `surface-raised` only** because `Callout` is unconditionally
   `bg-surface-raised` and `Badge`'s tones are too — that is T034c's finding and it is kept. They are
   comfortably legible elsewhere (light `warning` 6.5:1 on `S`, 5.8:1 on `BG`; light `info` 6.8:1 on
   `S`, 6.1:1 on `BG`) and §7's footnote records those numbers, but a role does not declare a surface
   because it _could_ — it declares the ones a component paints. Widening the list is the admission
   test's job, not a re-derivation's.
3. **`success` and `danger` are the only chromatic roles that declare all four surfaces**, because
   they are the only ones a data row paints: `MatchRow` puts win/loss text on `bg-surface` and hovers
   the row to `bg-surface-sunken` underneath that same text, and `ProfileSummary` puts rating deltas
   straight on `bg-background`. Both were previously measured against `surface` and `surface-raised`
   only.

**Carried forward, not introduced here**: `ProfileSummary`'s win/loss bar paints `success` and
`danger` adjacent to each other, and the two sit at the same band lightness (L\* 36.0 and 36.2), so
they are distinguished by hue alone at that one boundary. The percentage label beside the bar is what
satisfies rule 4 today. This was true of the previous palette too and is not made worse; it is
recorded so `profile-summary.md`'s retrofit does not remove the label without noticing what it was
carrying.

---

## 7. The measured pairs, and the four this task was set

Computed with the WCAG 2.2 relative-luminance formula — the same one `build-tokens.test.mjs` and
`tests/visual/focus-ring.spec.ts` use — from the hexes in §4, rounded to two decimals where the margin
is the point and one otherwise. **T526 re-measures all of these and transcribes them into
`README.md`; these are the values it must reproduce.** A disagreement is a transcription error in §4,
and §4 wins.

### 7.1 The four named problems

| Pair                                  | Floor | Before                | **After**                                                   | Margin |
| ------------------------------------- | ----- | --------------------- | ----------------------------------------------------------- | ------ |
| light `warning` on `surface-raised`   | 4.5   | 4.52 (two hundredths) | **7.06**                                                    | +2.56  |
| light `border` on `surface`           | none  | 1.6 ("decoration")    | **2.72**                                                    | +1.12  |
| light `focus-ring` on `accent`        | 3     | 1.38 (FAIL)           | **pair removed** — `accent-contrast` on `accent` = **6.07** | §5     |
| dark `focus-ring` on `accent`         | 3     | 1.21 (FAIL)           | **pair removed** — `accent-contrast` on `accent` = **8.07** | §5     |
| dark `text-secondary` on `background` | 4.5   | never measured        | **8.93**                                                    | +4.43  |

`border` on `background` — the `MatchRow` table's row separator, which is the reason `border` was
derived against `background` rather than `surface` — measures **2.43:1**, up from an unmeasured
~1.5:1. It carries no WCAG floor (a decorative separator is not a control boundary and never becomes
one; that is `border-strong`'s job, and rule 2 of §6's table is unchanged), so the bar here is visual:
a line a reader can see without looking for it.

### 7.2 Light theme

| Foreground         | Background               | Ratio | Verdict                                                                |
| ------------------ | ------------------------ | ----- | ---------------------------------------------------------------------- |
| `text-primary`     | `surface-raised`         | 16.5  | AAA                                                                    |
| `text-primary`     | `surface`                | 15.4  | AAA                                                                    |
| `text-primary`     | `background`             | 13.8  | AAA                                                                    |
| `text-primary`     | `surface-sunken`         | 11.6  | AAA                                                                    |
| `text-secondary`   | `surface-raised`         | 8.2   | AAA                                                                    |
| `text-secondary`   | `surface`                | 7.7   | AAA                                                                    |
| `text-secondary`   | `background`             | 6.8   | AA                                                                     |
| `text-secondary`   | `surface-sunken`         | 5.8   | AA (was 4.7, "thin margin")                                            |
| `text-disabled`    | `surface-raised`         | 4.4   | exempt (1.4.3, inactive); clears 3:1 by design                         |
| `text-disabled`    | `surface`                | 4.1   | exempt; clears 3:1                                                     |
| `text-disabled`    | `background`             | 3.6   | exempt; clears 3:1                                                     |
| `text-disabled`    | `surface-sunken`         | 3.1   | exempt; clears 3:1 — the real disabled-`Button` pair                   |
| `accent`           | `surface-raised`         | 6.0   | AA — `Badge` accent tone may now use `accent` in both themes           |
| `accent`           | `surface`                | 5.6   | AA                                                                     |
| `accent`           | `background`             | 5.0   | AA                                                                     |
| `accent-hover`     | `surface`                | 7.1   | AA                                                                     |
| `accent-active`    | `surface-raised`         | 9.7   | AA                                                                     |
| `accent-contrast`  | `accent`                 | 6.07  | AA — and the focus-ring pair for accent-filled controls (§5)           |
| `accent-contrast`  | `accent-hover`           | 7.65  | AA                                                                     |
| `accent-contrast`  | `accent-active`          | 9.78  | AA                                                                     |
| `warning`          | `surface-raised`         | 7.06  | AA — the real `Callout`/`Badge` heading pair                           |
| `info`             | `surface-raised`         | 7.3   | AA — the real `Callout`/`Badge` heading pair                           |
| `success`          | `surface-raised`         | 7.2   | AA — the real `Callout`/`Badge` heading pair                           |
| `danger`           | `surface-raised`         | 7.2   | AA — the real `Callout`/`Badge` heading pair                           |
| `success`          | `surface`                | 6.8   | AA — `MatchRow` win text                                               |
| `success`          | `surface-sunken`         | 5.1   | AA — `MatchRow` win text, row hovered                                  |
| `success`          | `background`             | 6.0   | AA — `ProfileSummary` delta                                            |
| `danger`           | `surface`                | 6.7   | AA — `MatchRow` loss text, `Button` destructive border                 |
| `danger`           | `surface-sunken`         | 5.1   | AA — `MatchRow` loss text, row hovered                                 |
| `danger`           | `background`             | 6.0   | AA — `ProfileSummary` delta                                            |
| `success-contrast` | `success`                | 7.3   | AA                                                                     |
| `warning-contrast` | `warning`                | 7.1   | AA (was 3.47, under even the non-text floor)                           |
| `danger-contrast`  | `danger`                 | 7.2   | AA                                                                     |
| `info-contrast`    | `info`                   | 7.3   | AA                                                                     |
| `focus-ring`       | `surface-raised`         | 8.2   | passes non-text 3:1                                                    |
| `focus-ring`       | `surface`                | 7.6   | passes non-text 3:1                                                    |
| `focus-ring`       | `background`             | 6.8   | passes non-text 3:1                                                    |
| `focus-ring`       | `surface-sunken`         | 5.7   | passes non-text 3:1 — `UploadControl` drag-over border                 |
| `border-strong`    | `surface-raised`         | 5.2   | passes non-text 3:1                                                    |
| `border-strong`    | `surface`                | 4.8   | passes non-text 3:1                                                    |
| `border-strong`    | `background`             | 4.3   | passes non-text 3:1 — `ConsentStep` decline control (was 3.16)         |
| `border-strong`    | `surface-sunken`         | 3.6   | passes non-text 3:1 — the `PlayerAvatar` frame's inner side            |
| `border`           | `surface-raised`         | 2.9   | decorative / inactive boundary only                                    |
| `border`           | `surface`                | 2.72  | decorative / inactive boundary only (was 1.6)                          |
| `border`           | `background`             | 2.43  | decorative — `MatchRow` table row separator                            |
| `border`           | `surface-sunken`         | 2.05  | inactive boundary — a disabled control's edge, deliberately faintest   |
| `text-inverse`     | `text-primary` (as fill) | 13.8  | AAA — no call site; recorded so admitting one is not a new measurement |

Measured but **not declared** (§6 note 2), recorded so widening the list later is arithmetic rather
than a re-derivation: light `warning` on `surface` 6.5, on `background` 5.8, on `surface-sunken` 4.9;
light `info` on `surface` 6.8, on `background` 6.1, on `surface-sunken` 5.1; light `accent` on
`surface-sunken` **4.27 — the reason `surface-sunken` is not declared for `accent`.**

### 7.3 Dark theme

| Foreground         | Background               | Ratio   | Verdict                                                           |
| ------------------ | ------------------------ | ------- | ----------------------------------------------------------------- |
| `text-primary`     | `surface-raised`         | 11.8    | AAA                                                               |
| `text-primary`     | `surface`                | 13.4    | AAA                                                               |
| `text-primary`     | `background`             | 14.6    | AAA                                                               |
| `text-primary`     | `surface-sunken`         | 15.7    | AAA                                                               |
| `text-secondary`   | `surface-raised`         | 7.2     | AAA                                                               |
| `text-secondary`   | `surface`                | 8.2     | AAA                                                               |
| `text-secondary`   | `background`             | **8.9** | AAA — **the pair the old table never carried** (`ProfileSummary`) |
| `text-secondary`   | `surface-sunken`         | 9.6     | AAA                                                               |
| `text-disabled`    | `surface-raised`         | 3.4     | exempt; clears 3:1                                                |
| `text-disabled`    | `surface`                | 3.9     | exempt; clears 3:1                                                |
| `text-disabled`    | `background`             | 4.2     | exempt; clears 3:1                                                |
| `text-disabled`    | `surface-sunken`         | 4.5     | exempt; clears 3:1 — the real disabled-`Button` pair              |
| `accent`           | `surface-raised`         | 6.5     | AA                                                                |
| `accent`           | `surface`                | 7.4     | AA                                                                |
| `accent`           | `background`             | 8.1     | AA                                                                |
| `accent-hover`     | `background`             | 10.1    | AAA                                                               |
| `accent-active`    | `background`             | 6.4     | AA                                                                |
| `accent-contrast`  | `accent`                 | 8.07    | AA — and the focus-ring pair for accent-filled controls (§5)      |
| `accent-contrast`  | `accent-hover`           | 10.06   | AAA                                                               |
| `accent-contrast`  | `accent-active`          | 6.39    | AA                                                                |
| `warning`          | `surface-raised`         | 6.1     | AA — the real `Callout`/`Badge` heading pair                      |
| `info`             | `surface-raised`         | 5.9     | AA — the real `Callout`/`Badge` heading pair                      |
| `success`          | `surface-raised`         | 6.2     | AA — the real `Callout`/`Badge` heading pair                      |
| `danger`           | `surface-raised`         | 6.0     | AA — was 4.6, the tightest dark pair in the old table             |
| `success`          | `surface`                | 7.0     | AA                                                                |
| `success`          | `surface-sunken`         | 8.2     | AA                                                                |
| `success`          | `background`             | 7.6     | AA                                                                |
| `danger`           | `surface`                | 6.8     | AA                                                                |
| `danger`           | `surface-sunken`         | 7.9     | AA                                                                |
| `danger`           | `background`             | 7.4     | AA                                                                |
| `success-contrast` | `success`                | 8.2     | AA                                                                |
| `warning-contrast` | `warning`                | 7.6     | AA                                                                |
| `danger-contrast`  | `danger`                 | 7.4     | AA                                                                |
| `info-contrast`    | `info`                   | 7.3     | AA                                                                |
| `focus-ring`       | `surface-raised`         | 5.4     | passes non-text 3:1                                               |
| `focus-ring`       | `surface`                | 6.1     | passes non-text 3:1                                               |
| `focus-ring`       | `background`             | 6.7     | passes non-text 3:1                                               |
| `focus-ring`       | `surface-sunken`         | 7.1     | passes non-text 3:1                                               |
| `border-strong`    | `surface-raised`         | 4.2     | passes non-text 3:1                                               |
| `border-strong`    | `surface`                | 4.8     | passes non-text 3:1                                               |
| `border-strong`    | `background`             | 5.2     | passes non-text 3:1                                               |
| `border-strong`    | `surface-sunken`         | 5.6     | passes non-text 3:1                                               |
| `border`           | `surface-raised`         | 2.3     | decorative / inactive boundary only                               |
| `border`           | `surface`                | 2.6     | decorative / inactive boundary only                               |
| `border`           | `background`             | 2.8     | decorative — table row separator                                  |
| `border`           | `surface-sunken`         | 3.0     | decorative                                                        |
| `text-inverse`     | `text-primary` (as fill) | 14.6    | AAA — no call site                                                |

**The asymmetry that `README.md` records — "the dark theme is comfortable and the light theme is
tight" — no longer holds, and that sentence should be rewritten by T526 rather than kept.** Every
light text pair now clears its floor by at least 1.2, the tightest being `text-secondary` on
`surface-sunken` at 5.8. The tightest pair in the whole system in either theme is now light
`accent` on `background` at 5.0. "Judge light first" is still good advice and should stay; the reason
it was true is gone.

---

## 8. The eight player colours and their inks — retained, unchanged

**Confirmed: all sixteen `player-*` values are byte-identical to the current `color.json`, in both
theme blocks.** They are excluded from the re-derivation by research D6 and by
`specs/005-design-system-foundations/contracts/token-families.md` §3, for the reason
[`game-asset-tokens.md`](./game-asset-tokens.md) gives: they are the game's own canonical colours, a
player's colour is their identity, and re-tinting one would make the swatch lie about which colour was
played. They are theme-invariant by that same decision, and their `-contrast` inks are theme-invariant
with them because the fill they sit on does not move.

| Token               | Value     | Name   | Status                                                   |
| ------------------- | --------- | ------ | -------------------------------------------------------- |
| `player-1`          | `#405BFF` | Blue   | **retained** — canonical, `color_id` 1                   |
| `player-1-contrast` | `#fffaf0` | —      | **retained** — the one fill needing the light ink, 4.8:1 |
| `player-2`          | `#FF0000` | Red    | **retained** — canonical, `color_id` 2                   |
| `player-2-contrast` | `#000000` | —      | **retained** — 5.2:1                                     |
| `player-3`          | `#00FF00` | Green  | **retained** — canonical, `color_id` 3                   |
| `player-3-contrast` | `#000000` | —      | **retained** — 15.3:1                                    |
| `player-4`          | `#FFFF00` | Yellow | **retained** — canonical, `color_id` 4                   |
| `player-4-contrast` | `#000000` | —      | **retained** — 19.5:1                                    |
| `player-5`          | `#00FFFF` | Teal   | **retained** — canonical, `color_id` 5                   |
| `player-5-contrast` | `#000000` | —      | **retained** — 16.7:1                                    |
| `player-6`          | `#FF57B3` | Purple | **retained** — canonical, `color_id` 6                   |
| `player-6-contrast` | `#000000` | —      | **retained** — 7.2:1                                     |
| `player-7`          | `#797979` | Grey   | **retained** — canonical, `color_id` 7                   |
| `player-7-contrast` | `#000000` | —      | **retained** — 4.8:1, the tightest fill                  |
| `player-8`          | `#FF9600` | Orange | **retained** — canonical, `color_id` 8                   |
| `player-8-contrast` | `#000000` | —      | **retained** — 9.6:1                                     |

**One consequence to notice rather than "fix".** `player-1-contrast` is `#fffaf0`, which was the old
light `surface`. That value no longer exists anywhere else in the palette. It stays exactly as it is:
it was chosen by measurement against Blue (4.8:1), not by matching a surface, and re-pointing it at
the new `#fffbf2` would change an asserted pair for a cosmetic reason. An implementer who "tidies" it
has broken a measurement.

**The frame is unaffected and gets better.** Every swatch is drawn with a 1px `border-strong` frame so
a pale fill (Yellow, Green, Teal) stays a distinct chip against parchment
([`game-asset-tokens.md`](./game-asset-tokens.md), Decision 1). Light `border-strong` moves from 3.5:1
to 4.8:1 on `surface` and from 3.4:1 to 5.2:1 on `surface-raised`, so the frame does its job with more
margin than before. No new assertion; the existing `border-strong` rows cover it.

---

## 9. Visual acceptance criteria

Phrased so `visual-reviewer` can decide each from a screenshot plus this file. Every one is checked in
**both themes** at every declared review width.

1. **The surface ramp is monotonic and visible.** In a story showing a raised surface on the page
   (`Callout`, `Menu` open, `Tooltip`, `SignInScreen`), the four surfaces read in order: the sunken
   region is the darkest area in light and in dark, and the raised panel is the lightest in both. A
   screenshot where `surface` is lighter than `surface-raised` is the old palette and fails.
2. **A raised surface is bounded without relying on its fill.** Every raised surface shows its border,
   stripe or shadow. If the only thing separating a `Callout` from the page is 2.7 L\* of fill, the
   component lost its stripe and this fails.
3. **The row separator is visible without hunting for it.** In `MatchRow`'s table story at 1280, the
   horizontal rules between rows are plainly visible against the page at a normal viewing distance.
   The previous 1.6:1 hairline is what this criterion exists to catch a return to.
4. **A focused accent-filled control shows a ring inside its fill.** `primitives-button--primary` and
   `DataExportPanel`'s download link, focused by keyboard, show a light ring _within_ the gold fill,
   not a coloured ring floating on the page beside it, and not no ring at all.
5. **A focused control on any page surface shows the azure ring outside it**, and that ring is
   unmistakably a different colour from the `info` callout in the same screenshot.
6. **Warning and danger are not the same colour.** A story rendering a `warning` `Callout` beside a
   `danger` one shows two different hues; if a reader has to read the heading to tell which is which,
   this fails.
7. **The disabled label is readable.** A disabled `Button` in either theme has a label that can be
   read, and is still obviously weaker than the secondary text beside it. Both halves are required —
   an unreadable label fails, and a label indistinguishable from `text-secondary` also fails.
8. **Hierarchy holds.** In any story carrying primary, secondary and disabled text together, the three
   are ranked by weight in that order at a glance, without measuring.
9. **Numbers first.** No re-derived colour puts a number behind a lower-contrast treatment than the
   prose beside it. In `StatValue`, `MatchRow` and `ProfileSummary`, the numeric value is the highest-
   contrast thing in its own row.

---

## 10. What the implementer does with this

1. Replace `packages/design-system/tokens/color.json` with §4 verbatim, and insert §4a's `$rationale`
   block after `$comment`. Do not add a `$comment` inside a theme block (§4a explains what breaks).
   Do not change any `player-*` value (§8).
2. Run `pnpm --filter design-system tokens:build`.
3. Update `tokens/build-tokens.test.mjs`'s asserted pairs to §7's floors — in particular: assert
   `warning`/`info`/`success`/`danger` against `surface-raised` (unchanged shape, new numbers), assert
   `success` and `danger` against `surface`, `background` **and** `surface-sunken`, assert every
   `X-contrast` against its own `X` at 4.5 (light `warning-contrast` was 3.47 and had no assertion),
   assert `focus-ring` against all four page surfaces at 3, assert `accent-contrast` against
   `accent`/`accent-hover`/`accent-active` at 4.5, and add dark `text-secondary` on `background`.
   Remove any assertion of `focus-ring` against `accent`.
4. Apply §5's two component changes. Without them DS-10 survives this task.
5. Hand the §7 tables to T526 for `README.md`, and hand §5's closing paragraph to whoever closes
   DS-10 in the gap register.
6. Baselines: this repaints every story in both themes. Regenerate in CI only, per research D3 — never
   locally.

---

## 11. Link roles (T522)

Three roles arrive: `link`, `link-hover`, `link-visited`. **This section adds a seventh member to the
chromatic band; it revises nothing already shipped.** The six existing chromatic values, the surface
ramp, the ink ramp and every measured pair in §7 stand exactly as written. Same method, same band,
same declaration rule.

> Add the `link`, `link-hover` and `link-visited` roles to `packages/design-system/tokens/color.json`,
> each declaring the surfaces it may be painted on and measured against `background`, `surface`,
> `surface-raised` and `surface-sunken` in both themes (closes DS-9, FR-006, research D10). The
> permanent underline stays: a link is never distinguished by colour alone.

### 11.1 Why this is a role and not three more measurements of `accent`

DS-9 offers two closures and they are not equivalent. Measuring `accent` on `surface-raised` and
`surface-sunken` and adding the rows would close the **contrast** half — and leave the **semantic**
half exactly where it is.

**`accent` means "the product's own emphasis"; `link` means "this text navigates". The two must be
able to move without dragging each other.** Today they cannot: the `SiteHeader` current-tab rule, the
`Badge` accent tone and every inline link in `PrivacyNotice` are one value, so a decision about how
loud the product's emphasis should be is silently also a decision about how a link looks in a legal
document. That is the same defect §3.4 removed between `info` and `focus-ring` — one value under two
names — and the fix is the same one: give the second meaning its own name before something needs them
to differ.

**The boundary, stated so it is checkable.** Two neighbouring cases stay with `accent` and are not
migrated:

- **A link styled as a control paints `accent`, not `link`.** `DataExportPanel`'s download anchor is a
  filled button that happens to be an `<a>`; it reads as a control, carries `accent-contrast` and its
  inward ring (§5), and nothing about it is prose. `link` is an ink, never a fill.
- **Navigation chrome paints `accent`, not `link`.** `SiteHeader`'s current-tab rule marks _where you
  are_ in a persistent control surface. In-document navigation is the other side of that line:
  `PrivacyNotice`'s `Contents` is a list of prose links to prose, and it paints `link`.

### 11.2 The hue, and why 258° / 260°

The band's seven hues, in order, so the choice is visibly deliberate rather than picked:

| Role         | Light | Dark | Nearest neighbour       |
| ------------ | ----- | ---- | ----------------------- |
| `danger`     | 7°    | 11°  | `warning`, 21° / 15°    |
| `warning`    | 28°   | 26°  | `accent`, 10° / 13°     |
| `accent`     | 38°   | 39°  | `warning`, 10° / 13°    |
| `success`    | 118°  | 105° | `info`, 69° / 86°       |
| `info`       | 187°  | 191° | `focus-ring`, 27° / 22° |
| `focus-ring` | 214°  | 213° | `info`, 27° / 22°       |
| **`link`**   | 258°  | 260° | `focus-ring`, 44° / 47° |

`214° → 7°` is the palette's one empty arc, 153° wide, and `link` takes a position inside it. Not its
centre — the centre (~290°) is a magenta-violet that reads as _visited_ before it reads as _link_,
which would undermine the rest/visited distinction §11.3 makes. **258° is the indigo a reader already
knows means "this navigates"**, and it is the one place in this palette where a web convention, not
the art direction, sets the hue: the functional constraint that outranks atmosphere applies to
recognition as much as to legibility, and a link a reader has to learn is a link they will not click.
It sits 44° from `focus-ring`, four times the `warning`/`accent` adjacency §3.3 already accepts, with
a chroma difference in the opposite direction (`focus-ring` is the system's most saturated value;
`link` is mid-chroma), and the two never occupy the same shape — one is a stroke around a box, the
other is glyph fill. §11.7 turns that into a checkable criterion rather than leaving it asserted.

**It is muted on purpose.** `#603fb0` is not `#0000EE`; its HSL saturation is 0.47 light and 0.55
dark, the same order as `accent` (0.63 dark). An electric blue-violet on parchment would be the one
value in the system that looks pasted in from another product.

**The sentence in §2 this amends.** §2 says the palette's only cool notes are `info` and `focus-ring`.
There are now three. That is the cost of the role and it is paid knowingly: a link's colour is a
convention rather than a mood, and the only warm alternative is `accent`, which is the thing this
section exists to stop reusing.

**Rejected: a blue `link` and a violet `link-visited`,** the browser default pair. It adds two hues to
the band instead of one, and the blue would land near 230° — 16° from `focus-ring`, tighter than the
`warning`/`accent` adjacency, in the exact case (a focused link) where the two are drawn touching.
One new hue, three roles, is the answer §3.3's method points at.

### 11.3 The three steps, and why `link-visited` is not an interaction step

`link-hover` is derived **exactly as `accent-hover` was** (§3.5): one interaction step away from the
page, in the theme's own direction — light −6.2 L\*, dark +7.5 L\*, against `accent-hover`'s −6.2 /
+7.4. Same rule, same magnitude, no new reasoning needed.

`link-visited` is **not** an interaction step, and this is the one place a link's states differ from
`accent`'s in kind rather than in value. `accent-hover` and `accent-active` both mean _more emphasis,
right now_; visited means the opposite — **already read, no longer the thing to click.** Expressing
that as a lightness step would say "less emphasis" in the light theme and "more" in the dark one,
because a step in the theme's own direction reverses. So:

> **`link-visited` keeps the hue and cuts the chroma by ~40%, with a small drop toward the band's
> floor (−2.6 L\* light, −3.1 L\* dark).** A chroma cut means the same thing in both themes: the
> colour is spending itself out, rather than moving toward or away from the reader.

It stays **inside the band** (33.7 light, 65.5 dark) because a visited link is a rest state that must
still be read — unlike `accent-active`, which is a transient press and is allowed below the band. It
is now the system's least saturated chromatic member, marginally below light `success` (0.28 vs 0.30).

**There is deliberately no `link-active`.** FR-004 rejects a token whose only justification is one call
site and requires naming the token that serves: **`link-hover` serves.** `accent-active` exists because
a button can be held pressed without committing; an anchor's press is the ~120ms before navigation,
under a pointer that is already showing hover. Call sites that carry `active:text-accent-active` on a
link point it at `link-hover` (§11.6) — which is not redundant with the hover rule, because a touch
activation never passes through hover.

| Step           | Light L\* | Dark L\* | Rule                                                      |
| -------------- | --------- | -------- | --------------------------------------------------------- |
| `link`         | 36.3      | 68.6     | rest — mid-band, between `success`/`warning` and `danger` |
| `link-hover`   | 30.1      | 76.1     | one interaction step away from the page (§3.5's rule)     |
| `link-visited` | 33.7      | 65.5     | rest, chroma −40%, small drop toward the band floor       |

**Why `link` sits mid-band and not at the top.** `accent` is the band's ceiling (40.8 light) and that
is precisely why it cannot declare `surface-sunken` — 4.27:1, §6. 4.5:1 against light `surface-sunken`
requires L\* ≤ 39.4, and 5.0:1 requires L\* ≤ 36.6. `link` is placed at 36.3 so it clears **5.0:1 on
every light surface**, which is what lets it declare all four and is the whole content of DS-9's
closure. The system's tightest pair therefore remains light `accent` on `background` at 5.0.

### 11.4 The values

Six keys per theme. Insert **after `focus-ring` and before `overlay`**, so the chromatic band stays
contiguous. No generator change: `build-tokens.mjs` emits `--ds-color-link*` like any other key, and
`text-link`, `hover:text-link-hover` and `visited:text-link-visited` are then ordinary utilities.

Merge into `light`:

```json
    "link": "#603fb0",
    "link-hover": "#503396",
    "link-visited": "#56467d",
```

Merge into `dark`:

```json
    "link": "#b39ce2",
    "link-hover": "#c6b2ee",
    "link-visited": "#a897c9",
```

`$rationale` gains the matching three lines in each theme block, in the same position:

```json
      "link": "derived: chromatic band L* 36.3, hue 258 — muted indigo. A distinct role from accent: accent is the product's emphasis, link means this text navigates. Placed mid-band rather than at accent's ceiling so it clears 5.0:1 on all four surfaces and can declare them (closes DS-9).",
      "link-hover": "derived: one interaction step (-6.2 L*) away from the page, the same rule and magnitude as accent-hover.",
      "link-visited": "derived: link's hue with chroma cut ~40% and -2.6 L*. Visited means spent, not emphasised, so it is a chroma cut and not a lightness step — a step would reverse direction between the themes.",
```

```json
      "link": "derived: chromatic band L* 68.6, hue 260 — muted amethyst; same role and same reasoning as light link.",
      "link-hover": "derived: one interaction step (+7.5 L*) away from the page, matching accent-hover's +7.4.",
      "link-visited": "derived: link's hue with chroma cut ~40% and -3.1 L*; stays inside the band because a visited link is a rest state that must still be read.",
```

### 11.5 Declared surfaces and the measured pairs

**All three roles declare all four page surfaces, in both themes.** A state role must declare at least
everything its rest role declares — a component that may paint `link` on `background` will hover that
link on `background` — so a shorter list for `link-hover` or `link-visited` would make hovering a
declared link an undeclared pair. None of the three declares a fill: a link is an ink, and there is no
`link-contrast` (FR-004; `accent-contrast` serves the one anchor that is a filled control, §11.1).

These rows extend §6's table:

| Role           | Means                       | Declared surfaces  | Floor | Real call sites that fix the list                                                                                                                        |
| -------------- | --------------------------- | ------------------ | ----- | -------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `link`         | this text navigates         | `BG` `S` `SR` `SS` | 4.5   | `PrivacyNotice` inline links and `Contents` on `S`, `ContactBlock`'s contact route on `SR`; `Footer` on `BG`; a link inside a hovered `MatchRow` on `SS` |
| `link-hover`   | that link, hovered          | `BG` `S` `SR` `SS` | 4.5   | every call site above, hovered                                                                                                                           |
| `link-visited` | that link, already followed | `BG` `S` `SR` `SS` | 4.5   | `PrivacyNotice` `Contents` and inline links; every future prose surface                                                                                  |

Computed with the same WCAG 2.2 relative-luminance formula as §7, from the hexes in §11.4. **T526
transcribes these 24 rows into `README.md`, and `build-tokens.test.mjs` asserts all 24 at 4.5.**

**Light** (`link` L\* 36.3 · `link-hover` 30.1 · `link-visited` 33.7)

| Foreground     | `surface-raised` | `surface` | `background` | `surface-sunken` |
| -------------- | ---------------- | --------- | ------------ | ---------------- |
| `link`         | **7.17**         | **6.70**  | **5.97**     | **5.05**         |
| `link-hover`   | 9.02             | **8.43**  | 7.51         | 6.35             |
| `link-visited` | 7.92             | **7.40**  | 6.59         | 5.57             |

**Dark** (`link` L\* 68.6 · `link-hover` 76.1 · `link-visited` 65.5)

| Foreground     | `surface-raised` | `surface` | `background` | `surface-sunken` |
| -------------- | ---------------- | --------- | ------------ | ---------------- |
| `link`         | **6.05**         | **6.88**  | **7.51**     | **8.03**         |
| `link-hover`   | 7.59             | **8.63**  | 9.42         | 10.08            |
| `link-visited` | 5.47             | **6.23**  | 6.80         | 7.27             |

The four bold `link` cells are the pairs the task set; the bold `surface` cells are the spot checks
the two state roles owe. Every one of the 24 clears 4.5, the tightest being dark `link-visited` on
`surface-raised` at 5.47 — still above the system's tightest pair, light `accent` on `background` at
5.0, which keeps its title.

**One adjacency this table does not measure and a reader would otherwise assume.** A link sits
_inside_ a paragraph of `text-primary`, and ink against ink is **2.31:1 light and 1.95:1 dark**. That
is not a WCAG pair — both are legible against the surface, which is what 1.4.3 asks — but it is the
number that makes the permanent underline structural rather than a formality, and it is _lower in
dark_, where the underline carries almost all of the distinction. FR-006 and rule 4 are not satisfied
by these hues at any value; the 5.97–7.17 column is not permission to drop it.

### 11.6 What this changes for `privacy-notice.md`, the caller that paid for DS-9

The interim being retired is quoted in the register: _"Until then no component paints a link on a
raised surface."_ `privacy-notice.md` §6 records what that cost, and
`packages/design-system/src/components/PrivacyNotice/index.tsx:709` is where it was paid — inside
`ContactBlock`, which is `bg-surface-raised`, the contact route renders `text-text-primary underline`
instead of a link colour. **A link the same colour as the sentence around it is a link found by
mousing over the paragraph.** In a legal notice that anchor is the one route a reader has to a human
being, and it is the last line of the document.

The concrete consequence, in order:

| Where                                 | Was                                                           | Becomes                                                |
| ------------------------------------- | ------------------------------------------------------------- | ------------------------------------------------------ |
| `PrivacyNotice` `ContactBlock` (:709) | `text-text-primary underline` on `surface-raised`             | `text-link underline` — **7.17** light / **6.05** dark |
| `PrivacyNotice` inline links (:204)   | `text-accent` / `hover:accent-hover` / `active:accent-active` | `text-link` / `hover:link-hover` / `active:link-hover` |
| `PrivacyNotice` `Contents` (:454)     | the same accent triple                                        | the same link triple                                   |
| `ThirdPartyObjectionForm` (:30)       | the same accent triple                                        | the same link triple                                   |
| `AccountErasurePanel` (:272)          | the same accent triple                                        | the same link triple                                   |
| `Footer` (:38, :46)                   | `text-text-secondary underline hover:text-accent-hover`       | rests at `link`; see the note below                    |

And in `privacy-notice.md` itself: §6's colour list drops `accent` / `accent-hover` / `accent-active`
for `link` / `link-hover` / `link-visited` **and the parenthetical restriction "on `surface` only —
see the DS-9 note below"**; §6's "Gaps in play" paragraph drops DS-9 together with the whole sentence
beginning "Until DS-9 closes, this component paints no link on `surface-raised`"; §5's hover and
active lines name the link roles; §9's contrast bullet replaces "links `accent` on `surface` (4.9
light / 7.7 dark — …which is why DS-9 permits `accent` here and only on this background)" with `link`
on `surface` **6.70 light / 6.88 dark** and on `surface-raised` **7.17 / 6.05**. That component keeps
a `visited:` declaration on its inline links and on `Contents`: a nine-section document a reader
returns to is the clearest case in the product for "which of these have I already read".

**`Footer` is the one call site where this changes an existing deliberate choice**, so it is named
rather than swept in: its links rest at `text-secondary` and only reach for accent on hover. With a
`link` role in existence that is a link withholding the one signal that says it is a link. The default
is that it rests at `link` (5.97 light / 7.51 dark on `background`) and expresses its quietness with
size, which it already does at `text-sm`; the footer's own spec applies it, and if it declines it must
record why — "a link that looks like text" is exactly the finding DS-9 was opened about.

### 11.7 Acceptance, and the one state a screenshot cannot reach

§9 gains three criteria, numbered 10 to 12, checked in both themes at every declared review width:

10. **A link is visibly a link before it is hovered.** In `PrivacyNotice` at 1280, an inline link
    inside a paragraph is distinguishable from the sentence around it by colour _and_ carries an
    underline. The two halves fail independently: no underline fails, and an indigo that reads as body
    ink fails.
11. **The contact route in `ContactBlock` is a link.** In the `PrivacyNotice` story with
    `controllerContact` supplied, the anchor in the raised contact block is the same colour as the
    inline links in the body above it. A `text-primary` anchor there is the interim this task retired,
    and fails.
12. **A focused link's ring is not its own colour.** With an inline link focused by keyboard, the
    azure `focus-ring` outside the glyphs and the indigo `link` inside them read as two colours. If
    the ring looks like a thicker link, this fails.

**`link-visited` cannot be verified from a story of real anchors, and that must not be discovered
during review.** Browsers restrict `:visited` styling and `getComputedStyle` deliberately reports the
unvisited colour, so neither Playwright nor Storybook can force or measure the state — the same
blindness the suite already has for focus, one step worse. Its criterion is therefore satisfied by a
**token story that paints `text-link-visited` directly**, beside `link` and `link-hover`, on all four
surfaces: three swatches that are three colours, the last one visibly spent rather than merely darker.
Its contrast is guaranteed by the asserted token pairs above, which is why all four surfaces are
declared and asserted for it even though no automated check will ever catch it in situ.

### 11.8 What the implementer does with this

1. Merge §11.4's two value fragments into `light` and `dark` after `focus-ring`, and the two
   `$rationale` fragments into the matching theme blocks in the same position. Nothing else in
   `color.json` changes — §4's values are shipped and are not reopened.
2. Run `pnpm --filter design-system tokens:build`.
3. Add §11.5's 24 assertions to `build-tokens.test.mjs` at 4.5: three roles × four surfaces × two
   themes.
4. Apply §11.6's six call-site rows and the `privacy-notice.md` edits. **Without them DS-9's cost
   survives its closure** — the token existing is not what refunds `ContactBlock`.
5. Close DS-9 in `README.md`'s gap register naming this section, and hand §11.5's tables to T526.
6. Baselines: this repaints every story containing a link, in both themes. CI only, per research D3.
