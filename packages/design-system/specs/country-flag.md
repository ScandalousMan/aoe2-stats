# CountryFlag

**Component**: `src/components/CountryFlag/` (T436)
**Feature**: 004, US2 — consumed by `ProfileSummary`'s `IdentityBar`
([`profile-summary.md`](./profile-summary.md) §12), itself consumed by
`apps/web/src/routes/dashboard.tsx`, `players.$profileId.tsx` and `players.$profileId.matches.tsx`.
**Requirements**: FR-008, FR-010, FR-013. SC-002, SC-005.
**Depends on**: [`game-asset-tokens.md`](./game-asset-tokens.md) — the `icon` size family (DS-7,
closed). [`profile-summary.md`](./profile-summary.md) §2 — `CountryLabel`'s existing convention
(country in text; a flag accompanies it, never replaces it), which this component implements rather
than replaces.
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
