# PlayerAvatar

**Component**: `src/components/PlayerAvatar/` (T436)
**Feature**: 004, US2 — consumed by `ProfileSummary`'s `IdentityBar`
([`profile-summary.md`](./profile-summary.md) §12).
**Requirements**: FR-008a, FR-013, FR-015. SC-002, SC-004.
**Depends on**: [`game-asset-tokens.md`](./game-asset-tokens.md) — the `icon` size family (DS-7,
closed). [`shared-primitives.md`](./shared-primitives.md) — `Skeleton`, for the caller's loading
footprint.
**Asset origin** (README rule 3): **none — nothing is copied into this repository.** The image is the
player's own Steam avatar, fetched by the browser from `avatars.steamstatic.com` at render time from
a hash the companion provider supplies (spec.md's clarification of 2026-08-30; FR-008a). It is not a
game asset, it is not a pack, and the constitution X licence gate has no surface here. The hash is
personal data and is recorded as such in `docs/privacy/processing-register.md` (T427).

## 1. Purpose

Put a face at the top of a profile, so a page about a person opens with that person rather than with
the number `1807091`.

## 2. Anatomy

```
PlayerAvatar                    a single square box; there is no label part — the alias is the
│                               caller's, and is mandatory (§2a)
├─ Frame        square, 1px `border-strong`, `radius-md`, `surface-sunken` fill. Drawn in EVERY
│               state, loaded and unloaded alike — it is the placeholder AND the picture's frame
└─ Image        <img>, `object-fit: cover`, painted over the fill. Removed by `onError`; absent
                entirely when there is no hash (§4)
```

Two elements, never more. **The component renders no name**, because at every call site the alias or
the fallback heading is already immediately beside it (`profile-summary.md` §12.3) and rendering it
twice would put the same name in the same line twice — the same rule and the same reason as
`player-colour-swatch.md` §2.

### 2a. The avatar is never the only carrier of identity

README rule 4, applied to a picture of a person. The avatar sits beside a heading that always
resolves to something — an alias, or the numeric id in words (`profile-summary.md` §12.3's rule 1) —
so nothing on the page depends on recognising a face. A call site that renders `PlayerAvatar` without
a name beside it has broken this rule; there is no prop that permits it and none may be added.

### 2b. This is the one component in the system that builds a URL, and the exception is bounded

`CivilisationIcon`, `MapThumbnail` and `CountryFlag` all take a resolved URL as a prop, because their
resolvers must run where the packs live (`packages/game-assets`' build-time glob) and because
`undefined` is a coverage answer only the pack can give. **`PlayerAvatar` takes the hash and builds
`https://avatars.steamstatic.com/<hash>_full.jpg` itself** (FR-008a, FR-015, data-model.md §4
"Profile presentation", T436's own wording). Three reasons, and they do not generalise:

- **There is nothing to resolve.** The template is one constant string with one hole in it. There is
  no coverage set, no key normalisation and no pack that could answer "not covered".
- **Only this component can observe the failure.** The degrade is decided by the browser's `onError`,
  which fires here and nowhere upstream. Building the URL where the fallback lives keeps the two
  halves of FR-008a in one file.
- **The alternative was rejected on the wire.** `contracts/http-api.md` states it as a rule that
  binds every route: `avatar_hash` "is a hash, never a URL; the CDN URL is built client-side". A URL
  in the response would put a third-party host into this service's API contract, and nothing in
  `packages/providers` or `apps/api` constructs one.

Consequences an implementer owes:

- **Exactly one occurrence of the host string in the repository's front end**, in this file. Greppable
  (§9), and T436's own check.
- **No `src`, `baseUrl` or `href` override prop.** An override would let any call site point the
  avatar at any host and would make the single-occurrence check meaningless.
- **The hash is URL-encoded before interpolation.** The value is an unverified third-party string
  (constitution IX); encoding it means a value the provider never sanitised cannot change the shape
  of the URL.
- **A `<img src>`, never a CSS `background-image`.** A background image cannot fire `onError`, so the
  identical-render rule in §4 would become unenforceable — the failure would show as an empty box by
  luck rather than by design.
- **The browser makes this request, not the service.** Constitution III is untouched: no code in
  `apps/*` or `packages/core` opens a connection (FR-015 says so in as many words).

## 3. Variants and sizes

No tone or style variants: a person has one appearance.

| Size             | Token             | Where                                                                |
| ---------------- | ----------------- | -------------------------------------------------------------------- |
| `sm`             | `icon-lg` (32px)  | `ProfileSummary`'s `compact` variant — a page header above a list    |
| `md` _(default)_ | `icon-2xl` (64px) | `ProfileSummary`'s `board` identity bar — the profile page's subject |

These are `game-asset-tokens.md`'s per-component mapping. **Sizes come from `iconTokens` /
`--ds-icon-*`, never from a Tailwind size utility** (`build-tokens.mjs`'s own note).

**The box is square, and the corner is `radius-md`, not `full`.** Steam serves a square image;
cropping it to a circle throws away the corners of a picture the person chose, and a circle in this
system reads as a status dot — `player-colour-swatch.md` §5 refuses `full` for the same reason. A
square with a softened corner also matches the framing `MapThumbnail` already uses, so the two
largest images in the product belong to one family. `object-fit: cover` handles a source that is not
exactly square; the image is never stretched.

## 4. States

- **default** — the image, filling the frame.
- **hover** — none of its own. In 004 the avatar is never interactive: on a profile page you are
  already where a link would take you. It does not lift, brighten, zoom or reveal a larger portrait.
- **focus-visible** — none. Never a tab stop, no `tabindex`.
- **active** — none.
- **disabled** — never. There is nothing about a person that can be unavailable, and a dimmed avatar
  would read as "this profile is inactive", a claim this service never makes.
- **loading** — two different waits, which must not be conflated:
  1. _The profile data has not arrived._ The component is not rendered at all; the caller draws
     `Skeleton/block` at the avatar's exact footprint — same square, same size token, same
     `radius-md` — so nothing reflows when the identity bar resolves (`profile-summary.md` §12.6).
  2. _The data arrived and the image is decoding._ **The frame with its `surface-sunken` fill is what
     shows, because it is already there** — the image paints over it when it decodes. No spinner, no
     second skeleton, no fade. The footprint is identical before and after, so the only thing that
     happens on decode is that a picture appears in a box that was already drawn.
- **error** — the URL was built but the image fails to load or decode: a hash the CDN no longer
  serves, an offline browser, or a request a content blocker refused — all of which are ordinary and
  none of which the reader can act on. `onError` removes the `<img>`, leaving the frame and its fill:
  **byte-identical to the no-hash render below.** No broken-image glyph, no callout, no retry, no
  tone change. FR-008a's "never a broken image" reduces to exactly this identity, and T436's story
  set exists to prove it.
- **empty** — `avatarHash` is absent, `null`, or blank after trimming: the same frame and fill, and
  nothing else. **This is a legitimate resting state, not a degraded one** — a profile never seen in
  a companion response has no hash and never will (data-model.md §2: "Nullable is the normal case,
  not the error case"), so it carries no dimming, no tooltip, no visible "no avatar" text and no
  apology.

### 4a. What the placeholder is, and what it must never contain

A `surface-sunken` fill inside the same `border-strong` frame and `radius-md` the loaded avatar uses,
at the same size. Nothing else. Specifically **no monogram or initial, no silhouette, no camera or
person glyph, no "?" and no generated pattern**:

- **An initial asserts an identity the service was not given**, and it is absent exactly for the
  profile that most needs an anchor — the alias-less one, whose heading is already a number
  (`profile-summary.md` §12.3, rule 1). "1" is not a monogram.
- **A silhouette is a picture of a person who is not this person.**
- **A "?" reads as an error**, which is the one thing FR-008a's neutral placeholder must not do.
- **A generated pattern** (identicon, colour from a hash) invents a visual identity that would then
  differ between the missing-hash case and the failed-hash case, breaking §4's identity outright.

### 4b. Why this placeholder is not the placeholder FR-010 forbids

[`match-history.md`](./match-history.md) §12.1's third rule — the absent-asset state is the prop being
`undefined`, rendering the label alone, never a placeholder — governs the **pack-keyed image props**
(`iconUrl`, `thumbnailUrl`, `flagUrl`). It does not govern this one, and the difference is not a
loophole:

- **FR-008a requires this placeholder in so many words**: "when the hash is unavailable it MUST show
  a neutral placeholder, never a broken image". FR-010 forbids one for identifiers a pack does not
  cover. Two requirements, two objects, no conflict.
- **Nothing is fetched for it.** The placeholder is two tokens and a border. It cannot 404, and the
  check FR-010 is actually testable by — zero requests under `/game-assets/` returning 404 — has no
  surface here at all, because the avatar is not a pack asset.
- **It is the identity bar's left anchor.** Collapsing it would move the profile's `<h2>`
  horizontally between a profile with an avatar and one without — the most prominent element on the
  page shifting for a fact that carries no meaning. A civilisation mark sits inline in a row where
  the name simply closes the gap; the avatar does not.
- **It stands where decoration was, not where a fact was.** Every fact the avatar could convey — who
  this is — is in the heading beside it (§2a). An uncovered civilisation's placeholder would stand
  where a fact belongs; this one stands where a picture belongs.

## 5. Tokens used

Colour: `surface-sunken` (the fill, in every state — it is simply what is behind the image),
`border-strong` (the 1px frame, both themes). **No `text-*` token: the component renders no text.**
The image is never tinted, filtered, theme-adjusted or given a drop shadow, in either theme.

**Why `border-strong` and not `border`.** `MapThumbnail`'s frame is decorative and takes `border`;
this one is not. It is drawn in every state, and in the empty and error states it is the **only**
thing that makes the avatar's position perceivable — `surface-sunken` against the light theme's
`background` is a near-invisible step. A boundary that has to be seen for a state to be seen owes
WCAG 1.4.11's 3:1, and `border-strong` is the token that carries it. The pair that matters is
`border-strong` on **`background`** — `ProfileSummary`'s root is `bg-background`, and README's
pairing convention (T034c) is that a spec names the background the component actually paints behind
the token, not the one that is conventionally "the" surface. That pair is in README's measured table
for both themes and is already asserted by `tokens/build-tokens.test.mjs`; this component adds no new
pair.

Size: `icon-lg` / `icon-2xl` (§3). Radius: `md`.

Elevation: none — no shadow behind a portrait that sits above a rating board (README rule 1).
Motion: **none at all.** No fade-in on decode, no cross-fade from placeholder to image, no skeleton
pulse of its own. Under `prefers-reduced-motion` nothing changes, because there was nothing to
reduce.

Gaps in play: none.

## 6. Spacing

The component adds **no outer margin**, so it can be dropped into a flex row without shifting
anything beside it. The gap between the avatar and the identity column (`space-4`) is the caller's
and is tabled in [`profile-summary.md`](./profile-summary.md) §12.5. There is no internal spacing:
the image fills the frame edge to edge.

## 7. Responsive

- **375 / 768 / 1280** — the size is set by the caller's variant (`md` in the board identity bar,
  `sm` in `compact`), never by the viewport. At 375 the avatar stays **beside** the heading rather
  than stacking above it: a 64px block on its own line pushes the ratings — the thing the user came
  for — further below the fold, and README rule 1 settles that trade.
- It never shrinks below `sm` (32px). Below that a face is unreadable and the download is paid for
  nothing.
- At 200% zoom the box scales with the token (rem-based), so it grows with the heading beside it
  rather than staying a fixed pixel square beside doubled type.
- The frame's aspect is square at every viewport; it is never made to fill a row's height.

## 8. Accessibility

- The image is `<img alt="">` — **decorative**, because the accessible name is the heading
  immediately beside it. Never `alt="Hera's avatar"` (a screen reader would announce the person
  twice) and never `alt="avatar"`, which names the widget rather than a fact.
- The placeholder is `aria-hidden`. It announces nothing, and that is correct: its absence has no
  meaning a screen-reader user could act on, so a "no avatar" announcement would be noise on every
  profile the companion has never seen — which is most of them.
- `width`/`height` from the size token so space is reserved before decode: no layout shift, which is
  the same no-reflow rule §4's loading state states from the other side. `loading="lazy"`,
  `decoding="async"`.
- **`referrerpolicy="no-referrer"` is required on the `<img>`.** The CDN necessarily learns the
  viewer's IP address — that is what T427 recorded in the processing register, and it is the cost of
  FR-008a — but it must not additionally learn which profile page the viewer was reading. This is a
  one-attribute privacy floor, and it is part of the component, not of a call site.
- Not focusable, no `title`, no tooltip. Non-interactive in 004, so WCAG 2.5.8's 44px target does not
  apply. If a later feature links an avatar (a favourites list, a search result), the **link's** hit
  area is at least `icon-xl` (44px) — the reason that token is fixed at 44 rather than sitting on the
  space scale (`game-asset-tokens.md`, Decision 2).
- Contrast: the frame's `border-strong` on `background` pair is in README's measured table for both
  themes, and clears the 3:1 non-text floor. The image itself carries **no** contrast obligation,
  because it carries no information the heading does not.
- The avatar hash is an **unverified third-party claim** (constitution IX). It is shown as the source
  reports it and is never used to infer, suggest or act on a relationship between profiles: no
  "same avatar, same person", no visual pairing, and **no avatar anywhere in `ProfileSummary` but the
  identity bar** — including the profile switcher's menu items, which 001 FR-045 keeps free of
  anything that visually pairs two accounts (`profile-summary.md` §4, §12.2).

## 9. Visual acceptance criteria

**The identity FR-008a actually reduces to**

- [ ] The absent-hash story and the failed-hash story are **pixel-identical** — the two screenshots
      overlay with no difference, in both themes. This is the single criterion T436 exists to satisfy.
- [ ] Neither of those two stories contains a letter, a monogram, a silhouette, a camera glyph, a "?"
      or any generated pattern: each is an empty framed fill (§4a).
- [ ] No broken-image glyph appears in any story, in either theme.
- [ ] Neither story uses `danger`, `warning` or any error affordance, and neither collapses: the
      frame is present at full size in all three of loaded, absent and failed.

**Footprint and craft**

- [ ] Overlaying the loaded story and the absent-hash story shows the heading beside the avatar at the
      **identical x-position** — the avatar never changes width between states.
- [ ] The loading story's `Skeleton/block` overlays the loaded story's avatar exactly: same size, same
      corner radius, no reflow of anything to its right.
- [ ] The frame is visible in every story in **both** themes — no avatar dissolves into the light
      theme's parchment.
- [ ] The `sm` and `md` stories in one frame are visibly different sizes; both are square, both
      undistorted, and the loaded image is crisp at 1× and 2× device pixel ratio.
- [ ] No story animates: the first and second frames of the loading → loaded transition differ only
      by the picture appearing, with no fade, no scale and no cross-fade.
- [ ] At 375 the avatar sits beside the heading, not above it, in the `ProfileSummary` story.

**Verified in the DOM or the source, not the screenshot** (stated here so the reviewer knows they are
not expected to see them)

- [ ] `https://avatars.steamstatic.com` appears exactly once in `packages/design-system/src` and
      `apps/web/src` combined — in this component — and no other host is constructed anywhere
      (greppable; T436's own check).
- [ ] The rendered `<img>` carries `alt=""`, `referrerpolicy="no-referrer"`, `loading="lazy"` and
      explicit `width`/`height`.
- [ ] The component exposes no `src`, `baseUrl` or `href` prop (§2b).

**The visual baseline must not depend on Steam**

- [ ] The loaded-avatar story renders from a **local fixture**: `tests/visual/stories.spec.ts`
      fulfils `https://avatars.steamstatic.com/**` from a file in the repository, so the baseline
      does not change when a stranger changes their avatar, does not fail in an offline CI, and does
      not send a request from the test runner. The stub lives in the visual runner, never in a prop
      and never in the component. A run that captured this story against the live CDN has proved
      nothing repeatable — the same trap T433 recorded for `/game-assets/`.
