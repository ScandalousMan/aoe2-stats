# Typography tokens — the typeface decision (feature 005, T523)

The answer to the question phase 0 found and the spec does not carry ([research.md](../../../specs/005-design-system-foundations/research.md) **D6a**). Written by
`product-designer`; the values, filenames, licence records and configuration here are applied
**verbatim** by T523's implementer, who invents nothing. Where this file states a path, that path
ships; where it states a verification step, that step is performed and its result recorded before the
change is handed back.

**The task this closes**, recorded so a later reader does not have to reconstruct it:

> Resolve the typeface question, which phase 0 found and the spec does not carry (research D6a).
> `font.json` names `Inter`, `Fraunces` and `JetBrains Mono`; there is no font file, no `@font-face`
> and no stylesheet link anywhere, and every surface in the product and in Storybook has always
> rendered `system-ui`, `Georgia` and `ui-monospace` instead. All 279 baselines were captured in the
> fallbacks. Two outcomes are admissible and `product-designer` picks one with the palette: self-host
> all three under `packages/design-system/tokens/fonts/`, each with the five-field licence record and
> a preload so the first paint is not a swap — and, in the same change, extend
> `scripts/checks/asset_packs.py` and the `asset-packs` paths filter in `.github/workflows/pr.yml` to
> that directory — or name `Georgia` and `ui-monospace` as the chosen families deliberately and
> delete the three names nothing serves. Not admissible: a third pass of the same defect, a family
> named in the token source that no reader ever sees.

**Scope.** The three **families** and everything required to make them real: the files, their
licence records, the licence gate that has to reach them, the `@font-face` output, the mounting in
both consumers, and the preload. **Not** the type scale: `size`, `weight`, `tracking` and the new
`role` group are **T524**, which runs immediately after this one and re-derives against the metrics
decided here (§11). Colour is [`color-tokens.md`](./color-tokens.md) and is not reopened.

Measured facts about the outside world — each pack's licence, source and date — are mirrored in
[`docs/asset-packs.md`](../../../docs/asset-packs.md), which is the repository's ledger for them, and are
**referenced there, not restated here** once §6 has been transcribed. This file is the source that
transcription is written from.

---

## 1. The decision

> **Self-host all three families — `Inter`, `Fraunces` and `JetBrains Mono` — as Latin-subset
> variable WOFF2 files under `packages/design-system/tokens/fonts/`, one licence-recorded pack each,
> and extend the constitution X licence gate to that directory in the same change.** The three names
> already in `font.json` are ratified by being loaded rather than deleted; the fallback stacks behind
> them stay exactly as written, because they now do the job a fallback stack is actually for.

Uniform across all three roles. Not split. §2.4 records the split I considered and why it loses.

---

## 2. Why

### 2.1 The two costs, weighed

**Self-hosting costs**, all real and none of them decisive:

- Three binary files enter the repository. Bounded at ~150 KB each and 1 MB for the directory (§4.4),
  against a repository whose only existing binary payload — `packages/game-assets` — already carries a
  10 MB budget and a gate to enforce it.
- It repaints every glyph in the product. **In this phase that is free**, and D6a says why: the
  palette already repaints everything here, so the two share one regeneration. Deferring is what costs
  a repaint, not doing it (§12).
- It extends `scripts/checks/asset_packs.py` and a CI paths filter to a second assets root. This is
  work, and it is also the only part of this task that improves something independently of the
  typeface question: constitution X's "a pack whose licence is not recorded MUST NOT be added" is
  today enforced **only where the gate looks**, and it looks at exactly one directory (§9).
- It adds ~170 KB of first-visit page weight and a preload dependency. Stated as a budget, measured,
  and with a named lever if it ever bites (§8.4).
- It forces T524 to re-derive the scale against real metrics rather than fallback metrics (§11).

**Naming the fallbacks costs** exactly one thing, and it is larger than it looks: it makes every
typographic decision in this system conditional on the reader's operating system. That is not only a
loss of character. It is a loss of _knowledge_.

### 2.2 The argument that decides it: a fallback stack is not a family, so nothing derived from it is true

`system-ui`, `Georgia` and `ui-monospace` are not typefaces. They are instructions to the reader's
machine, and they resolve differently on every one of them:

| Named family   | macOS   | Windows           | Android / most Linux                              |
| -------------- | ------- | ----------------- | ------------------------------------------------- |
| `system-ui`    | SF Pro  | Segoe UI          | Roboto / whatever fontconfig picks                |
| `Georgia`      | Georgia | Georgia           | **absent** — falls through to a generic `serif`   |
| `ui-monospace` | SF Mono | Cascadia/Consolas | **frequently unsupported** — falls to `monospace` |

These faces do not share an x-height, a cap-height, or — for the monospace — an advance width. So
under the fallback route:

1. **T524's type scale would be derived against one machine's metrics** and would be a different
   optical scale on every other. FR-007 asks for roles defined by function; a role whose rendered size
   is a property of the reader's OS is not a decision the system made.
2. **FR-018's "no horizontal overflow, no unintended truncation at any review width" cannot be
   established.** Overflow is a function of advance width. A rating table verified clean at 375 in CI
   is unverified for a reader whose monospace is 8% wider.
3. **The 1,794 baselines this feature is about to capture would depict a rendering no reader ever
   sees.** CI's Linux container resolves all three fallbacks to its own fonts — not macOS's, not
   Windows'. Every acceptance criterion FR-059 requires to be "decidable from a still image" would be
   decidable about an image that exists nowhere but in the runner.

That third point is why this decision is not a matter of taste. **The spec's third named gap is a
verification suite that claims coverage it does not have.** Shipping the faces is what makes the
baseline and the reader's screen the same picture, so the gate this feature is rebuilding verifies
something. Keeping the fallbacks would close two of the three gaps and quietly widen the third.

### 2.3 The functional constraint argues for shipping, not against

The standing constraint — _this is a data tool, consulted often and quickly; number legibility and
information density come before decoration_ — is the reason to be suspicious of a display serif. It
is also, applied honestly, an argument for shipping the monospace and for shipping all three:

- **Numbers.** D7 puts `font-variant-numeric: tabular-nums` on the `numeric` role, which is what makes
  alignment a decision rather than a coincidence (SC-009). `tnum` is an OpenType feature: it applies
  only if the font implements it. A shipped face is a face whose figure set the repository can check
  once and rely on; `ui-monospace` is a face nobody in this project will ever have seen.
- **Identifiers.** The `identifier` and `machine` roles carry Steam ids, profile ids, filenames and
  error classes. `0` against `O` and `1` against `l` at `text-xs` is a legibility property of the
  chosen face and of nothing else. §13 criterion 4 checks it from a screenshot.
- **Density.** Column widths, row heights and the point at which a table overflows are all metric
  facts. Under the fallbacks they are facts about the reader; under a shipped face they are facts
  about the product, which is the only version of them T525's surface classes and T524's scale can be
  written against.

Where the constraint does bite is on the display face, and it bites in one specific place: it is why
Fraunces ships with its decorative axis pinned off (§3.2). Atmosphere is admitted; wonk is not.

### 2.4 The split I considered and rejected

The defensible hybrid is: **ship JetBrains Mono for the numeric, machine and identifier roles; name
`system-ui` and `Georgia` for body and display.** It captures the functional guarantee, costs ~45 KB
instead of ~170 KB, and touches the licence gate exactly as much (any font file at all forces the
gate extension, so the split saves nothing there).

It loses for three reasons:

1. **The determinism argument in §2.2 is not about the mono.** Body text is most of the glyphs on
   every page; headings set the vertical rhythm the whole page inherits. A split leaves the majority
   of the type in the state this task exists to end.
2. **`Georgia` is not available to name.** It does not exist on Android or on most Linux desktops, so
   "we chose Georgia" would mean "we chose Georgia for the readers who have it and a lottery for the
   rest" — an unrecorded decision wearing a recorded one's clothes, which is the precise defect
   `font.json` has carried for a year.
3. **It defers rather than decides.** A later Fraunces would be a fourth global repaint, after the
   retrofit, which D1 exists to prevent — so the split's honest form is "Georgia and system-ui,
   permanently", and that is §2.2 again.

Recorded here so a reader does not re-derive it, and so that if the mono ever ships alone it is
because someone overturned this paragraph rather than because nobody read it.

### 2.5 What this decision is not

It is **not** a change of art direction (spec Risk 10, Out of Scope). The families are the three the
system already named; what changes is that they exist. The character is carried by the palette
([`color-tokens.md`](./color-tokens.md)); typography's job here is hierarchy and legibility, plus one
place — the heading serif — where the era is expressed at a cost of a few glyphs read once per page.

Self-hosting rather than a font CDN is **not the designer's choice and was never open**: a
`<link>` to a font service would be an outbound runtime request from `apps/web` (constitution III) and
would hand a reader's address to a non-EU host (constitution IX). Fetching files by hand at
development time and serving them from our own origin is not an external call; it is the same rule
feature 004 adopted for asset packs.

---

## 3. The three families, chosen rather than inherited

FR-001a requires each role's family to be _chosen_. Ratifying the three existing names is a choice
only if the reasoning is written down, so it is.

### 3.1 `sans` — **Inter**

Carries `body` and `supporting` (D7): prose, control labels, table headers, every alias and every
sentence in the product. Chosen because it is a face designed for user interfaces at small sizes on
screen — large x-height, open apertures, unambiguous `I`/`l`/`1` — which is the same brief `system-ui`
was solving, done once, identically, for every reader. Neutral on purpose: the parchment palette
carries the era, and a characterful body face on top of it would be two voices competing across the
densest surfaces in the product.

**What it deliberately does not do**: replace the reader's system font for glyphs it does not have.
The stack stays `'Inter', system-ui, sans-serif`, and §7.2 explains why that matters more in this
product than in most.

### 3.2 `display` — **Fraunces**

Carries `display`: page and section headings, the wordmark in `SiteHeader`. Chosen for three reasons,
in order of weight:

1. **It has an optical-size axis.** The display role runs from `text-lg` (18px, the `SiteHeader`
   wordmark) to `text-3xl` (30px, `PrivacyNotice`'s h1) — a range across which a single-design serif
   is either too delicate at the bottom or too coarse at the top. `opsz` applies automatically from
   `font-size` (`font-optical-sizing: auto` is the default), so a heading is drawn for the size it is
   set at. In a data tool whose headings are small, that is a legibility property, not a flourish.
2. **Its letterforms are old-style and warm** — the "parchment, stone, muted gold, restrained" brief
   read into type rather than colour — without being a costume serif. A blackletter or a
   pseudo-medieval face would be the character change Risk 10 puts out of scope, and would be
   unreadable at 18px besides.
3. **It is a variable font under OFL**, so all four declared weights are real (§7.3).

**Its decorative axes are pinned off, and that is this file's application of the functional
constraint.** Fraunces ships `SOFT` (softened terminals) and `WONK` (eccentric alternates —
the swashy `g`, the flicked `y`). Both are pinned at `0`, by shipping the weight-axis instance and by
the verification in §4.3. A wonky heading is decoration in a screen a reader consults to compare
ratings, and decoration loses to legibility by standing rule. The face's warmth survives the pinning;
its eccentricity does not, and is not missed.

### 3.3 `mono` — **JetBrains Mono**

Carries `numeric`, `machine` and `identifier` (D7) — every rating, rank, duration, delta, Steam id,
profile id, filename and error class in the product. This is the product's core content and the
family the functional constraint most directly governs. Chosen for a tall x-height at small sizes
(the `identifier` role renders at `text-xs`), an even, unfussy digit rhythm, and disambiguated
`0`/`O` and `1`/`l` — the property that stops a copied Steam id being wrong. It is designed to be
read for long stretches at small sizes, which is exactly what a rating column is.

Its `0`/`O` and `1`/`l` distinction is stated here as the **reason for the choice** and verified in
§13 criterion 4 from a screenshot, not asserted as a fact about the font's internals that nobody in
this repository has checked. If the rendered proof fails, the choice is wrong and comes back here.

---

## 4. What ships

### 4.1 Layout — three packs, the shape the gate already understands

`scripts/checks/asset_packs.py` treats **every immediate subdirectory of an assets root** as a pack
and requires a `LICENCE.md` in each (`_pack_dirs`, `check_pack`). Giving each family its own
directory means the gate needs no new concept — only a second root (§9).

```text
packages/design-system/tokens/fonts/
├── inter/
│   ├── LICENCE.md
│   └── inter-variable-latin.woff2
├── fraunces/
│   ├── LICENCE.md
│   └── fraunces-variable-latin.woff2
└── jetbrains-mono/
    ├── LICENCE.md
    └── jetbrains-mono-variable-latin.woff2
```

**The destination filenames above are normative.** Files are renamed on copy-in, and the rename is
recorded in each `LICENCE.md`'s `Source` field (the same discipline `civilisations` uses to record
"re-encoded to WebP"). This is deliberate: the `@font-face` `src` in §8.1 is then a string this file
fixes, rather than a string that depends on what an upstream release happened to call its artifact.

### 4.2 Sources — exact, versioned, and re-fetchable by hand

Two things are named per family: the **upstream project**, which is where the typeface and its
licence come from, and the **distribution artifact**, which is the specific pre-built, pre-subset
WOFF2 file to copy. Both go in the record, because a reader asking "is this lawful?" needs the first
and a reader asking "can I re-fetch this exact byte sequence?" needs the second.

| Family         | Upstream project (licence lives here)                                     | Artifact to copy                                                                                                     |
| -------------- | ------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------- |
| Inter          | `rsms/inter` — SIL OFL 1.1, `LICENSE.txt` at the repository root          | npm `@fontsource-variable/inter`, exact version pinned in the record, file `files/inter-latin-wght-normal.woff2`     |
| Fraunces       | `undercasetype/Fraunces` — SIL OFL 1.1, `OFL.txt` at the repository root  | npm `@fontsource-variable/fraunces`, exact version pinned, file `files/fraunces-latin-wght-normal.woff2`             |
| JetBrains Mono | `JetBrains/JetBrainsMono` — SIL OFL 1.1, `OFL.txt` at the repository root | npm `@fontsource-variable/jetbrains-mono`, exact version pinned, file `files/jetbrains-mono-latin-wght-normal.woff2` |

**Why the Fontsource distribution and not the upstream release zip.** The upstream projects ship
full-charset TTFs (and, for Inter, a full-charset variable WOFF2 several times the size of the Latin
subset). Using them means running `fonttools` to instance the non-weight axes, subset to Latin and
compress to WOFF2 — three tool invocations whose output the implementer cannot verify against
anything. Fontsource publishes exactly the artifact this decision needs — Latin subset, weight axis
only, WOFF2, already built — as an **immutable, exactly-versioned npm package** carrying the upstream
OFL text. That is a better provenance story than a hand-run conversion, not a worse one, and it is
recorded in the `Source` field so the chain upstream is never hidden behind the mirror.

**Fetching is a person's development-time action, not code.** Nothing in the repository fetches a
font at build or at run time. The packages are **not** added to any `package.json`: the implementer
downloads them, copies the three files in with the names in §4.1, records the exact version, and
removes the download. The repository's "no external network call outside `packages/providers`" rule is
about the running system and is untouched.

**Fraunces' upstream is `undercasetype/Fraunces`** (Undercase Type), mirrored into `google/fonts`
under `ofl/fraunces/`. It is named here because T523's briefing mis-cited it as an Oswald project;
Oswald is an unrelated family and the record must not carry that error.

### 4.3 Verification, before anything is committed

Each fetched file, in order. Any step that fails **stops the task and is reported** rather than worked
around — this file's values are applied verbatim, and a font that does not match them is a different
decision.

1. **Read the licence text in the package you downloaded.** Confirm it is SIL Open Font License 1.1
   and that it names the family. Copy nothing whose licence text you have not read; a sibling file's
   licence is not this file's licence (the `civilisations` record exists because of exactly that
   trap).
2. **Record the exact package version** (`name@x.y.z`) into the `Source` field. `latest` is not a
   version.
3. **Confirm the file is WOFF2** — the first four bytes are `wOF2`.
4. **Confirm the weight axis.** The `fvar` table must expose a `wght` axis whose range contains
   400–700 inclusive. If it does not, the four declared weights are not all real and §7.3's guarantee
   fails.
5. **Confirm Fraunces carries no live `SOFT` or `WONK` axis** (§3.2). The weight-axis artifact should
   expose `wght` and `opsz` only. If `SOFT` or `WONK` are present and variable, pin them at `0` before
   committing and record the instancing in `Source`.
6. **Confirm the family name in the font's `name` table** matches the first quoted name in the
   matching `font.json` stack, character for character: `Inter`, `Fraunces`, `JetBrains Mono`.
   **This is the trap of this whole task.** A mismatch produces no error, no warning and no failing
   test — the browser silently uses the fallback, and the repository ships a second year of exactly
   the defect T523 was opened about. §10 turns the JSON half of this into an assertion; this step is
   the half a test cannot reach.
7. **Confirm each file is ≤ 150 KB** and the directory total ≤ 1 MB (§4.4).

### 4.4 The size budget

**1 MB over `packages/design-system/tokens/fonts/`**, enforced by `check_size_budget` at the new root
(§9.2). The three Latin-subset variable files are expected in the 35–120 KB range each, so the budget
is roughly eight times the expected payload: enough headroom for an italic or a second subset to be
admitted later by a deliberate decision, not enough for the directory to grow by accident. It is a
**separate constant** from `packages/game-assets`' 10 MB, because it is a different fact with a
different justification, and a shared constant would make one of the two a coincidence.

---

## 5. The licence records — transcribe verbatim

Five fields, in this order, in the format
[`specs/004-visual-parity/contracts/asset-pack.md`](../../../specs/004-visual-parity/contracts/asset-pack.md)
fixes and `parse_licence_fields` parses (`- **Field**: value`, continuation lines allowed).

`<VERSION>` is the one value the implementer supplies, from §4.3 step 2. Everything else ships as
written.

### 5.1 `packages/design-system/tokens/fonts/inter/LICENCE.md`

```markdown
# Licence record — Inter (design-system `sans` family)

- **Source**: `rsms/inter`, the upstream project. Copied from the pre-built Latin-subset variable web
  font distributed in npm package `@fontsource-variable/inter@<VERSION>`, file
  `files/inter-latin-wght-normal.woff2` (upright, weight axis, Latin subset), renamed on copy-in to
  `inter-variable-latin.woff2`. Not re-encoded, not subset further, not modified in any way.
- **Licence**: SIL Open Font License 1.1. The upstream repository's root `LICENSE.txt` (© The Inter
  Project Authors, <https://github.com/rsms/inter>) covers the font files themselves with no
  carve-out — unlike a game-assets pack, there is no `img/README`-style notice narrowing it — and the
  distribution package carries the same text. Both were read before this pack was copied in.
- **Permitted usage**: OFL 1.1 terms — use, study, embed, modify and redistribute the font, including
  as part of a commercial product, on three conditions: it is not sold on its own, any modified
  version is not distributed under the Reserved Font Name, and this licence notice travels with it.
  This project redistributes the file unmodified, under its original name, served from its own
  origin, inside a non-commercial application. No Reserved Font Name is triggered and no condition is
  in tension with anything this project does.
- **Ruling**: **COPY IN**. OFL 1.1 grants this directly. Microsoft's "Game Content Usage Rules"
  reasoning does not apply and must not be read into this pack: a typeface is not game content and
  constitution X's asset permission does not reach it. The pack carries this record because
  `scripts/checks/asset_packs.py` walks every directory under every declared assets root regardless of
  why a given pack is lawful. Self-hosting rather than linking a font service is fixed by
  constitution III (no outbound connection from `apps/*`) and IX (no reader's address handed to a
  non-EU host), not by this ruling.
- **Checked**: 2026-09-05
```

### 5.2 `packages/design-system/tokens/fonts/fraunces/LICENCE.md`

```markdown
# Licence record — Fraunces (design-system `display` family)

- **Source**: `undercasetype/Fraunces`, the upstream project (Undercase Type), mirrored in
  `google/fonts` under `ofl/fraunces/`. Copied from the pre-built Latin-subset variable web font
  distributed in npm package `@fontsource-variable/fraunces@<VERSION>`, file
  `files/fraunces-latin-wght-normal.woff2` (upright, weight axis, Latin subset, the `SOFT` and `WONK`
  axes not variable), renamed on copy-in to `fraunces-variable-latin.woff2`. Not re-encoded, not
  subset further, not modified in any way.
- **Licence**: SIL Open Font License 1.1. The upstream repository's root `OFL.txt` (© The Fraunces
  Project Authors, <https://github.com/undercasetype/Fraunces>) covers the font files themselves with
  no carve-out, and the distribution package carries the same text. Both were read before this pack
  was copied in.
- **Permitted usage**: OFL 1.1 terms — use, study, embed, modify and redistribute the font, including
  as part of a commercial product, on three conditions: it is not sold on its own, any modified
  version is not distributed under the Reserved Font Name, and this licence notice travels with it.
  This project redistributes the file unmodified, under its original name, served from its own
  origin, inside a non-commercial application. No Reserved Font Name is triggered.
- **Ruling**: **COPY IN**. OFL 1.1 grants this directly. Microsoft's "Game Content Usage Rules"
  reasoning does not apply and must not be read into this pack: a typeface is not game content and
  constitution X's asset permission does not reach it. The pack carries this record because
  `scripts/checks/asset_packs.py` walks every directory under every declared assets root regardless of
  why a given pack is lawful. Self-hosting rather than linking a font service is fixed by
  constitution III and IX, not by this ruling.
- **Checked**: 2026-09-05
```

### 5.3 `packages/design-system/tokens/fonts/jetbrains-mono/LICENCE.md`

```markdown
# Licence record — JetBrains Mono (design-system `mono` family)

- **Source**: `JetBrains/JetBrainsMono`, the upstream project. Copied from the pre-built Latin-subset
  variable web font distributed in npm package `@fontsource-variable/jetbrains-mono@<VERSION>`, file
  `files/jetbrains-mono-latin-wght-normal.woff2` (upright, weight axis, Latin subset), renamed on
  copy-in to `jetbrains-mono-variable-latin.woff2`. Not re-encoded, not subset further, not modified
  in any way.
- **Licence**: SIL Open Font License 1.1. The upstream repository's root `OFL.txt` (© The JetBrains
  Mono Project Authors, <https://github.com/JetBrains/JetBrainsMono>) covers the font files
  themselves with no carve-out, and the distribution package carries the same text. Both were read
  before this pack was copied in.
- **Permitted usage**: OFL 1.1 terms — use, study, embed, modify and redistribute the font, including
  as part of a commercial product, on three conditions: it is not sold on its own, any modified
  version is not distributed under the Reserved Font Name, and this licence notice travels with it.
  This project redistributes the file unmodified, under its original name, served from its own
  origin, inside a non-commercial application. No Reserved Font Name is triggered.
- **Ruling**: **COPY IN**. OFL 1.1 grants this directly. Microsoft's "Game Content Usage Rules"
  reasoning does not apply and must not be read into this pack: a typeface is not game content and
  constitution X's asset permission does not reach it. The pack carries this record because
  `scripts/checks/asset_packs.py` walks every directory under every declared assets root regardless of
  why a given pack is lawful. Self-hosting rather than linking a font service is fixed by
  constitution III and IX, not by this ruling.
- **Checked**: 2026-09-05
```

---

## 6. The `docs/asset-packs.md` mirror

`check_docs_mirror` fails unless every pack with a `LICENCE.md` has exactly one row in
`docs/asset-packs.md` whose `Pack` cell equals the directory name and whose five cells match the
record **exactly** after whitespace stripping. `_documented_packs` reads **every** markdown table in
the file whose header names a `Pack` column plus all five fields, so the three rows may live in their
own table.

Add a section after "Packs copied in" and before "Rejected sources":

> ## Typeface packs
>
> One row per directory under `packages/design-system/tokens/fonts/`, mirroring that pack's own
> `LICENCE.md` — the normative copy — field for field, exactly as the game-asset table above does.
> These are a second assets root, added by feature 005 T523 and covered by the same
> `scripts/checks/asset_packs.py`; they are **not** game assets, and constitution X's Game Content
> Usage Rules permission has nothing to do with why they are lawful. All three are SIL OFL 1.1. The
> reasoning is in `packages/design-system/specs/typography-tokens.md`.

Then one table with the header `| Pack | Source | Licence | Permitted usage | Ruling | Checked |` and
three rows — `inter`, `fraunces`, `jetbrains-mono` — each cell transcribed from §5, single-line (a
table cell cannot wrap; the `LICENCE.md` continuation lines are joined with single spaces by
`parse_licence_fields`, so the cell must equal that joined string).

**Also add three rows to the existing "Rejected sources" table**, because the next reader's question
is "was a CDN considered?" and silence answers it wrongly:

| Source                                          | Holds              | Licence | Ruling    | Why                                                                                                                                                       |
| ----------------------------------------------- | ------------------ | ------- | --------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Google Fonts stylesheet `<link>`                | all three families | OFL 1.1 | **AVOID** | A runtime outbound request from `apps/web` (constitution III) handing a reader's address to a non-EU host (constitution IX)                               |
| `fonts.gstatic.com` WOFF2 URLs, fetched by hand | all three families | OFL 1.1 | **AVOID** | Version-hashed, unnameable, moving URLs with no in-package licence text — unre-fetchable provenance                                                       |
| System stacks as the chosen families            | —                  | n/a     | **AVOID** | `Georgia` is absent on Android and most Linux; no metric the type scale is derived against would be a property of the product (typography-tokens.md §2.2) |

**Checked**: 2026-09-05 for all three.

---

## 7. `font.json`

### 7.1 `family` — unchanged, and that is the point

```json
  "family": {
    "sans": "'Inter', system-ui, sans-serif",
    "display": "'Fraunces', Georgia, serif",
    "mono": "'JetBrains Mono', ui-monospace, monospace"
  },
```

Not one character changes. What changes is that the first name in each stack now resolves.

### 7.2 The fallback stacks stay, and they are load-bearing in this product specifically

A Latin subset is the right payload and it has a consequence: **an alias in Cyrillic, Greek, Korean,
Japanese or Chinese is not in these files.** This product renders player aliases straight from Relic,
and a large share of them are not Latin. The stacks are what make that render as real glyphs from the
reader's own system rather than as tofu, per glyph, automatically. Do not add `unicode-range` to the
`@font-face` rules: per-glyph fallback already handles this correctly, and a declared range would be a
second, hand-maintained statement of what the file actually contains — a fact written twice.

Recorded so that a later reader seeing a Korean alias in a different face does not "fix" it.

### 7.3 `weight` — untouched here, and all four are now real

`normal` 400, `medium` 500, `semibold` 600, `bold` 700 stay exactly as they are (T524 owns this group
and may narrow it; this task may not). Every one is a real interpolation of a shipped weight axis
spanning 400–700 — **nothing is synthesised**. For the record, what the source uses today:

| Family                  | Weights actually written in components today |
| ----------------------- | -------------------------------------------- |
| `sans` (Inter)          | 400, 500, 600                                |
| `display` (Fraunces)    | 600, and 700 once (`SignInScreen`'s h1)      |
| `mono` (JetBrains Mono) | 400, 600                                     |

Add `font-synthesis-weight: none` alongside the `@font-face` block (§8.1). It is small hardening
rather than load-bearing: with a 400–700 axis nothing needs synthesis, so its only job is to make a
future missing weight fail visibly instead of being faked into a smeared approximation nobody
notices.

### 7.4 The new `face` group — the one addition to `font.json`

The family name appears in two places once fonts exist: inside the stack string, and inside the
`@font-face` rule. If they ever disagree the browser silently uses the fallback and **nothing fails**
— §4.3 step 6's trap, in permanent form. So the second occurrence is generated from the first, and the
agreement is asserted (§10).

Add, after `family` and before `size`:

```json
  "face": {
    "sans": {
      "family": "Inter",
      "src": "/fonts/inter/inter-variable-latin.woff2",
      "weight": "400 700",
      "style": "normal",
      "display": "swap"
    },
    "display": {
      "family": "Fraunces",
      "src": "/fonts/fraunces/fraunces-variable-latin.woff2",
      "weight": "400 700",
      "style": "normal",
      "display": "swap"
    },
    "mono": {
      "family": "JetBrains Mono",
      "src": "/fonts/jetbrains-mono/jetbrains-mono-variable-latin.woff2",
      "weight": "400 700",
      "style": "normal",
      "display": "swap"
    }
  },
```

`face` is a real key, not `$`-prefixed: `readJson` strips `$`-prefixed keys at the top level, so a
`$face` would be invisible to the generator. `fontVars()` iterates `font.family`, `font.size`,
`font.weight` and `font.tracking` by name — never generically — so adding `face` emits no stray
custom property and needs no defensive change there.

Update `font.json`'s `$comment`: the current text says "no font file is copied into the repository
(constitution X); self-hosting them, if ever needed, is a separate decision with its licence
documented." **That decision is this file.** The comment becomes a pointer to it, and to the licence
records, so the JSON never again describes a state the repository has left.

---

## 8. Delivery

### 8.1 `@font-face`, generated, in `tokens.css`

`build-tokens.mjs` gains a `fontFaceRules()` builder that emits one block per `face` entry at the
**top of `generated/tokens.css`**, before `:root`. `preset.css` opens with `@import './tokens.css'`
and `tailwind.css` imports `preset.css`, so both consumers — `apps/web/src/index.css` and Storybook's
`preview.tsx` — receive the rules through the single stylesheet they already import. **No consumer
gains a font import**; that is the property that makes the app and Storybook render identically.

```css
@font-face {
  font-family: 'Inter';
  src: url('/fonts/inter/inter-variable-latin.woff2') format('woff2');
  font-weight: 400 700;
  font-style: normal;
  font-display: swap;
}
```

`format('woff2')` and not `format('woff2') tech(variations)` or the legacy
`format('woff2-variations')`: every browser that supports variable fonts accepts the plain form, and
the two hinted forms are each unsupported somewhere. An absolute `url()` and not a relative one:
these files are served as static assets under a fixed prefix (§8.3), never resolved through a
bundler, so the string is the same in every consumer and in every build mode.

`font-synthesis-weight: none` goes on `:root` in the same generated file, with a comment naming §7.3.

### 8.2 `font-display: swap`, and why not `optional`

The choice is between a first-visit reflow and a first-visit wrong face.

- **`optional`** never swaps and never shifts layout, but if the font misses its ~100 ms block window
  the browser uses the fallback **for that entire page load and never reconsiders**. In the
  application that is a reader occasionally getting the unchosen face. In the visual suite it is
  worse: a story that loses the race captures a baseline in the fallback, and the failure looks like a
  regression in whatever component happened to be captured. That is a flake generator across 1,794
  captures, and this feature has already paid once for a baseline that carries no evidence
  (research D3's `SearchBox` note).
- **`swap`** guarantees the chosen face always ends up on screen. Its cost is a possible one-time
  reflow on a cold cache, and the preload in §8.3 is what shrinks that window to near zero: the font
  request starts as the document is parsed, in parallel with the JS bundle, rather than after the
  stylesheet has been fetched and matched.

**`swap`.** The reflow is bounded, one-time and cached thereafter; a reader who silently never gets
the face would invalidate every metric T524 derives (§11) and every baseline T530 captures (§12).
Deliberately **not** specified: `size-adjust` / `ascent-override` fallback metric matching. It would
reduce the reflow further, it requires per-face measurements this file cannot make without rendering,
and it is a refinement that can be admitted later against a measured shift. It is recorded as a known
lever, not an omission.

### 8.3 Mounting and the preload — one prefix, both consumers

The same arrangement `packages/game-assets` already uses, for the same reason: a URL that is
identical in the app and in a story is the only kind that makes a baseline mean anything
(`contracts/asset-pack.md`, "Mounting"; plan.md's constitution XII row says fonts land "under one
prefix, mounted the same way `packages/game-assets` already is").

| Consumer   | How                                                                                                                                                                                                                                                                     |
| ---------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `apps/web` | `viteStaticCopy`, three targets mirroring the existing game-asset targets: `src: '../../packages/design-system/tokens/fonts/<pack>/*.woff2'`, `dest: 'fonts/<pack>'`. The `*.woff2` glob is deliberate — the licence records stay in the repository and are not served. |
| Storybook  | `staticDirs` gains `{ from: '../tokens/fonts', to: '/fonts' }` beside the existing game-assets entry.                                                                                                                                                                   |

**The preload, in `apps/web/index.html`**, one line per family:

```html
<link
  rel="preload"
  href="/fonts/inter/inter-variable-latin.woff2"
  as="font"
  type="font/woff2"
  crossorigin
/>
```

`crossorigin` is **mandatory even though these are same-origin**: fonts are always fetched in CORS
mode, and a preload without it is discarded and the file is fetched a second time — the preload then
costs bandwidth and buys nothing. This is the one attribute that silently inverts the point of the
line.

**Note for T533 (Phase 3), which also edits this file.** T533 adds the blocking inline
theme-resolution script (research D11), which **must stay the first thing in `<head>` after
`<meta charset>`** and must run before the stylesheet. The three preload links are non-blocking and
follow it. Neither task may reorder the other's element. T523 does not implement the theme script and
T533 does not touch the preloads.

**Storybook gets no preload and needs none**: the stories are not a first-paint budget, and §10's
`document.fonts.ready` wait is what makes captures correct there.

### 8.4 The page-weight budget, and the lever if it bites

Three files, expected 35–120 KB each, ≈170 KB total on a first visit, in parallel with the bundle,
cached thereafter. If a later measurement shows the display face delaying first paint on a real
connection, **the lever is to drop Fraunces' preload link — not to change `font-display`, and not to
un-ship a family.** Headings are few and a heading arriving one round trip late is the smallest
reflow of the three. Named now so the fix is not re-litigated under time pressure later.

---

## 9. The licence gate — exactly what changes, and the proof it bites

Constitution X: _"a pack whose licence is not recorded MUST NOT be added."_ Today that is enforced in
one directory. `main()` hard-codes `assets_root = REPO / "packages" / "game-assets"`, and `pr.yml`'s
`asset-packs` paths filter lists `packages/game-assets/**`, `docs/asset-packs.md`, `README.md` and the
script itself. **A font landing anywhere else is covered by nothing and does not even trigger the
job.** Both are fixed in this change.

### 9.1 What "hard-scoped" means mechanically

It is narrower than it sounds, and that is good news for the diff. Every real check in the module —
`_pack_dirs`, `check_pack`, `check_size_budget`, `check_docs_mirror` — **already takes its root as a
parameter**. The only two places a single root is assumed are `main()`'s three lines of setup and the
aggregate `check_asset_packs`, which composes the per-root checks with the one repository-wide check
(`check_disclaimer`). So the change is a composition change, not a rewrite.

### 9.2 `scripts/checks/asset_packs.py`

1. **Add a second budget constant**, beside `SIZE_BUDGET_BYTES`, with its own docstring naming
   typography-tokens.md §4.4 as its source:
   `FONT_SIZE_BUDGET_BYTES = 1 * 1024 * 1024`. Do **not** reuse or generalise the 10 MB figure: the two
   budgets are different facts with different justifications, and merging them would make one of them
   a coincidence.
2. **Add a module-level record of the roots**, each with its budget — a tuple of
   `(path, size_budget_bytes)` pairs, `packages/game-assets` at 10 MB and
   `packages/design-system/tokens/fonts` at 1 MB — with a comment saying why a font directory is an
   assets root: constitution X's gate is only enforced where it looks, and until this feature it
   looked in one place.
3. **Add a new aggregate**, `check_asset_roots(roots, docs_file, readme_file)`, which runs
   `check_pack` over every pack in every root, `check_size_budget` per root with that root's own
   budget, `check_docs_mirror` per root, and `check_disclaimer` **exactly once**. The disclaimer is a
   repository-wide anchor, not a per-root one; calling the existing aggregate twice would report its
   failure twice and is the obvious wrong refactor.
4. **Leave `check_asset_packs`'s signature untouched.** `scripts/checks/tests/test_asset_packs.py`
   calls it by keyword with a single root, and those tests are the existing game-assets coverage. The
   new aggregate is composed alongside it, not in place of it.
5. **`main()` iterates the roots.** Its per-pack report line and its `asset_packs: packages/game-assets`
   header both become per-root, printing the root's repository-relative path and then its packs.
6. **`_NON_PACK_DIR_NAMES` needs no entry**: the fonts root holds the three pack directories and
   nothing else. If it ever holds tooling, that name is added there rather than the walk being
   loosened.

**New tests in `scripts/checks/tests/test_asset_packs.py`**, in the style of the existing ones —
`tmp_path` trees, no network, no repository state:

- a font-shaped pack (`LICENCE.md` + one `.woff2`) with all five fields and a matching docs row passes;
- the same pack with one field removed fails, and the failure string **names the pack directory**;
- two roots with different budgets are each held to their own (a 1.5 MB fonts root fails while a
  1.5 MB game-assets root passes);
- the disclaimer failure is reported **once** across two roots, not twice.

### 9.3 `.github/workflows/pr.yml`

Add to the `asset-packs` filter, beside the existing four entries:

```yaml
asset-packs:
  - 'packages/game-assets/**'
  - 'docs/asset-packs.md'
  # 005 T523: the second assets root. The design-system filter above already fires on
  # this path, but the licence-gate job is gated on `asset-packs` alone, so without this
  # line a font pack could be added, changed or stripped of its record without the gate
  # constitution X requires ever running.
  - 'packages/design-system/tokens/fonts/**'
  - 'README.md'
  - 'scripts/checks/asset_packs.py'
```

The job body itself does not change — `uv run scripts/checks/asset_packs.py` now walks both roots.
Its `name:` and the comment above the run step gain the second root so the job does not describe
itself as narrower than it is.

### 9.4 The proof it bites, which T523 owes and which is not optional

Mechanically, before hand-back:

1. Delete the `- **Checked**:` line from `packages/design-system/tokens/fonts/fraunces/LICENCE.md`.
2. `uv run scripts/checks/asset_packs.py` — it must exit 1 and print
   `fraunces: LICENCE.md is missing the 'Checked' field`.
3. Restore the line; re-run; it must exit 0 and report all six packs.
4. Record both outcomes in the hand-back.

A gate that has never been observed to fail is a gate nobody has tested. This one has failed to exist
for a year in this exact directory, which is why the proof is part of the task rather than a
suggestion.

---

## 10. Determinism — the two ways this silently reverts

**A family-name mismatch is invisible.** `build-tokens.test.mjs` gains one assertion: for every entry
in `font.face`, its `family` value is the **first quoted name** in the matching `font.family` stack.
Three families, one loop, in the style of the existing Callout-tone loop. That closes the JSON half of
§4.3 step 6; the font-file half is a manual verification and §13's criteria are its backstop.

**A capture taken mid-swap is a wrong baseline.** With `font-display: swap` a story can be
screenshotted in the fallback if the capture beats the font. Add
`await page.evaluate(() => document.fonts.ready)` **after** the existing story-settled wait and
**before** the axe scan and the screenshot, in `tests/visual/stories.spec.ts`, and at the equivalent
point in `tests/visual/app-routes.spec.ts` and `tests/visual/focus-ring.spec.ts`. It is the same class
of wait as the `completing`-state wait already there, and the comment beside it should say so: the
suite already knows that "the DOM has rendered" is not "the render has finished".

---

## 11. Consequence for T524 — the scale is re-derived against real metrics

**Yes. T524 re-derives, and it may not carry a value forward on the grounds that it was already
there.** Every number in `font.json`'s `size` group was chosen — or inherited — against
`system-ui`, `Georgia` and `ui-monospace`, which is to say against nothing in particular. The three
shipped faces do not share those metrics, and a nominal step is not an optical size.

What T524 must measure, per family, from the shipped files rather than from a specimen image:

1. **x-height ÷ em and cap-height ÷ em**, for each shipped face and for the fallback it displaces.
   These set apparent size. Two faces at `1rem` with different x-heights are two different sizes to a
   reader, and body text is where this is felt.
2. **Fraunces against Georgia specifically.** Georgia has an unusually large x-height and short
   extenders; a warmer old-style face at the same nominal step will generally read **smaller** and
   more delicate. If the display steps are carried over unchanged, headings lose hierarchy against
   Inter body text — the exact failure §13 criterion 6 is written to catch. Expect the display steps
   to need re-setting rather than to survive.
3. **Fraunces' `opsz` axis makes the display role size-dependent by design.** The face drawn at 18px
   (`SiteHeader`) is not the face drawn at 30px (`PrivacyNotice` h1). T524 cannot derive the display
   ladder from one specimen; each step is looked at at its own size.
4. **JetBrains Mono's advance width ÷ em.** This sets every numeric column's width. Against the
   fallbacks it displaces, column widths move — so the rating tables must be re-checked for overflow
   and truncation at **375 first**, which is FR-018 and is the width least covered by baselines today.
5. **Line-height per step**, re-derived so the rendered line box still lands on the spacing rhythm
   T520 wrote into `space.json`. Line height is where a font swap most often breaks a grid silently.

What T524 does **not** inherit as a constraint from this file: the `weight` group (it may narrow it —
all four are real, so narrowing is a design choice, not a repair), the `tracking` group, and the whole
`role` group, which is D7's and is independent of which families were chosen. Splitting the three
meanings of the monospace treatment is owed regardless of this decision; it is only the _numbers_ that
this decision moves.

---

## 12. Consequence for T530 and the baselines

**Yes — this is an "every pixel" event.** Loading three faces repaints every glyph in the product and
in Storybook, in both themes, at all three review widths.

**And it is the second cause inside the same regeneration, not a second regeneration.** The palette
(T521, T522) is the first. T530 dispatches `.github/workflows/baselines.yml` **once**, with the cause
`palette-and-typefaces`, after both have landed. That is D6a's own stated reason this decision belongs
to phase 2 rather than to a later one: deferring the fonts would buy a third global repaint after the
retrofit, which D1 exists to prevent. **The phase pays for one regeneration in total.**

Concretely, for T523's implementer:

- **Do not dispatch `baselines.yml`.** T530 is the single dispatch for this phase, and a dispatch here
  would produce a generation carrying the fonts without the rest of the phase.
- **Do not update snapshots locally**, for any reason — research D3, and the standing rule that
  full-page baselines are authoritative only from CI's renderer.
- Expect the visual job to be red between this task and T530. That is the phase's designed state, not
  a defect, and T530's own text says the diff is uninformative here by construction: the contrast
  test, the axe scan and `visual-reviewer` carry this phase.
- When T530's regeneration is read, research D3's addendum applies unchanged: a handful of
  pre-existing files showing 9–20 pixel differences at a max channel delta of 1–2, non-repeating
  between runs, is antialiasing jitter; `composite-searchbox--rate-limited-*` churns for its own
  documented reason. Neither is evidence about the fonts.

---

## 13. Visual acceptance criteria

Phrased so `visual-reviewer` decides each from a screenshot plus this file. Checked in **both
themes** at every declared review width. Criteria 1–4 are the ones that fail if the fonts did not
actually load — the failure mode this whole task exists to make impossible, and the one that produces
no error anywhere else.

1. **The three families are three faces.** In any story carrying a heading, body text and a number —
   `ProfileSummary`, `MatchDetailPanel`, `StatValue` in a panel — the heading is a **serif**, the body
   and labels are a **sans**, and the number is **monospaced**. A screenshot where the heading and the
   body share letterforms is the fallback render and fails.
2. **The heading serif is not Georgia and not a generic serif.** On the foundation typography page
   (T5xx, Storybook), the `display` specimen is labelled `Fraunces` and shows old-style, warm
   letterforms with an evident stroke modulation — **and no eccentric alternates**: no swash, no
   flicked terminals (§3.2's `WONK` pin). Wonky glyphs in a heading fail; so does a specimen
   indistinguishable from the `serif` generic beside it.
3. **Every declared weight is a distinct weight.** The foundation page shows each family at 400, 500,
   600 and 700, and the four are visibly distinct in each. Two adjacent weights that look identical
   mean the weight axis is missing or the file did not load; a "bold" with smeared, thickened stems
   means synthesis and also fails.
4. **`0` is not `O`, and `1` is not `l`.** In the story showing an unresolved identifier —
   `ProfileSummary`'s fallback heading, `PlayerResultRow`'s unverified Steam id — the digits are
   unambiguous at `text-xs`. This is the reason JetBrains Mono was chosen (§3.3); if it fails, the
   choice was wrong.
5. **Digits align down a column.** In `ProfileSummary`'s ratings table and `MatchRow`'s table at 1280,
   ratings of three and four digits align on their right edge **and** their digit stems line up
   vertically. Ragged stems mean the numeric role is not on the mono family.
6. **The heading still outranks the body.** In any panel showing a `display` heading above `body`
   text, the heading is unmistakably larger and heavier at a glance, without measuring. This is the
   criterion that catches Fraunces' smaller optical size at a step carried over unchanged from the
   fallbacks — T524's job to fix and this criterion's job to notice.
7. **No mid-swap capture.** No baseline shows clipped, overlapped or doubled text, and no two
   paragraphs in one screenshot are set in two different sans faces. Either is a capture taken while
   the font was still arriving (§10).
8. **No tofu.** In a story carrying a non-Latin alias, the alias renders as real glyphs — from the
   reader's own system, per §7.2 — never as replacement boxes.
9. **Numbers first, unchanged from the palette record.** No typographic treatment makes a measured
   number less legible than the prose beside it. In `StatValue`, `MatchRow` and `ProfileSummary` the
   numeric value remains the most legible thing in its row.

---

## 14. What the implementer does with this

In order. Steps 1–3 are gated by §4.3 — a failed verification stops the task.

1. Fetch the three distribution packages named in §4.2, verify each file against §4.3's seven steps,
   copy them in under §4.1's paths and filenames, and record the exact versions.
2. Write the three `LICENCE.md` files from §5 verbatim, substituting only `<VERSION>`.
3. Transcribe §6 into `docs/asset-packs.md` — the typeface table and the three rejected-source rows.
4. Add §7.4's `face` group to `font.json` and rewrite its `$comment` to point at this file. Change
   nothing in `family`, `size`, `weight` or `tracking` — those are T524's.
5. Extend `build-tokens.mjs` with `fontFaceRules()` (§8.1) and `:root { font-synthesis-weight: none }`,
   then run `pnpm --filter design-system tokens:build`.
6. Add §10's `face`-vs-`family` assertion to `build-tokens.test.mjs`.
7. Mount the fonts in both consumers (§8.3): `viteStaticCopy` targets in `apps/web/vite.config.ts`,
   `staticDirs` in `packages/design-system/.storybook/main.ts`. **Both, or the baselines and the app
   disagree.**
8. Add the three preload links to `apps/web/index.html`, each with `crossorigin`. Do not add the theme
   script — that is T533, and §8.3 records the ordering both tasks must respect.
9. Extend `scripts/checks/asset_packs.py` per §9.2 and its tests per the same section; extend
   `pr.yml`'s `asset-packs` filter per §9.3.
10. Perform §9.4's proof that the gate bites, and record both outcomes in the hand-back.
11. Add §10's `document.fonts.ready` wait to the three visual specs.
12. **Do not regenerate baselines** (§12). Hand §11 to T524 and §13 to `visual-reviewer`.

---

## 15. What this file deliberately does not decide

- **The type scale.** T524, against §11's measurements.
- **Whether the `weight` group keeps four steps.** T524 may narrow it; all four are real either way.
- **Italic.** No italic face ships, because no component asks for one. If one is ever needed it is a
  new pack, a new licence record and a new `face` entry, admitted through
  `GOVERNANCE.md`'s token admission test — never a `font-style: italic` synthesised from the upright.
- **Fallback metric overrides** (`size-adjust`, `ascent-override`). A real refinement, requiring
  measurements this file cannot make, admissible later against an observed layout shift (§8.2).
- **A second subset.** Cyrillic, Greek and CJK stay with the reader's system by design (§7.2), and
  admitting a subset later is a size-budget decision against §4.4, not a typeface decision.
