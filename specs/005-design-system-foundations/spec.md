# Feature Specification: Design System Foundations

**Feature Branch**: `005-design-system-foundations`

**Created**: 2026-09-05

**Status**: Draft

**Input**: User description: "Create the specification for the application's foundational Design System. Establish a genuinely high-quality visual and interaction system that can support the application as it grows, not merely a collection of reusable React components."

## Context

A design system already exists and much of it is good. Thirty-two components, twenty-four component
specs each carrying the nine mandated sections, seven token families, a measured contrast table
asserted by a test rather than by re-reading, and a diff-scoped visual regression suite. The
application consumes it cleanly: a grep of `apps/web/src` for hard-coded colour, arbitrary bracket
values or default-palette class names returns nothing.

What does not yet exist is a **system**. Three gaps separate the two.

**The foundations are incomplete, and components are paying for it.** The token gap register in
`packages/design-system/specs/README.md` carries six open gaps (DS-3 through DS-6, DS-8, DS-9).
Each one is a design decision the system has declined to make, and each has produced an arbitrary
value inside the design system itself: `h-[1em]` in the spinner, `h-[1.2em]` in a stat skeleton,
`animate-[pulse_var(--ds-motion-duration-slow)...]` in the skeleton, `h-[var(--ds-icon-2xl)]` in the
profile summary because the icon family has no utility namespace. Constitution VI forbids exactly
this, and the components are not at fault: they had no token to reach for. Breakpoints are worse
than missing — they are duplicated, named in CSS by one mechanism and hard-coded as `768`, `1024`
and `1280` in a hook that decides which of two layouts enters the DOM. Two sources of truth for the
same number, in a repository whose stated law is that a number written twice goes stale in one copy.

**There is no structural layer.** Every primitive in the system is a leaf: a button, a badge, a
stat. Nothing assembles a screen. So every route assembles its own, and they have drifted. Nine
containers repeat the same page wrapper, and because the root layout already renders a `main`
landmark, each of them nests a second `main` inside it — an accessibility defect present on every
authenticated route, invisible in a screenshot, and one a page primitive would have made impossible.
Eight error presentations repeat the same wrapper and the same heading grammar, two of them
word-for-word. Section spacing is `mt-6` in three places, `mt-8` in three others and `gap-12` in one,
with no rule saying which is right. One route constrains its width; eight do not. There is no page,
section, card, table, field, text, link, empty-state or error-state primitive, so each of those
decisions is remade per route by whoever is there.

**Half the system is unverified, and a quarter of it is unreachable.** The dark theme is fully
specified, fully tokenised, contrast-measured, and *no user can select it*: the word "theme" does
not appear anywhere in `apps/web`, and nothing sets the attribute the generated stylesheet keys on.
The visual suite holds 279 baselines and not one is dark. Thirty-two story files exist and four
carry any capture below desktop width; no baseline is taken at tablet width at all. The
`visual-reviewer` agent's own protocol instructs it to capture "every state declared in the spec, in
light and dark theme, at all three breakpoints" — the harness it drives does none of those three
things. The mechanism is not missing: a bespoke focus-ring test already drives both themes through a
single URL parameter. It was simply never made an axis of the suite.

This feature closes those three gaps. It does not redesign the product, change any behaviour, or add
a domain component.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Every design decision has a token (Priority: P1)

A developer or agent building a component needs a value — an icon size, a ring width, a container
width, a looping animation duration, a link colour, a numeric type treatment. Today the honest ones
stop and ask, and the rest write an arbitrary value with an apologetic comment. After this story,
every decision the existing thirty-two components have already had to make has a named token, and
the register of open gaps is empty or each remaining entry carries an explicit, dated refusal.

**Why this priority**: it is the precondition for everything else. Constitution VI is violated
inside the design system today, and no amount of review discipline fixes a component that has
nothing to reach for. It also unblocks Stories 2 and 4, which both need tokens that do not exist.

**Independent Test**: search the design system source for arbitrary values and CSS-variable escape
hatches; the result is empty. Every gap-register entry is either closed or carries a recorded
decision not to close it. No component comment says a token is missing.

**Acceptance Scenarios**:

1. **Given** a component needs to size an icon, **When** it is written, **Then** it uses a named
   icon token through the same utility vocabulary as every other token family, with no
   variable reference written by hand.
2. **Given** a component needs a looping animation, **When** it is written, **Then** it names a
   motion token for the loop, and that animation stops on its resting frame under a reduced-motion
   preference.
3. **Given** a layout decides which of two shapes enters the page, **When** the breakpoint changes,
   **Then** the styling and the shape decision change together, because both read the same named
   breakpoint.
4. **Given** a reviewer inspects a component, **When** they search it for a raw value, **Then** they
   find none, and no comment explains why one was unavoidable.

---

### User Story 2 - A screen is assembled, not re-invented (Priority: P1)

A developer building a new route composes it from the system: a page, a section, a panel, a table, a
field, a heading, a link, an empty state, an error state. The page owns exactly one main landmark,
one content width, one horizontal padding rule and one vertical rhythm, so a new route is
indistinguishable in structure from an existing one without anyone comparing them.

**Why this priority**: this is where the drift is visible today and where every future route will
add more of it. It is also the only story that removes an existing accessibility defect from the
live product.

**Independent Test**: build a new route using only system primitives, with no layout or spacing
class written in the application, and it matches the existing routes' rhythm. Every existing route,
retrofitted, renders exactly one main landmark.

**Acceptance Scenarios**:

1. **Given** any route in the application, **When** its accessibility tree is inspected, **Then**
   exactly one main landmark is present.
2. **Given** two different routes, **When** their content width, horizontal padding and spacing
   between sections are compared, **Then** they are identical unless a spec states a difference.
3. **Given** a route whose request failed, **When** it renders, **Then** it uses the system's error
   presentation, with the same anatomy and the same recovery affordance as every other failed route.
4. **Given** a route with nothing to show, **When** it renders, **Then** it uses the system's empty
   presentation and explains why in words, never a blank region.
5. **Given** a developer building a route, **When** they need a layout or spacing decision, **Then**
   they express it through a system primitive and write no spacing class in the application.

---

### User Story 3 - The reader can use the theme they need (Priority: P1)

A reader opens the product and it appears in the theme their operating system asks for. They can
override that choice and it is remembered. Every surface, every state and every component is correct
in both themes, because both are verified rather than assumed.

**Why this priority**: an entire theme, its palette, its elevation values and its measured contrast
work are currently inert. This is the largest amount of finished work in the repository that reaches
no user. It is also an accessibility requirement for readers who need a dark or a light surface.

**Independent Test**: with the operating system set to dark, the product opens dark. The override
survives a reload. Every published story has a verified appearance in both themes.

**Acceptance Scenarios**:

1. **Given** a reader whose system prefers dark, **When** they open the product for the first time,
   **Then** it renders in the dark theme with no flash of the light one.
2. **Given** a reader who overrides the theme, **When** they return later in the same browser,
   **Then** their choice is still in effect.
3. **Given** any component in the system, **When** it is rendered in both themes, **Then** every
   text, boundary and control pair it draws meets its contrast floor in both.
4. **Given** a reader who has expressed no preference and whose system expresses none, **When** they
   open the product, **Then** it renders in a defined default rather than an undefined one.

---

### User Story 4 - Numbers are legible and comparable (Priority: P2)

A reader scanning a column of ratings, ranks, durations and deltas can compare them by eye. Digits
align vertically. A number never sits behind a texture, never animates in, and never appears as a
placeholder that could be read as real. The typographic treatment that makes this true is a named
role, so it survives a change of font.

**Why this priority**: this is the product's stated functional priority and the thing it is judged
on. It is P2 only because the current behaviour is accidentally correct — alignment rides on a font
family happening to be monospaced — rather than broken.

**Independent Test**: a column of numbers of differing widths aligns digit-for-digit. Changing the
monospace family does not change alignment. No numeric placeholder can be mistaken for a value.

**Acceptance Scenarios**:

1. **Given** a column of numeric values of differing digit counts, **When** it is rendered, **Then**
   the digits align vertically regardless of which font family is configured.
2. **Given** a value that has not loaded, **When** it renders, **Then** no digit and no zero appears
   in its place.
3. **Given** a value that has never been observed, **When** it renders, **Then** it is visibly
   distinct from a measured value and states why in words.
4. **Given** a raw identifier, a machine string and a measured number in the same view, **When** they
   are rendered, **Then** each is recognisable as what it is rather than all three sharing one
   treatment.

---

### User Story 5 - The system is verified across the axes it claims (Priority: P2)

A reviewer trusts the suite. When a component claims a state, a theme and a width, all three are
captured and compared. When a colour moves, the pairs that colour actually draws fail a test. When
markup loses a label or a role, an automated check fails before a human looks.

**Why this priority**: the conformance gate currently claims coverage it does not have. A gate that
is believed and does not hold is worse than an absent one, because it displaces the manual check
that would otherwise happen.

**Independent Test**: remove a required accessible name from a component and an automated check
fails. Break a dark-theme-only colour and a baseline fails. Introduce an overflow at tablet width
and a baseline fails.

**Acceptance Scenarios**:

1. **Given** a change to a component, **When** the suite runs, **Then** the affected stories are
   compared in both themes and at every review width the specification declares.
2. **Given** a component that loses its accessible name, its role or its label association, **When**
   the suite runs, **Then** an automated check fails and names the component.
3. **Given** a colour token change, **When** the suite runs, **Then** every pair that a component
   actually paints with that token is asserted, not only the pair conventionally associated with it.
4. **Given** a component with a focus-visible obligation, **When** the suite runs, **Then** the ring
   is verified as present and contrasted in both themes.

---

### User Story 6 - Storybook explains the system without the source (Priority: P2)

Someone who has never read the application opens Storybook and understands the system: what the
colours mean and where each may be used, what the type scale is, what the spacing rhythm is, which
primitives exist, what each one's states look like, and how they compose into a realistic screen.
They leave able to build a page correctly.

**Why this priority**: the system is maintained largely by agents working from a cold context. A
surface that explains itself is what makes the reuse test in the design-system skill answerable
before a component is written rather than after.

**Independent Test**: hand someone Storybook and no repository access, and ask them which component
to use for a given need, which token carries a given meaning, and what a given state looks like.
They answer all three.

**Acceptance Scenarios**:

1. **Given** Storybook, **When** a person looks for the colour system, **Then** they find a page
   naming every semantic role, its meaning, the surfaces it may be used on, and its verified pairs.
2. **Given** a component in Storybook, **When** a person opens it, **Then** every variant and every
   applicable state is a separate, named story, and each inapplicable state is documented as such.
3. **Given** a component in Storybook, **When** a person looks for how it is really used, **Then**
   they find at least one realistic composition rather than only isolated specimens.
4. **Given** any story, **When** it is rendered twice, **Then** it is pixel-identical, with no
   dependence on the clock, on randomness or on the network.
5. **Given** a person deciding whether a component already exists, **When** they browse the
   navigation, **Then** the grouping tells them where a primitive ends and a domain composite
   begins.

---

### User Story 7 - The system evolves deliberately (Priority: P3)

A developer or agent notices the same composition for the third time in the application. There is a
written trigger telling them it is now a system pattern, a written procedure for promoting it, and a
written procedure for retiring what it replaces. Nobody has to open a governance discussion, and
nobody has to guess.

**Why this priority**: the rules that prevent drift matter most once the foundations exist. Adding
governance before there is anything to govern is how bureaucracy starts.

**Independent Test**: a repeated application composition is promoted, and a deprecated component is
retired, each by following the written rule with no judgement call left unrecorded.

**Acceptance Scenarios**:

1. **Given** a composition repeated in the application beyond the stated threshold, **When** it is
   next touched, **Then** the rule requires it to be promoted or requires the reason it is not to be
   recorded.
2. **Given** a component being retired, **When** it is deprecated, **Then** its replacement is named,
   its consumers are enumerated, and its removal happens in a change that also updates them.
3. **Given** a proposed new token, **When** it is assessed, **Then** the written admission test
   decides it, and a rejected proposal records what existing token serves instead.

---

### Edge Cases

- A reader's system expresses no colour-scheme preference, and they have never chosen one.
- A reader has both a stored theme override and a system preference, and the two disagree.
- A reader's browser blocks storage, so no override can be remembered.
- A component is rendered at a width between two declared review widths.
- A component's only distinguishing signal in a state is colour, and the reader cannot perceive it.
- A hover-revealed fact is needed by a reader on a touch device, who has no hover.
- A looping animation runs for a reader who has asked for reduced motion.
- A number arrives as a value that formats to zero, in a view where zero is also the loading
  placeholder's shape.
- A container is narrower than the minimum touch target the control inside it owes.
- A token is proposed that is a synonym of an existing token under a different name.
- A component is used in an application composition that repeats, but each occurrence differs in a
  detail, so no single promotion is obviously correct.
- A colour token is changed and a pair it draws is not in the measured table, so no test fails.

## Requirements *(mandatory)*

The constitution (VI, VII) and the `design-system` skill already require tokens-first components,
Storybook coverage, visual review and visual regression. Those are constraints here, not
requirements restated. The `packages/design-system/specs/README.md` gap register, contrast table and
six standing rules are likewise existing constraints. Requirements below add what is missing.

### Foundations — completeness

- **FR-001**: The token system MUST cover every design decision the existing components make. Every
  arbitrary value and every hand-written variable reference currently present in the design system
  source MUST be replaceable by a named token, and the source MUST end with none of either.
- **FR-002**: Every open entry in the token gap register MUST be resolved, either by admitting the
  token family or by recording a dated decision not to, naming what components use instead. An entry
  may not remain open with only an interim workaround.
- **FR-003**: Breakpoints MUST have exactly one definition. Styling and any layout decision that
  selects between structures MUST derive from the same named source, so the two cannot disagree.
- **FR-004**: Every token MUST express a reusable design decision. A token whose only justification
  is one call site MUST be rejected, and the rejection MUST name the existing token that serves.
- **FR-005**: Semantic colour roles MUST be defined by meaning, not by appearance, and each role MUST
  declare the surfaces it may be painted on. A role used on a surface it does not declare is a
  defect, whether or not the resulting pair happens to pass contrast.
- **FR-006**: The system MUST define a link role, or record that inline links use an existing role
  under a stated restriction. A link MUST never be distinguished by colour alone.
- **FR-007**: Typography MUST define named roles by function — at minimum display, body, supporting,
  numeric, and machine text — rather than by size alone. A role MUST NOT be inferred from a font
  family being coincidentally suitable.
- **FR-008**: The spacing scale MUST be the single source of vertical and horizontal rhythm, and the
  system MUST state which steps are used for which relationship (within a component, between
  components, between sections) so that rhythm is a rule rather than a habit.
- **FR-009**: Elevation MUST define, for each level, what it means and what may sit at it. Where the
  system relies on document order rather than an explicit stacking value, that MUST be recorded as a
  decision with the constraints it imposes on call sites.
- **FR-010**: Motion MUST cover transitions and looping animations, and every duration a component
  uses MUST come from the motion family. Motion MUST NOT be the only signal that a state changed.
- **FR-011**: Iconography MUST have a defined contract: the size scale, how an icon aligns with
  adjacent text, how it is given or denied an accessible name, and the minimum interactive footprint.
  An icon MUST NEVER be the only carrier of a meaning.
- **FR-012**: Density MUST be a stated property of a surface class rather than a per-component
  choice: the system MUST define the row height, padding and line rhythm that a data-dense surface
  uses and that a prose surface uses, and every component MUST declare which class it belongs to.
- **FR-013**: Radii MUST be assigned by role — control, panel, overlay, pill — so that two components
  of the same role cannot differ.

### Foundations — themes and responsiveness

- **FR-014**: Both themes MUST be reachable by a reader. The product MUST honour the reader's system
  colour-scheme preference on first visit, MUST allow an explicit override, and MUST remember that
  override for the same reader and browser.
- **FR-015**: The product MUST NOT render one theme before switching to the other on load.
- **FR-016**: Where no preference can be determined and none is stored, the product MUST render a
  defined default theme.
- **FR-017**: A component MUST NOT branch on the active theme. Both themes MUST be served by the same
  token names.
- **FR-018**: The system MUST declare its review widths and MUST behave correctly at each: no
  horizontal overflow of the page, no unintended truncation, no control below its minimum touch
  footprint, and no content that is reachable at one width and unreachable at another.
- **FR-019**: Where a component changes structure rather than styling across a width, exactly one
  structure MUST be present at a time.

### Structure — the assembly layer

- **FR-020**: The system MUST provide the primitives required to assemble a screen without the
  application writing layout or spacing: a page, a section, a panel, a heading and text treatment, a
  link, a table, a form field, an empty presentation and an error presentation.
- **FR-021**: The page primitive MUST own the single main landmark, the content width and the page
  padding. An application route MUST NOT declare any of the three.
- **FR-022**: Every route MUST render exactly one main landmark.
- **FR-023**: The empty presentation MUST state why a region is empty and, where an action would fill
  it, offer that action. A blank region is a defect.
- **FR-024**: The error presentation MUST state what failed in the reader's terms and MUST offer a
  path forward. A failure MUST NOT leave the control that caused it permanently unusable.
- **FR-025**: The form field primitive MUST associate its label, its hint and its error with its
  control, and MUST convey an error in text as well as in colour.
- **FR-026**: The table primitive MUST carry column semantics, MUST align numeric columns on their
  digits, and MUST define what it does when it is wider than its container.
- **FR-027**: Everything the design system exposes for use MUST be reachable from its public surface.
  A component that other components use but consumers cannot import is either published or
  documented as internal.

### Components — what belongs where

- **FR-028**: The system MUST define tiers with a written boundary between them: primitives that
  carry no domain knowledge, domain composites that do, and screens. Every component MUST declare its
  tier, and a component's tier MUST determine where it lives and what it may depend on.
- **FR-029**: A primitive MUST NOT depend on a domain composite, and no component MUST depend on the
  application.
- **FR-030**: A new component MUST be admitted only when reuse, consistency or interaction complexity
  requires it, and the admission MUST record which of the three. Composition of existing primitives
  MUST be preferred where it suffices.
- **FR-031**: A new variant MUST be admitted only when it expresses a distinct meaning. A variant
  that exists to accommodate one call site MUST be rejected.
- **FR-032**: Components MUST share one prop vocabulary for the same concept across the system. Where
  two components today name the same concept differently, or use different value sets for the same
  scale, the system MUST reconcile them or record why the difference is real.
- **FR-033**: An application composition that repeats beyond a stated threshold MUST be promoted to
  the system or MUST carry a recorded reason it is not.

### States

- **FR-034**: The state vocabulary MUST be closed and MUST cover every state the existing components
  actually implement, including selection and expansion, which the current eight do not name.
- **FR-035**: Every component spec MUST answer every state in the vocabulary, either by specifying
  its appearance and behaviour or by recording why it does not apply and what happens instead. An
  unanswered state MUST fail a mechanical check.
- **FR-036**: A state MUST NOT be implemented because the vocabulary lists it. A state that has no
  meaning for a component is documented as inapplicable, not built.
- **FR-037**: Two states of the same component MUST be distinguishable from one another by more than
  colour, and MUST be distinguishable in a still image.
- **FR-038**: Interactive feedback MUST be consistent across the system: the same category of control
  MUST respond to hover, focus and activation in the same way unless a spec states a difference.
- **FR-039**: A fact revealed only on hover MUST also be reachable by keyboard and by touch, and MUST
  be present in the accessibility tree whether or not the reveal has fired.

### Storybook

- **FR-040**: Storybook MUST be sufficient to understand the system without reading the application
  source.
- **FR-041**: Storybook MUST document the foundations interactively: every semantic colour role with
  its meaning and permitted surfaces, the type scale and its roles, the spacing rhythm, radii,
  elevation, motion and iconography.
- **FR-042**: Every variant and every applicable state MUST have its own named story. Every state
  documented as inapplicable MUST be visible as such rather than silently absent.
- **FR-043**: Every component MUST carry at least one realistic composition showing it as it is
  actually used, with plausible content lengths rather than specimen text.
- **FR-044**: Components with responsive behaviour MUST have stories that demonstrate it at the
  declared review widths.
- **FR-045**: Storybook MUST carry accessibility-oriented examples: keyboard interaction, focus
  order, an error being announced, and a reduced-motion rendering.
- **FR-046**: Navigation MUST make the tier of a component evident and MUST let someone find a
  component by the need it serves, so the reuse test can be answered from Storybook alone.
- **FR-047**: Every story MUST be deterministic: identical output on repeated renders, with no
  dependence on the clock, on randomness, on the network or on an unsettled animation.

### Accessibility

- **FR-048**: Semantics MUST come from HTML before ARIA. An interactive element MUST be a real
  interactive element.
- **FR-049**: Every interactive element MUST be reachable and operable by keyboard, in an order that
  matches its visual order, with no trap outside a modal surface that defines its own.
- **FR-050**: Every focusable element MUST show a visible focus indicator that meets the non-text
  contrast floor against the surface it appears on, in both themes, and MUST NOT lose it on pointer
  interaction.
- **FR-051**: Every control, region and image MUST have an accessible name that says what it is or
  does. A name MUST NOT be the raw identifier when a human-readable one exists.
- **FR-052**: Text MUST meet its contrast floor in both themes, and every pair a component actually
  paints MUST be measured and asserted, not inferred from the pair conventionally associated with
  the token.
- **FR-053**: Form errors MUST be associated with their control, MUST be conveyed in text, and MUST
  be announced to assistive technology when they appear after the initial render.
- **FR-054**: Loading MUST be announced once for a region rather than per element, and MUST NOT
  present a placeholder that reads as data.
- **FR-055**: Under a reduced-motion preference, every transition MUST be reduced to no perceptible
  duration and every looping animation MUST stop on its resting frame.
- **FR-056**: Every interactive target MUST meet the minimum touch footprint at widths where touch is
  expected, and a target MUST NOT be enlarged by an overlay that intercepts unrelated interaction.
- **FR-057**: ARIA MUST be used only where HTML cannot express the semantics, and an ARIA attribute
  that contradicts the element it sits on MUST fail a check.
- **FR-058**: An automated accessibility check MUST run over the system's stories as part of the
  suite, and MUST fail the change rather than only reporting.

### Verification and the visual-reviewer's surface

The `visual-reviewer` is the conformance gate and its role is not restated here. These requirements
define what the specification and the tooling MUST make objectively decidable for it.

- **FR-059**: Every component spec's visual acceptance criteria MUST be decidable from a still image
  plus the spec, without reading the source and without judging taste. A criterion that requires
  either MUST be rewritten or moved to the general reviewer's scope.
- **FR-060**: The suite MUST capture the axes the review protocol claims: every affected story, in
  both themes, at every declared review width, for every state the spec declares.
- **FR-061**: Where the full matrix is not captured on every change, the specification MUST state
  which subset runs when, so that "verified" has one meaning and the gate never claims coverage it
  does not have.
- **FR-062**: A spacing, colour, radius or motion value that is not on the scale MUST fail a
  mechanical check rather than depend on being noticed in review.
- **FR-063**: Conformance to tokens MUST NOT be treated as sufficient for visual quality. The spec
  MUST carry, per component, at least one criterion about hierarchy, rhythm or legibility that a
  token-correct but visually poor implementation would fail.

### Evolution

- **FR-064**: Admitting a token, a component or a variant MUST follow one written test whose steps
  an agent can apply mechanically, and the outcome MUST be recorded where the next reader will find
  it.
- **FR-065**: Deprecating anything MUST name its replacement and enumerate its consumers.
- **FR-066**: A breaking change MUST land together with the updates to every consumer it breaks, in
  one change.
- **FR-067**: Governance MUST add no step that requires a synchronous human decision for an ordinary
  addition. A rule that cannot be applied by an agent working alone is not a rule this system keeps.

### Key Entities

- **Token family**: a named group of design decisions of one kind, serving both themes under one set
  of names, with a stated admission test and a recorded rationale per token.
- **Component tier**: primitive, domain composite or screen. Determines dependencies, location and
  the kind of specification owed.
- **Component specification**: the nine-section contract, one per component, answering every state in
  the closed vocabulary and carrying acceptance criteria decidable from an image.
- **Surface class**: data-dense or prose. Determines density, rhythm and which typography roles apply.
- **Review matrix**: the set of story, theme, width and state combinations the suite captures, and
  when each subset runs.
- **Gap register**: the list of design decisions the system has not yet made, each with what
  components do meanwhile and who must act.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A search of the design system and the application for values outside the token scales
  returns nothing, and no source comment reports a missing token.
- **SC-002**: The gap register has no entry that is open with only an interim workaround.
- **SC-003**: Every route renders exactly one main landmark, and no route declares its own content
  width or page padding.
- **SC-004**: A new route can be built with no layout or spacing decision written in the application,
  and its rhythm matches existing routes without adjustment.
- **SC-005**: A reader whose system prefers dark opens the product in dark, with no flash of the
  other theme, and an override they set is still in effect after a reload.
- **SC-006**: Every published story has a verified appearance in both themes and at every declared
  review width.
- **SC-007**: Removing an accessible name, a label association or a role from any component causes an
  automated check to fail and to name the component.
- **SC-008**: Changing any colour token causes every pair that a component actually paints with it to
  be re-asserted.
- **SC-009**: Digits align vertically in every numeric column, and alignment survives a change of the
  monospace family.
- **SC-010**: No loading or unobserved value renders as a digit, and an unobserved value is visibly
  distinct from a measured one.
- **SC-011**: A person with Storybook and no repository access can name the component to use for a
  stated need, the token that carries a stated meaning, and the appearance of a stated state.
- **SC-012**: Every component's states, variants, a realistic composition, and its responsive and
  accessibility examples are present as named stories, and repeated renders are identical.
- **SC-013**: Every component spec answers every state in the closed vocabulary, verified
  mechanically rather than by reading.
- **SC-014**: A composition repeated in the application beyond the promotion threshold either exists
  in the system or carries a recorded reason it does not.
- **SC-015**: A reader using only a keyboard can reach and operate every interactive element on every
  route, with the focus indicator visible at every step in both themes.
- **SC-016**: With a reduced-motion preference set, no looping animation runs and no transition has a
  perceptible duration.

## Assumptions

- The existing token values, palette and typographic families are the starting point and are not
  redesigned by this feature. The art direction — warm parchment, stone, muted gold, restrained
  rather than ornamental — is already established in the tokens and is preserved. This assumption is
  the subject of the first unresolved decision below.
- The nine-section component specification structure, the closed state vocabulary and the six
  standing rules in the design system's own specs directory are kept and extended, not replaced.
- Theme selection follows the reader's system preference by default, with an explicit override
  stored per browser, and light is the defined default when neither is available.
- The declared review widths remain the three the specs already name, so existing baselines stay
  meaningful.
- Density is a property of a surface class in this feature, not a reader-facing setting. A
  reader-controlled density toggle is out of scope.
- No new domain component, no product behaviour change, no data model change and no API change is in
  scope. Every existing component keeps its current behaviour and its current public props unless a
  requirement here explicitly reconciles them.
- Retiring an existing component or renaming a prop is permitted where FR-032 requires it, and lands
  with its consumers under FR-066.
- Storybook remains the authoritative interactive surface, as the constitution already requires. The
  visual regression suite remains diff-scoped for pull requests with full coverage nightly, as
  constitution VII requires; how the theme and width axes fit that budget is the third unresolved
  decision below.

## Out of Scope

- Redesigning the palette, the typefaces or the art direction.
- Any new domain composite, screen or product capability.
- A reader-facing density control.
- Internationalisation and localisation of formatting, which is presently fixed to one locale.
- Server-side rendering, which the theme requirements are written to accommodate but do not assume.
- Publishing the design system outside this repository.

## Existing strengths to preserve

1. **Specifications that carry judgement, not just parameters.** The component specs state why a
   decision was made and what failure it prevents — why a destructive control does not fill with the
   danger colour, why a loading number must never render a zero, why a dialog's escape key reaches
   the secondary action. This is the most valuable artifact in the repository and must not be
   flattened into a table of properties.
2. **Contrast as an asserted fact rather than a document.** Pairs are measured, tabled, and asserted
   by a test, so a colour edit fails a build rather than depending on a table being re-read.
3. **The pairing convention.** A token is asserted against the background the component actually
   paints behind it, found by reading the component, rather than against the background
   conventionally associated with the token. This was learned three times and is written down.
4. **Application-level token discipline.** The application writes no colour, no arbitrary value and
   no default-palette class. That is rare and was clearly maintained deliberately.
5. **The closed state vocabulary, answered rather than skipped.** "This component has no empty state"
   is treated as a design bug, and the specs answer every state even when the answer is a refusal.
6. **Colour is never the only carrier of meaning**, with one narrow, documented exception.
7. **The gap register itself.** An honest list of decisions not yet made, each naming its interim and
   its owner, is why the arbitrary values in the source are traceable rather than mysterious.
8. **Real elements over simulated ones.** Rows are real links that honour modifier clicks; controls
   are real controls.
9. **Deterministic stories that wait for the render to settle** rather than screenshotting a
   mid-transition frame.

## Missing foundations

1. Icon sizing usable through the ordinary utility vocabulary.
2. A looping-animation duration.
3. Border, ring and ring-offset widths.
4. A single breakpoint definition shared by styling and structure.
5. Container, panel and reading-measure widths.
6. A numeric typography role independent of the monospace family.
7. A link role, and the measured pairs it needs.
8. An opacity family, or a recorded decision that the colour route replaces it.
9. Separation of the three meanings currently carried by one monospace treatment: measured numbers,
   machine text, and unresolved identifiers.
10. The entire structural tier: page, section, panel, table, field, text, link, empty and error.
11. A reachable theme in the product.
12. Theme and width as axes of the verification suite.
13. Automated accessibility checking in the suite.
14. A promotion rule with a threshold, and a deprecation procedure.
15. A deliberate public surface for the package.
16. Interactive foundation documentation in Storybook.
17. Selection and expansion in the state vocabulary.
18. One prop vocabulary for size and for variant across components.

## Important design decisions

1. **Foundations before components.** No new component is admitted until the token gap that would
   force it to invent a value is closed. This ordering is why User Story 1 is a precondition rather
   than a parallel workstream.
2. **The structural tier is a system concern, not an application one.** The nested landmark defect
   exists because layout was left to each route. Layout that repeats is a design decision, and design
   decisions live in the system.
3. **Density is a property of a surface, not a knob.** Two named surface classes, assigned per
   component, rather than a density prop on every component or a reader-facing setting. This
   satisfies the information-density requirement without a runtime axis nothing yet needs.
4. **One meaning per typographic role.** The monospace family currently means three different things,
   so a change to it would move all three together. Splitting the roles is what makes number
   alignment a decision rather than a coincidence.
5. **Both themes are a correctness requirement, not a feature.** A theme that is specified,
   tokenised, contrast-measured and unreachable is unfinished work, not an optional enhancement.
6. **Verification must match its claim.** Either the suite captures the axes the review protocol
   names, or the protocol is narrowed to what is captured. A gate that overstates its coverage
   displaces the manual check that would otherwise happen.
7. **Token compliance is necessary and not sufficient.** Each component owes at least one acceptance
   criterion about hierarchy, rhythm or legibility that a token-correct but poor implementation
   fails.
8. **Governance is mechanical or it is absent.** Every rule added must be applicable by an agent
   working alone from a cold context. A rule needing a synchronous human decision is not kept.

## Important unresolved decisions

1. **Is the art direction re-opened?** This specification assumes the existing palette and
   typefaces are fixed and that the work is completing the system around them. Re-deriving the
   palette would deliver a more distinctive product but invalidates the measured contrast table and
   every visual baseline.
   [NEEDS CLARIFICATION: are the existing colour and typography tokens the fixed starting point, or
   is a palette and typography redesign in scope for this feature?]
2. **How much of the existing surface is retrofitted here?** Thirty-two components and nine
   application containers exist. Bringing all of them onto the new foundations in this feature is a
   large body of work; leaving them to migrate opportunistically leaves the system in two states
   indefinitely, which is the drift this feature exists to end.
   [NEEDS CLARIFICATION: does this feature retrofit every existing component and route onto the new
   foundations, or establish the foundations and migrate existing surfaces as they are next touched?]
3. **What is the verification matrix, given the budget?** Two themes times three widths multiplies
   the baseline count several-fold, against a constitutional rule that pull-request runs test only
   what the diff affects.
   [NEEDS CLARIFICATION: what theme and width coverage must run on a pull request versus nightly, and
   is a larger baseline count acceptable given the free-tier constraints in docs/adr/0002-hosting.md?]
4. **Where do the system's living facts belong?** The measured contrast table and the gap register
   are living, world-facing facts that must be true today, which the repository's own rule places in
   the documentation directory rather than beside the specs. They are currently in the design
   system's specs directory and are protected by a test. Moving them is a correctness-of-filing
   question, not a behaviour change, and this feature should settle it rather than inherit it.
5. **Is an opacity family wanted at all?** The register has carried this question since the
   beginning with the colour route working well. Closing it as a recorded refusal is likely correct
   and is cheaper than leaving it open, but it is a judgement the system owner should make once.

## Risks

1. **Baseline churn swamps the work.** Almost every requirement here changes rendered output.
   Recapturing 279 baselines, and more once themes and widths become axes, risks a change so large
   that a real regression hides inside it. Mitigation: sequence so that baseline-affecting changes
   land in small, separately reviewable steps.
2. **Baselines are environment-sensitive.** Full-page baselines are authoritative from the
   continuous-integration renderer, not from a developer machine. A retrofit of this size will
   produce a large number of locally captured baselines that are subtly wrong.
3. **Premature abstraction.** The instruction to add a structural tier is also an invitation to
   invent a component for every layout shape. The promotion threshold and the admission test exist
   to prevent this, and both are written in this feature rather than before it.
4. **A prop vocabulary reconciliation is a breaking change** across every consumer, and lands as one
   change under FR-066. That change is large and must not be batched with unrelated work.
5. **Governance becoming bureaucracy.** Every rule added is a cost paid on every future change.
   FR-067 is the guard, and it must be applied to this feature's own output.
6. **The theme override and system preference can disagree** in ways that are easy to get subtly
   wrong, particularly on first paint. This is user-visible and hard to catch in a still image.
7. **Automated accessibility checking produces findings on existing components** the moment it is
   switched on. The volume is unknown until it runs, and it may be large enough to need its own
   sequencing decision.
8. **Two sources of truth for breakpoints already exist.** Consolidating them changes which layout
   renders at which width, and the widths where a structure switches are exactly the widths least
   covered by baselines today.
9. **Scope creep into a redesign.** "Distinctive and premium" is an invitation to re-open settled
   visual decisions. The first unresolved decision above exists to make that an explicit choice
   rather than an accumulating one.

## Production-readiness acceptance criteria

The feature is ready to ship when all of the following hold.

1. No arbitrary value and no hand-written variable reference remains in the design system or the
   application, and no source comment reports a missing token.
2. The gap register contains no entry open with only an interim workaround.
3. Every route renders exactly one main landmark, and no route declares its own content width or
   page padding.
4. Both themes are reachable by a reader, honour the system preference, remember an override, and
   render without a flash of the other theme.
5. Every component's every drawn colour pair is measured and asserted in both themes, and a colour
   change fails a test rather than a review.
6. The verification suite captures the axes the review protocol claims, or the protocol has been
   narrowed to what it captures, and the specification states which subset runs when.
7. An automated accessibility check runs over the system's stories and fails the change on a finding.
8. Every component specification answers every state in the closed vocabulary, verified mechanically.
9. Every component has stories for its variants, its applicable states, a realistic composition, its
   responsive behaviour and its accessibility behaviour, and every story is deterministic.
10. Storybook documents every foundation interactively, and the system is comprehensible from it
    without the application source.
11. Every component declares its tier, and no primitive depends on a domain composite.
12. Everything intended for use is reachable from the package's public surface.
13. Keyboard operation, focus visibility, touch footprints and reduced motion are verified on every
    route in both themes.
14. The promotion threshold, the admission test, the deprecation procedure and the breaking-change
    rule are written, and each has been applied at least once during this feature.
15. `visual-reviewer` returns a pass for every affected component, and the general reviewer approves
    against this specification and the constitution.
