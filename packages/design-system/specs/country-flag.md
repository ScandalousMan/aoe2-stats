# CountryFlag

**Component**: `src/components/CountryFlag/` (T436)
**Feature**: 004, US2 — consumed by `ProfileSummary`'s `IdentityBar`
([`profile-summary.md`](./profile-summary.md) §12), itself consumed by
`apps/web/src/routes/dashboard.tsx`, `players.$profileId.tsx` and `players.$profileId.matches.tsx`.
**Requirements**: FR-008, FR-010, FR-013. SC-002, SC-005.
**Amended by §11 (004, Phase 8, T455)**: FR-008 now requires the country name to be conveyed through
a [`Tooltip`](./tooltip.md) on the flag — on hover, on keyboard focus, and with an accessible name —
and **not** as an adjacent text element. **Read §11 before implementing anything below**: it
supersedes §2's always-visible name, §4's "never a tab stop", §7's wrap rule, §8's "not focusable, no
tooltip" and §10's first criterion. §11.1 lists exactly what changes and what stands.
**Depends on**: [`game-asset-tokens.md`](./game-asset-tokens.md) — the `icon` size family (DS-7,
closed). [`profile-summary.md`](./profile-summary.md) §2 — `CountryLabel`'s existing convention
(country in text; a flag accompanies it, never replaces it), which this component implements rather
than replaces. [`tooltip.md`](./tooltip.md) — from §11 onward.
**Asset origin** (README rule 3): the flag is a file in `packages/game-assets/flags/`, whose
`LICENCE.md` records source (`lipis/flag-icons`, the 4x3 set), licence (MIT), permitted usage, ruling
and check date (`specs/004-visual-parity/contracts/asset-pack.md`, enforced by
`scripts/checks/asset_packs.py`). Flags are **not** game assets — constitution X does not reach them
and the Game Content Usage Rules reasoning does not apply — but the pack carries the same record
because the check walks every directory under `packages/game-assets/`. **This component never imports
a flag.** It receives a URL as a prop, exactly as `CivilisationIcon` and `MapThumbnail` do.

## 1. Purpose

Show which country a player plays from, as the flag a reader recognises without reading, beside the
country's name in words — so a profile says where someone is from instead of showing the two-letter
code the API happens to serve.

## 2. Anatomy

```
CountryFlag                    one inline group; the flag and the country name are a single unit
├─ Frame     a 4:3 box with a 1px `border` hairline and `radius-sm`, drawn ONLY when an image is
│            actually rendered inside it (§4 empty)
│  └─ Image  <img>, `object-fit: contain`, 4:3, never stretched to square and never cropped
└─ Name      the country name, always rendered, always selectable text
```

The three rules stated once in [`match-history.md`](./match-history.md) §12.1 govern this component
too. All three decide something here:

1. **Imagery is never the only carrier of meaning** (README rule 4). There is no `flagOnly` and no
   `labelHidden` prop, and adding one is a spec change rather than an implementation choice. At
   `icon-sm` several flags are genuinely indistinguishable — Chad and Romania, Monaco and Indonesia,
   Ireland and Côte d'Ivoire differ by hue alone at 16px — so a flag without its name is not a
   compressed fact, it is a wrong one.
2. **The absent-asset state is the prop being `undefined`**, rendering the readable label alone.
   Never a globe glyph, a grey rectangle, a "?" tile or a reserved gap. **The frame does not survive
   the image**: an empty bordered box is a placeholder drawn in CSS, and it says "something should be
   here" and nothing else (`map-thumbnail.md` §2's identical rule, for the identical reason).
3. **The name is resolved upstream, never here.** The API serves `country` as an ISO 3166-1 alpha-2
   code — `"country": "fr"` (`contracts/http-api.md`) — and this component ships no country table,
   parses no code and knows nothing about ISO. It receives `countryName` already in words, the same
   way `CivilisationIcon` receives `civ_name` already resolved. §2a fixes who resolves it and how,
   because "somewhere upstream" is not an answer an implementer can act on.

### 2a. Who turns `"fr"` into "France", and why not this component

`apps/web/src/features/players/format.ts` (T438) resolves the code with the platform's own
`Intl.DisplayNames(['en'], { type: 'region' })`. Three consequences worth stating, because each is a
decision someone would otherwise make differently:

- **No new dependency, no new pack, no ~260-row mapping to maintain.** The browser already holds
  this table; shipping a second copy of it would be a third place for country names to drift.
- **The locale is fixed to `en`, never the viewer's.** Constitution XI is English-only, and a
  locale-dependent label would also make every visual baseline machine-dependent — the name under the
  flag would differ between a French reviewer's laptop and CI, and the diff would look like a
  regression.
- **A value that is not a two-letter code is shown verbatim.** `country` is typed `str | None` all
  the way from the provider (`packages/providers/src/aoe2stats_providers/base.py`), so a source that
  one day sends `"Germany"` instead of `"de"` renders "Germany" rather than a mangled lookup. The
  only thing a non-code value can be is a name already.

The flag URL is resolved the same way and in the same place: `countryFlag(code)` from
`packages/game-assets` returns a URL or `undefined`, and `undefined` is passed straight through
(plan.md's Structure Decision — the design system never reaches into a pack).

## 3. Variants and sizes

No tone or style variants: a country is a fact, and a fact has one appearance.

| Size             | Token            | Where                                                                               |
| ---------------- | ---------------- | ----------------------------------------------------------------------------------- |
| `sm` _(default)_ | `icon-sm` (16px) | Inline beside an alias — `ProfileSummary`'s `compact` variant                       |
| `md`             | `icon-md` (24px) | `ProfileSummary`'s `board` identity bar, where the profile's name owns the page top |

These are `game-asset-tokens.md`'s per-component mapping. **Sizes come from `iconTokens` /
`--ds-icon-*`, never from a Tailwind size utility** — no Tailwind namespace maps this family
(`build-tokens.mjs`'s own note), so `w-4` is a hard-coded value even where it equals the token.

**The token sets the box's _height_; the width follows at 4:3.** The pack is `flag-icons`' 4x3 set
(`packages/game-assets/flags/LICENCE.md`), and a flag squeezed into a square is a different flag's
proportion — aspect is part of how a flag is recognised. `object-fit: contain` inside the 4:3 box
handles any source that is not exactly 4:3; nothing is ever stretched or cropped. Height, not width,
is what the token fixes, so a flag lines up with the text beside it rather than with the icons above
it.

Below `icon-sm` a flag is a coloured smudge, so there is no smaller size and the component never
shrinks responsively (§7).

## 4. States

- **default** — framed flag, then the country name.
- **hover** — none of its own. It is a fact, not a control: no brighten, no scale, no tooltip
  revealing the code. Whatever container it sits in owns its own hover.
- **focus-visible** — none. Never a tab stop, no `tabindex`.
- **active** — none, for the same reason.
- **disabled** — never. A player's country is not a capability, and a dimmed flag would read as
  "stale", a claim nobody made.
- **loading** — the component has no loading state of its own **and the caller renders no skeleton in
  its place.** This deliberately differs from `CivilisationIcon` and `MapThumbnail`, whose callers do
  reserve a footprint: a civilisation and a map certainly exist for every match, so reserving their
  space prevents a reflow. **Whether a country exists at all is not known until the data arrives**, so
  a reserved flag-shaped box would be a placeholder for a fact that may never come, and would leave a
  gap on every profile without a country. `ProfileSummary`'s identity-bar skeleton covers this
  position as part of the alias line (§12.6).
- **error** — `flagUrl` resolved but the image fails to load or decode (a pack file removed, a stale
  build, an offline cache): the `onError` handler removes **the image and its frame together**,
  leaving the name alone — **byte-identical to the `undefined` render below**. No broken-image glyph
  ever reaches the screen.
- **empty** — three absences. The first two render identically to each other; the third renders
  nothing at all, and the difference is FR-008's whole point:
  - **A country the pack does not cover** (`flagUrl === undefined` — a code outside the 249 files, or
    a value that is not a code): the name alone, in the colour the caller's context sets, with no
    frame and no reserved space. Nothing about the line says a picture was expected.
  - **The image failed** (§4 error): the same render, to the pixel.
  - **No country at all** (`countryName` absent or blank after trimming): **the component renders
    `null`** — no flag, no label, no em dash, no "Unknown country", no reserved width. The parts
    around it close up, and a profile without a country looks like a profile that never had one
    rather than one that lost it. This is FR-008's "omit it cleanly", and it is the same mechanism
    `PlayerColourSwatch` §2a uses for a blank `playerName`: the component itself refuses to render
    half of a pair.

## 5. Tokens used

Colour: `border` for the frame hairline. README's own rule for that token — "decorative separators
only, never a control boundary" — is exactly what this is, and it is why the frame may be `border`
and not `border-strong`: the flag carries no information the name beside it does not, so its
boundary carries none either (`map-thumbnail.md` §5's identical reasoning; contrast
`player-colour-swatch.md`, whose frame _is_ meaning-bearing and therefore owes 3:1). The frame still
matters visually: a mostly-white flag (Japan, Poland, Finland) would otherwise dissolve into the
light theme's parchment and read as a half-loaded image.

The **name sets no colour of its own** — it inherits `currentColor` from the caller's context, as
`CivilisationIcon` does. In `ProfileSummary`'s identity bar that is `text-secondary` (§12.4): the
country qualifies the person, it is not the person.

The image is never tinted, filtered, theme-adjusted or given a drop shadow. A national flag is
rendered as authored, in both themes.

Typography: `sans`, weight normal, at the size of the text the pair sits in (`sm` in the identity
bar, `xs` in a compact line). Never `mono`: a country name is prose, not an identifier — and the
whole point of §2a is that the code never reaches the screen.

Size: `icon-sm` / `icon-md` (§3). Radius: `sm` on the frame, matching `CivilisationIcon`'s mark
rather than `MapThumbnail`'s larger `md`, because these are the two small marks that sit inline with
text.

Elevation: none. Motion: **none at all** — no fade-in on decode. README rule 1: nothing animates
beside a number, and the identity bar sits directly above the ratings. Under
`prefers-reduced-motion` nothing changes, because there was nothing to reduce.

Gaps in play: none. DS-7 is closed by the `icon` family this component consumes.

## 6. Spacing

| Between      | Step      |
| ------------ | --------- |
| Flag to name | `space-2` |

That is the whole spacing surface. The pair adds no outer margin; the caller's layout gap
(`profile-summary.md` §12.5) positions it.

## 7. Responsive

- **375 / 768 / 1280** — the size is set by the caller's variant (`md` in the board identity bar,
  `sm` in `compact`), never by the viewport. It does not shrink on a narrow screen.
- The pair **never wraps between the flag and its name**. If the line is too narrow the name wraps
  within itself and the flag stays with the first line; a flag orphaned onto its own line is an
  image with no label, which is §2's rule 1 broken by layout instead of by prop.
- The pair may wrap **as a unit** onto the line below the alias at 375 (`profile-summary.md` §12.7)
  — that is the caller's decision, and this component neither prevents nor requires it.
- At 200% zoom the box scales with the token (rem-based), so the flag grows with the name beside it.

## 8. Accessibility

- The image is `<img alt="">` — **decorative**, because the accessible name is the visible country
  name immediately beside it. Never `alt="France"` (a screen reader would say the country twice) and
  never `alt="flag"`, which names the widget rather than the fact. This is also the treatment
  `profile-summary.md` §2 and `player-search.md` §2 already required of any flag glyph:
  `aria-hidden`, beside the country in text, never instead of it.
- `width`/`height` (or an equivalent CSS aspect box) come from the size token and the 4:3 rule, so
  the image reserves its space before it decodes — no layout shift. `loading="lazy"`,
  `decoding="async"`.
- Not focusable, no `title`, no tooltip. The component is non-interactive, so WCAG 2.5.8's 44px
  target does not apply. If a call site ever wraps the pair in a link — nothing in 004 does — that
  link's hit area is at least `icon-xl` (44px).
- Contrast: the name inherits the caller's colour and is measured there
  (`profile-summary.md` §12.8). The flag carries **no** contrast obligation, because it carries no
  information the adjacent text does not; the `border` hairline is decorative and is therefore
  exempt from 1.4.11, which is precisely why it may be `border`.
- Colour is never the only carrier: converting the frame to greyscale leaves the country readable,
  because it was always a word.
- The country name is selectable text, never baked into the image.

## 9. Where this component may and may not appear in 004

`ProfileSummary`'s `IdentityBar` only. Two adjacent places take a flag in a later change, not this
one:

- **`PlayerResultRow`** (`player-search.md`) is unchanged by 004. Its own §2 permits "a
  free-licensed, `aria-hidden` glyph beside the country name" — which is exactly this component — but
  its §9 acceptance criterion currently reads "no flag illustration in any frame", so adding one is
  an amendment to that spec, not a call-site choice.
- **`MatchRow` / `MatchDetailPanel`** receive `country` per participant on the wire
  (`contracts/http-api.md`, `participants[]`) and render **no flag**: `match-history.md` §12.3 caps
  what a row shows precisely so imagery does not push the figures off the line (README rule 1). Eight
  flags in a row is the trade that spec already settled against.

Stating this here is what stops a flag from appearing in three places with three different sizes
before anyone notices there was never a decision.

## 10. Visual acceptance criteria

- [ ] Every story renders a country name. **No story anywhere shows a flag without its name beside
      it** — including the size stories.
- [ ] The uncovered-country story (`flagUrl` undefined) shows the name alone: no frame, no grey box,
      no globe, no "?" tile, no reserved gap. Beside a covered story in the same frame, the two names
      sit on the same baseline.
- [ ] The failed-image story is **pixel-identical** to the uncovered-country story — the two
      screenshots overlay with no difference, frame included (that is, neither has one).
- [ ] The blank-`countryName` story renders **nothing at all** where the pair would be, and the
      elements around it close up: overlaid on a story with a country, everything before it sits at
      the identical position.
- [ ] No broken-image glyph appears in any story, in either theme; the browser network panel shows no
      request under `/game-assets/flags/` returning 404 (SC-005).
- [ ] A mostly-white flag (Japan and Poland are the two stories) shows a **visible boundary** against
      the light theme's parchment — no flag bleeds into the background.
- [ ] The `sm` and `md` stories in one frame are visibly different sizes; every flag is **wider than
      it is tall** (a square flag is a failure of this criterion, not a pass), undistorted, and crisp
      at 1× and 2× device pixel ratio.
- [ ] No story shows a two-letter code anywhere in the frame — the code never reaches the screen
      (§2a), which is SC-002 in miniature.
- [ ] Converting any story to greyscale leaves the country identifiable, because the name is doing
      the work (README rule 4).

---

## 11. The name is the flag's tooltip, not the text beside it (004, Phase 8 — T455)

FR-008 was amended by Clarifications 2026-09-02 after the T447 walk: the country name "MUST be
conveyed through a design-system Tooltip on the flag — revealed on hover and on keyboard focus, with
an accessible name for assistive technology — and MUST NOT be rendered as an adjacent text element."

This section supersedes parts of §§2–10 rather than sitting beside them, and it changes the two
things this component was most emphatic about: that the name is always visible, and that the flag is
never a tab stop. Both changes are stated in full below, because a reader of §2 alone would implement
the opposite of what now holds.

### 11.1 What §11 supersedes, and what it leaves standing

| Earlier text                                                                                | Status                                                                                                                                                                                                              |
| ------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| §2 anatomy's `Name` part, "always rendered, always selectable text"                         | **Superseded when a flag renders** (§11.2). The name becomes the `Tooltip`'s content. It returns to being visible text, unchanged, in exactly the two cases where no flag renders (§11.4).                          |
| §2 rule 1, "imagery is never the only carrier of meaning… there is no `flagOnly` prop"      | **Standing, and satisfied differently** (§11.3). The carrier is still text; it is in the accessibility tree at all times and revealed three ways. What is gone is the requirement that it be _permanently painted_. |
| §2 rule 2 (absent asset is the prop `undefined`) and rule 3 (the name is resolved upstream) | **Unchanged.** §2a, the props (`countryName`, `flagUrl`) and `ViewedProfile`'s fields are untouched — this is a presentation change and needs no new data.                                                          |
| §3 sizes (`icon-sm` / `icon-md`, 4:3, no responsive shrink)                                 | **Unchanged for the flag itself.** §11.5 adds an interactive box around it; the flag's own size token does not change.                                                                                              |
| §4 hover, "none of its own… no tooltip revealing the code"                                  | **Superseded** (§11.6). Note what that sentence forbade: a tooltip revealing the **code**. The code still never reaches the screen (§2a), which is SC-002, and is untouched.                                        |
| §4 focus-visible and active, "none. Never a tab stop, no `tabindex`"                        | **Superseded** (§11.6). The flag is now a tab stop with a visible focus ring. This is the change a later reviewer is most likely to assume was handled, so §11.6, §11.8 and §11.9 each state it.                    |
| §4 disabled, loading, error, empty                                                          | **Unchanged**, with §11.4 saying what the two absent-asset cases render now that no permanent label sits beside the flag.                                                                                           |
| §7 "the pair never wraps between the flag and its name"                                     | **Retired.** There is no pair to wrap. §11.7 replaces it.                                                                                                                                                           |
| §8 "not focusable, no `title`, no tooltip… the 44px target does not apply"                  | **Superseded** (§11.8). It is focusable, it has a tooltip (never a `title`), and the 44px target now applies.                                                                                                       |
| §9 "`ProfileSummary`'s `IdentityBar` only", and the two places that may not take a flag     | **Unchanged.** `PlayerResultRow` and `MatchRow` are untouched by this amendment, and neither gains a flag or a tooltip.                                                                                             |
| §10's first criterion, "no story shows a flag without its name beside it"                   | **Superseded** by §11.9, which inverts it: no story shows a name beside a flag.                                                                                                                                     |

### 11.2 What renders

`CountryFlag` renders a [`Tooltip`](./tooltip.md) whose trigger is the framed flag and whose content
is the country name.

```
CountryFlag (superseding §2's anatomy wherever a flag actually renders)
└─ Tooltip                     relation="label", placement block-start (tooltip.md §3)
   ├─ Trigger  <button type="button">, hit area icon-xl (44px), containing:
   │  └─ Frame     §2's 4:3 box, `border` hairline, `radius-sm` — unchanged
   │     └─ Image  <img alt="">, object-fit contain — unchanged
   └─ Content  role="tooltip", ALWAYS in the DOM, `hidden` while closed:
      ├─ "Country: "   visually hidden qualifier
      └─ "France"      the visible tooltip text — §2a's already-resolved `countryName`
```

The visually hidden qualifier is `tooltip.md` §8's rule: without it the trigger announces "France,
button", which names a country but not what the country is _of_. With it the accessible name is
"Country: France", the visible text is still the bare name, and WCAG 2.5.3 (label in name) holds
because the visible text is contained in the accessible name.

**The props do not change.** `countryName` and `flagUrl` mean what they meant; only where
`countryName` is drawn has changed. `apps/web` resolves both exactly as §2a specifies, and
`ViewedProfile` is untouched — nothing on the wire moves for this.

### 11.3 Why this does not break README rule 4, and what would

§2 rule 1 argued, correctly, that several flags are indistinguishable at 16px, so a flag without its
name is not a compressed fact but a wrong one. That argument is about the fact being **unreachable**,
not about it being permanently painted. It survives here on three conditions, and this component
fails rule 4 the moment any one of them is dropped:

1. **The name is in the accessibility tree whether the tooltip has ever opened or not** —
   `tooltip.md` §8's always-in-the-DOM content element. A screen reader cannot produce a hover event;
   an implementation that mounts the content on open turns the country into a sighted-pointer-only
   fact, screenshots identically to a correct one, and is the single likeliest defect in T456.
2. **Three independent routes reveal it** — hover, keyboard focus and press/tap (`tooltip.md` §4).
   Drop the third and a touch user, who has no hover and generally no `:focus-visible`, cannot reach
   the country at all on the viewport where the flag is smallest.
3. **The trigger is a real 44px control with a visible focus ring**, so the fact is reachable by
   keyboard at all, and visibly so.

What this section does **not** license: a civilisation icon, a map thumbnail or a player colour
swatch losing its adjacent name to a tooltip. Those sit in a match row where the name is already the
primary carrier and the mark is the accompaniment (`match-history.md` §12.3), and `tooltip.md` §9
forbids it by name. The country is the one fact in this system whose permanently visible label cost
more line than the fact was worth.

### 11.4 The two absences where the name is still visible text

Nothing hangs a tooltip on a flag that is not there. §4's first two empty cases therefore render
**exactly as §4 already specified — the country name alone, as plain, selectable text, with no
frame, no button, no tab stop and no tooltip**:

- **A country the pack does not cover** (`flagUrl === undefined`).
- **The image failed to load or decode** (§4 error) — still byte-identical to the case above.

This does not violate FR-008's "MUST NOT be rendered as an adjacent text element". _Adjacent_ is the
operative word: FR-008 forbids the name sitting **beside a flag**, which is the "🇫🇷 France" the T447
walk found. Where there is no flag, the name is adjacent to nothing — it is the entire render, and
the alternative is a reader who is never told the country at all.

**No country at all** (`countryName` absent or blank after trimming) is unchanged: the component
renders `null`. `tooltip.md` §4's empty state agrees from the other side — a `Tooltip` with blank
content renders no button and no surface — so the two components cannot disagree about which of them
suppresses the render.

### 11.5 Sizes and the interactive box

The flag's own size is unchanged: `icon-sm` in `compact`, `icon-md` in `board`, 4:3, height set by
the token (§3).

**The trigger's hit area is `icon-xl` (44px) in both axes at both sizes**, reached by padding on the
button itself, never by a transparent overlay (`tooltip.md` §6). The flag is centred inside it, and
the visible boundary remains the 4:3 frame, not the button's box — the flag does not grow, and no
new border appears around the padding.

What that costs, stated so nobody re-derives it: in `board` the identity bar's height is set by the
64px avatar, so the 44px box costs nothing. In `compact` the row already contains the
`ProfileSwitcher` trigger — a `Button` at 40px pointer / 48px touch — so the box adds **at most 4px**
to the row on a pointer viewport and nothing at all on a touch one. That is the whole price of the
country being reachable rather than decorative.

### 11.6 States — superseding §4's hover, focus-visible and active

The eight states are `tooltip.md` §4's, applied here. The three §4 declared absent:

- **hover** — the pointer over the flag opens the tooltip after `motion.duration.normal`; it closes
  `motion.duration.fast` after the pointer has left **both** the flag and the surface. The flag
  itself does not brighten, scale, lift or tint: the tooltip appearing is the entire hover
  affordance, and a national flag is not re-rendered to acknowledge a cursor.
- **focus-visible** — **the flag is a tab stop.** Reaching it by Tab opens the tooltip **immediately,
  with no delay**, and the trigger shows the one uniform focus ring (`outline-2 outline-offset-2` in
  `focus-ring`, gap DS-4) around the button's box, unclipped, in both themes. **The tooltip appearing
  is not a substitute for the ring** — both are in the same frame. Opening on `:focus-visible` and
  not `:focus` is what stops a mouse click from stranding a tooltip open after the pointer has gone.
- **active** — pressing (click, Enter, Space or tap) pins the tooltip open until an explicit dismiss;
  Escape dismisses it and leaves focus on the flag. On touch this is the only route (§11.3), which is
  why it is specified rather than left to the implementation.

**disabled** — never, and now for a second reason on top of §4's: a `disabled` button is neither
focusable nor hoverable, so disabling this one would make the country unreachable rather than merely
dim (`tooltip.md` §4).

**loading**, **error** and **empty** are §4's, with §11.4 above.

### 11.7 Responsive — superseding §7's wrap rule

- **375 / 768 / 1280** — the flag's size is still the caller's variant, never the viewport (§3).
- **There is no pair, so there is nothing to wrap between.** §7's rule against orphaning the flag from
  its name is retired: the flag is a single 44px mark that moves as one unit, and the name travels
  with it in the tooltip by construction rather than by a layout rule.
- The tooltip's placement, flipping, inline shifting and minimum viewport margin are `tooltip.md`
  §3a and §7; nothing here overrides them.
- At 200% zoom the flag, the button box and the tooltip text all scale with the token (rem-based).

### 11.8 Accessibility — superseding §8

- The `<img>` stays `alt=""`. It is decorative **inside a button whose accessible name is the
  country** — `aria-labelledby` pointing at the tooltip content (`tooltip.md` §8,
  `relation="label"`). Never `alt="France"`, which would name the country twice inside one control,
  and never `alt="flag"`.
- **The accessible name resolves with the tooltip closed**, because the content element is in the DOM
  with the `hidden` attribute at all times. This is FR-008's "with an accessible name for assistive
  technology", verbatim, and it is not something a screenshot can show — it is asserted in T456's
  unit test, not in a baseline.
- **The flag is now focusable and now owes the 44px target** (§11.5), reversing §8's two claims.
  Anything that reads "not focusable" above this section is superseded.
- Keyboard, in full: Tab in (opens), Tab out (closes), Enter and Space pin and unpin, Escape
  dismisses without moving focus and it stays dismissed until focus leaves and returns. No arrow
  keys — this is one control (`tooltip.md` §8).
- Contrast: the tooltip's `text-primary` on `surface-raised` is README's measured pair in both
  themes. The flag's `border` hairline stays decorative and exempt (§5). The focus ring is
  `focus-ring` on whatever the caller paints — `background`, for `ProfileSummary` (5.9 light).
- Colour is never the only carrier: the country is a word, reachable three ways, and greyscaling the
  flag loses nothing that was not already text.
- **The country name in the tooltip is not selectable** — nothing in a tooltip is. That is a real
  loss against §8's "selectable text, never baked into the image", accepted because a country is not
  a value anyone copies, and refused for anything that is: `tooltip.md` §2 rule 2 keeps every figure
  off that surface precisely so this trade never has to be made about a number.

### 11.9 Visual acceptance criteria — replacing §10's first criterion, adding to the rest

§10's criteria stand except its first, which is inverted below. Half of these are pointer- or
keyboard-only and are judged against stories that force the state open (`tooltip.md` §10) — a suite
of default captures verifies none of them and passes anyway.

- [ ] **No story shows a country name as text beside a flag.** In the default story the flag stands
      alone and the frame contains no country word anywhere.
- [ ] The **hover story** shows the country name in a tooltip above the flag, in both themes.
- [ ] The **keyboard-focus story** shows the tooltip open **and** the focus ring visible and
      unclipped around the flag's button box, in the same frame, in both themes. A frame with one and
      not the other fails this criterion.
- [ ] The **pinned (pressed) story** shows the tooltip open with no pointer over the flag and no
      focus ring — the touch route.
- [ ] The **after-Escape story** shows no tooltip and a still-visibly-focused flag.
- [ ] The open tooltip sits **above** the flag, is opaque, and covers no figure in the frame.
- [ ] Overlaying the closed and open default stories, every element sits in the identical position —
      opening the tooltip reflows nothing.
- [ ] The flag's button box measures at least 44×44px at 375, while the flag drawn inside it is still
      `icon-sm` / `icon-md`, still wider than it is tall, and still framed by the same hairline.
- [ ] The **uncovered-country** and **failed-image** stories show the country name as plain visible
      text with **no flag, no frame and no focus ring**, are pixel-identical to each other, and
      tabbing through them stops on nothing.
- [ ] The **blank-`countryName`** story renders nothing at all, and tabbing through it does not stop
      where the flag would be.
- [ ] No story shows a two-letter country code anywhere — **including inside a tooltip** (§2a,
      SC-002).
- [ ] No caret, arrow, dotted underline or "?" affix appears on or near the flag in any story.
