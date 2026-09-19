# The determinability register

<!-- GENERATED FILE. Do not edit. -->

This file is generated from `register.toml`, the only place a classification is written (FR-006a). Regenerate it with `uv run python -m aoe2stats_core.truth.register`; a test fails when the two diverge.

## Non-determinable (1)

These data cannot be known from the recording. Each is stated in full: why, what it costs, what stands in for it, and what would change the answer.

### `participant.units_lost`

- status: blocked
- blocked on: an outcome event in the recording format
- reason: the operation stream is player intent only: it carries no damage event, no death event and no completion event, and the post-game operation carries no statistics block, so no field of the file states that any unit died
- impact: no casualty count, no army value over time, no trade evaluation, and no military-strength dimension that needs either; the analytics that wanted them are not degraded, they are absent
- approximation: group silence, published separately under participant.group_silence_episodes as an inferred engagement signal that is explicitly not a casualty count
- approximation_acceptable: no
- would change if: a recording format that carries outcome events or a post-game statistics block
- source: no field of the recording: the recording carries no damage, death or completion event and no post-game statistics block
- method: none exists; nothing is computed and nothing is published under this id
- requires knowledge: none
- depends on: none
- validation: the absence is re-measured against every newly committed current-patch recording, as docs/data-sources.md section 2 requires
- evidence: docs/data-sources.md §2

## observed (39)

Read directly from the recording.

### `document.schema_version`

- status: published
- source: the analyzer's own document constant, not a field of the recording
- method: written verbatim by the analyzer when it serialises the document; names the document's shape
- document path: `schema_version`
- requires knowledge: none
- depends on: none
- validation: packages/replay-engine/tests/test_extract.py — golden timeline
- evidence: specs/006-replay-analysis-foundations/research.md D8

### `match.game_id`

- status: published
- source: the platform's match identifier, carried by the request that fetched the recording; not read from inside the recording
- method: copied unchanged from the match record the analysis was requested for
- document path: `game_id`
- requires knowledge: none
- depends on: none
- validation: packages/replay-engine/tests/test_extract.py — golden timeline
- evidence: docs/data-sources.md §2

### `match.point_of_view_profile_id`

- status: published
- source: the profile identifier the recording was fetched for; the recording is that profile's point of view
- method: copied unchanged from the fetch request
- document path: `point_of_view_profile_id`
- requires knowledge: none
- depends on: none
- validation: packages/replay-engine/tests/test_extract.py — golden timeline
- evidence: docs/data-sources.md §2

### `match.world_time_ms`

- status: published
- source: the recording's post-game world-time block
- method: read unchanged from the block; it is the match clock's end, not a wall-clock duration
- document path: `world_time_ms`
- requires knowledge: none
- depends on: none
- validation: packages/replay-engine/tests/test_extract.py — golden timeline
- evidence: specs/003-player-search-match-analysis/research.md R1

### `engine.name`

- status: published
- source: the parser distribution's own name
- method: read from installed distribution metadata
- document path: `engine.name`
- requires knowledge: none
- depends on: none
- validation: packages/replay-engine/tests/test_extract.py — golden timeline
- evidence: specs/006-replay-analysis-foundations/research.md D10

### `engine.version`

- status: published
- source: the parser distribution's installed version
- method: read from installed distribution metadata
- document path: `engine.version`
- requires knowledge: none
- depends on: none
- validation: packages/replay-engine/tests/test_extract.py — golden timeline
- evidence: specs/006-replay-analysis-foundations/research.md D10

### `engine.dependencies`

- status: published
- source: the installed metadata of the parser and each requirement it declares
- method: read from installed distribution metadata; empty is a construction error
- document path: `engine.deps.*`
- requires knowledge: none
- depends on: none
- validation: packages/replay-engine/tests/test_extract.py — golden timeline
- evidence: specs/006-replay-analysis-foundations/research.md D10

### `source_recording.object_key`

- status: published
- source: the object store key of the retained original archive
- method: copied unchanged from the retention record
- document path: `source_recording.object_key`
- requires knowledge: none
- depends on: none
- validation: packages/replay-engine/tests/test_extract.py — golden timeline
- evidence: specs/003-player-search-match-analysis/research.md R9

### `source_recording.sha256`

- status: published
- source: the checksum of the retained original archive, recorded at retention
- method: copied unchanged from the retention record and verified again on retrieval
- document path: `source_recording.sha256`
- requires knowledge: none
- depends on: none
- validation: packages/replay-engine/tests/test_extract.py — golden timeline
- evidence: specs/003-player-search-match-analysis/research.md R9

### `participant.profile_id`

- status: published
- source: the recording header's game-settings player slot
- method: read unchanged from the slot; it joins the parse to the match's participants without inference
- document path: `participants[].profile_id`
- requires knowledge: none
- depends on: none
- validation: packages/replay-engine/tests/test_extract.py — golden timeline
- evidence: specs/003-player-search-match-analysis/research.md R2

### `participant.player_number`

- status: published
- source: the recording header's game-settings player slot
- method: read unchanged from the slot; it joins the parse to the match's participants without inference
- document path: `participants[].player_number`
- requires knowledge: none
- depends on: none
- validation: packages/replay-engine/tests/test_extract.py — golden timeline
- evidence: specs/003-player-search-match-analysis/research.md R2

### `participant.civ_id`

- status: published
- source: the recording header's game-settings player slot
- method: read unchanged from the slot; it joins the parse to the match's participants without inference
- document path: `participants[].civ_id`
- requires knowledge: none
- depends on: none
- validation: packages/replay-engine/tests/test_extract.py — golden timeline
- evidence: specs/003-player-search-match-analysis/research.md R2

### `participant.resolved_team_id`

- status: published
- source: the recording header's game-settings player slot
- method: read unchanged from the slot; it joins the parse to the match's participants without inference
- document path: `participants[].resolved_team_id`
- requires knowledge: none
- depends on: none
- validation: packages/replay-engine/tests/test_extract.py — golden timeline
- evidence: specs/003-player-search-match-analysis/research.md R2

### `participant.builds.world_time_ms`

- status: published
- source: the time field of the build action
- method: read unchanged from the action
- document path: `participants[].builds[].world_time_ms`
- requires knowledge: none
- depends on: none
- validation: packages/replay-engine/tests/test_extract.py — golden timeline
- evidence: specs/003-player-search-match-analysis/research.md R4

### `participant.trainings.unit_id`

- status: published
- source: a named field of the wheel-decoded training-queue command
- method: read unchanged, one entry per command, never collapsed
- document path: `participants[].trainings[].unit_id`
- requires knowledge: none
- depends on: none
- validation: packages/replay-engine/tests/test_extract.py — golden timeline
- evidence: specs/003-player-search-match-analysis/research.md R1

### `participant.trainings.amount`

- status: published
- source: a named field of the wheel-decoded training-queue command
- method: read unchanged, one entry per command, never collapsed
- document path: `participants[].trainings[].amount`
- requires knowledge: none
- depends on: none
- validation: packages/replay-engine/tests/test_extract.py — golden timeline
- evidence: specs/003-player-search-match-analysis/research.md R1

### `participant.trainings.building_id`

- status: published
- source: a named field of the wheel-decoded training-queue command
- method: read unchanged, one entry per command, never collapsed
- document path: `participants[].trainings[].building_id`
- requires knowledge: none
- depends on: none
- validation: packages/replay-engine/tests/test_extract.py — golden timeline
- evidence: specs/003-player-search-match-analysis/research.md R1

### `participant.trainings.world_time_ms`

- status: published
- source: the time field of the training command
- method: read unchanged from the action
- document path: `participants[].trainings[].world_time_ms`
- requires knowledge: none
- depends on: none
- validation: packages/replay-engine/tests/test_extract.py — golden timeline
- evidence: specs/003-player-search-match-analysis/research.md R1

### `participant.researches.technology_id`

- status: published
- source: a named field of the wheel-decoded research command
- method: read unchanged; first occurrence per technology over the whole match
- document path: `participants[].researches[].technology_id`
- requires knowledge: none
- depends on: none
- validation: packages/replay-engine/tests/test_extract.py — golden timeline
- evidence: specs/003-player-search-match-analysis/research.md R5

### `participant.researches.world_time_ms`

- status: published
- source: the time field of the first research command naming the technology
- method: read unchanged from the action; later identical commands do not move it
- document path: `participants[].researches[].world_time_ms`
- requires knowledge: none
- depends on: none
- validation: packages/replay-engine/tests/test_extract.py — golden timeline
- evidence: specs/003-player-search-match-analysis/research.md R5

### `participant.age_up_commands`

- status: published
- source: research commands naming an age technology, per participant
- method: first-occurrence collapse; match-clock time of the command. It is an order, not an arrival
- document path: `participants[].age_up_commands.*`
- requires knowledge: none
- depends on: none
- validation: packages/replay-engine/tests/test_extract.py — golden timeline
- evidence: specs/003-player-search-match-analysis/research.md R5

### `participant.resigned_at_ms`

- status: published
- source: the time field of the participant's first resignation action
- method: read unchanged from the action; absent when the participant never resigned
- document path: `participants[].resigned_at_ms`
- requires knowledge: none
- depends on: none
- validation: packages/replay-engine/tests/test_extract.py — golden timeline
- evidence: specs/006-replay-analysis-foundations/research.md D11

### `event.clock_ms`

- status: planned
- source: the time of an operation on the match clock
- method: match-clock time; accumulated from sync increments and asserted to agree with each action's own time field
- requires knowledge: none
- depends on: none
- validation: packages/replay-engine/tests — golden canonical stream (feature 006 phase 3)
- evidence: specs/006-replay-analysis-foundations/research.md D10

### `event.participant`

- status: planned
- source: the issuing player of an action
- method: player identifier of the action; absent only on match-level events, never an observer or empty slot
- requires knowledge: none
- depends on: none
- validation: packages/replay-engine/tests — golden canonical stream (feature 006 phase 3)
- evidence: specs/006-replay-analysis-foundations/research.md D10

### `event.match_started.game_build`

- status: planned
- source: the recording header's game build field
- method: read unchanged
- requires knowledge: none
- depends on: none
- validation: packages/replay-engine/tests — golden canonical stream (feature 006 phase 3)
- evidence: specs/006-replay-analysis-foundations/research.md D10

### `event.match_started.map`

- status: planned
- source: the recording header's resolved map field
- method: read unchanged
- requires knowledge: none
- depends on: none
- validation: packages/replay-engine/tests — golden canonical stream (feature 006 phase 3)
- evidence: specs/006-replay-analysis-foundations/research.md D10

### `event.match_started.lobby_presets`

- status: planned
- source: the recording header's lobby preset fields
- method: read unchanged
- requires knowledge: none
- depends on: none
- validation: packages/replay-engine/tests — golden canonical stream (feature 006 phase 3)
- evidence: specs/006-replay-analysis-foundations/research.md D10

### `event.match_started.participants`

- status: planned
- source: the recording header's game-settings player slots
- method: read unchanged; observers and empty slots are omitted, not present and silent
- requires knowledge: none
- depends on: none
- validation: packages/replay-engine/tests — golden canonical stream (feature 006 phase 3)
- evidence: specs/006-replay-analysis-foundations/research.md D10

### `event.unit_queued.unit_id`

- status: planned
- source: a named field of the training-queue command
- method: read unchanged
- requires knowledge: none
- depends on: none
- validation: packages/replay-engine/tests — golden canonical stream (feature 006 phase 3)
- evidence: specs/006-replay-analysis-foundations/research.md D10

### `event.unit_queued.producing_building`

- status: planned
- source: a named field of the training-queue command
- method: read unchanged
- requires knowledge: none
- depends on: none
- validation: packages/replay-engine/tests — golden canonical stream (feature 006 phase 3)
- evidence: specs/006-replay-analysis-foundations/research.md D10

### `event.unit_queued.count`

- status: planned
- source: a named field of the training-queue command
- method: read unchanged
- requires knowledge: none
- depends on: none
- validation: packages/replay-engine/tests — golden canonical stream (feature 006 phase 3)
- evidence: specs/006-replay-analysis-foundations/research.md D10

### `event.research_queued.technology_id`

- status: planned
- source: a named field of the research command
- method: read unchanged; first occurrence collapse
- requires knowledge: none
- depends on: none
- validation: packages/replay-engine/tests — golden canonical stream (feature 006 phase 3)
- evidence: specs/006-replay-analysis-foundations/research.md D10

### `event.research_queued.researching_building`

- status: planned
- source: a named field of the research command
- method: read unchanged; first occurrence collapse
- requires knowledge: none
- depends on: none
- validation: packages/replay-engine/tests — golden canonical stream (feature 006 phase 3)
- evidence: specs/006-replay-analysis-foundations/research.md D10

### `event.units_commanded.command_class`

- status: planned
- source: the wheel's own name for the command variant
- method: read unchanged, mapped to the closed command-class vocabulary
- requires knowledge: none
- depends on: none
- validation: packages/replay-engine/tests — golden canonical stream (feature 006 phase 3)
- evidence: specs/006-replay-analysis-foundations/research.md D10

### `event.units_commanded.unit_object_ids`

- status: planned
- source: the unit identifier list of a move, interact or order command
- method: read unchanged; other command kinds carry no ids and yield an empty list, never a guess
- requires knowledge: none
- depends on: none
- validation: packages/replay-engine/tests — golden canonical stream (feature 006 phase 3)
- evidence: specs/006-replay-analysis-foundations/research.md D10

### `event.units_commanded.target`

- status: planned
- source: the target field of an interact or order command
- method: read unchanged; optional
- requires knowledge: none
- depends on: none
- validation: packages/replay-engine/tests — golden canonical stream (feature 006 phase 3)
- evidence: specs/006-replay-analysis-foundations/research.md D10

### `event.match_ended.final_clock_ms`

- status: planned
- source: the recording's post-game world-time block
- method: read unchanged
- requires knowledge: none
- depends on: none
- validation: packages/replay-engine/tests — golden canonical stream (feature 006 phase 3)
- evidence: specs/006-replay-analysis-foundations/research.md D10

### `event.undecoded.operation_label`

- status: planned
- source: the wheel's own label for an action it does not map
- method: carried as an opaque label, never the payload's shape
- requires knowledge: none
- depends on: none
- validation: packages/replay-engine/tests — golden canonical stream (feature 006 phase 3)
- evidence: specs/006-replay-analysis-foundations/research.md D10

### `event.undecoded.payload_length`

- status: planned
- source: the byte length of the unmapped action's payload
- method: read unchanged; no bytes and no offsets are carried
- requires knowledge: none
- depends on: none
- validation: packages/replay-engine/tests — golden canonical stream (feature 006 phase 3)
- evidence: specs/006-replay-analysis-foundations/research.md D10

## decoded (18)

Read from the recording after decoding an encoded field.

### `participant.builds.building_id`

- status: published
- source: the raw payload of a build command; the pinned wheel returns it undecoded
- method: the repository's own build-payload decoder, golden-tested against every committed recording
- document path: `participants[].builds[].building_id`
- requires knowledge: none
- depends on: none
- validation: packages/replay-engine/tests/test_extract.py — golden timeline
- evidence: specs/003-player-search-match-analysis/research.md R4

### `participant.villagers_ordered`

- status: published
- source: villager training commands and their cancellation counterparts, per participant
- method: sum of ordered amounts less cancelled amounts; a count of commands, never a population
- document path: `participants[].villagers_ordered`
- requires knowledge: none
- depends on: `participant.trainings.unit_id`, `participant.trainings.amount`
- validation: packages/replay-engine/tests/test_extract.py — golden timeline
- evidence: specs/003-player-search-match-analysis/research.md R1

### `participant.actions`

- status: published
- source: every action operation issued by the participant
- method: count of action operations before any collapse
- document path: `participants[].actions`
- requires knowledge: none
- depends on: none
- validation: packages/replay-engine/tests/test_extract.py — golden timeline
- evidence: specs/006-replay-analysis-foundations/research.md D10

### `participant.actions_per_minute`

- status: published
- source: the participant's action count and the match clock's end
- method: actions divided by match minutes; zero when the clock is zero
- document path: `participants[].actions_per_minute`
- requires knowledge: none
- depends on: `participant.actions`, `match.world_time_ms`
- validation: packages/replay-engine/tests/test_extract.py — golden timeline
- evidence: specs/003-player-search-match-analysis/research.md R1

### `event.building_placed.building_id`

- status: planned
- source: the raw payload of a build command
- method: the repository's own build-payload decoder
- requires knowledge: none
- depends on: none
- validation: packages/replay-engine/tests — golden canonical stream (feature 006 phase 3)
- evidence: specs/006-replay-analysis-foundations/research.md D10

### `event.building_placed.position`

- status: planned
- source: the raw payload of a build command
- method: the repository's own build-payload decoder
- requires knowledge: none
- depends on: none
- validation: packages/replay-engine/tests — golden canonical stream (feature 006 phase 3)
- evidence: specs/006-replay-analysis-foundations/research.md D10

### `event.chat.channel`

- status: planned
- source: the channel inside the chat operation's JSON string
- method: the repository's own decoder; the message text is discarded at the adapter and appears nowhere
- requires knowledge: none
- depends on: none
- validation: packages/replay-engine/tests — golden canonical stream (feature 006 phase 3)
- evidence: specs/006-replay-analysis-foundations/research.md D10

### `event.object_deleted.object_id`

- status: planned
- source: the raw payload of an explicit delete command; the pinned wheel returns it as undecoded bytes
- method: the repository's own delete-payload decoder, golden-tested over every committed recording; exact, and never blended into an inferred quantity
- requires knowledge: none
- depends on: none
- validation: packages/replay-engine/tests — golden canonical stream (feature 006 phase 3)
- evidence: specs/006-replay-analysis-foundations/research.md D10

### `event.market_transaction.direction`

- status: planned
- source: the raw payload of a market sell or buy command; the pinned wheel returns it as undecoded bytes
- method: the repository's own market-payload decoder, golden-tested over every committed recording; exact, and never blended into an inferred quantity
- requires knowledge: none
- depends on: none
- validation: packages/replay-engine/tests — golden canonical stream (feature 006 phase 3)
- evidence: specs/006-replay-analysis-foundations/research.md D10

### `event.market_transaction.resource`

- status: planned
- source: the raw payload of a market sell or buy command; the pinned wheel returns it as undecoded bytes
- method: the repository's own market-payload decoder, golden-tested over every committed recording; exact, and never blended into an inferred quantity. The code is read from the payload and only 0, 1 and 2 occur; the names food, wood and stone are the game's own resource enumeration, which the recordings cannot confirm by themselves
- requires knowledge: none
- depends on: none
- validation: packages/replay-engine/tests — golden canonical stream (feature 006 phase 3)
- evidence: specs/006-replay-analysis-foundations/research.md D10

### `event.market_transaction.amount`

- status: planned
- source: the raw payload of a market sell or buy command; the pinned wheel returns it as undecoded bytes
- method: the repository's own market-payload decoder, golden-tested over every committed recording; exact, and never blended into an inferred quantity. The payload carries a count of market steps, only 1 and 5 occurring; the amount is that count times the game's fixed step of 100 units, a constant the recordings do not carry
- requires knowledge: none
- depends on: none
- validation: packages/replay-engine/tests — golden canonical stream (feature 006 phase 3)
- evidence: specs/006-replay-analysis-foundations/research.md D10

### `participant.starting_attributes`

- status: blocked
- blocked on: the starting-attributes decoder (feature 007, research D1 tier A)
- source: the per-player attribute array in the decompressed header, present in the file and reachable by no working parser
- method: a repository-local decoder anchored on the participant's name string, golden-tested against committed recordings
- requires knowledge: none
- depends on: none
- validation: packages/replay-engine/tests — golden starting attributes (feature 007)
- evidence: specs/006-replay-analysis-foundations/research.md D1

### `participant.starting_resources`

- status: blocked
- blocked on: the starting-attributes decoder (feature 007, research D1 tier A)
- source: the first entries of the participant's starting attribute array: food, wood, stone and gold
- method: read from the decoded attribute array in the engine's own resource order
- requires knowledge: none
- depends on: `participant.starting_attributes`
- validation: packages/replay-engine/tests — golden starting attributes (feature 007)
- evidence: specs/006-replay-analysis-foundations/research.md D1

### `event.starting_attributes.values`

- status: blocked
- blocked on: the starting-attributes decoder (feature 007, research D1 tier A)
- source: the per-participant attribute values of the declared-only starting-attributes canonical event
- method: emitted by the starting-attributes decoder once it exists; the type is declared now so its arrival changes no type
- requires knowledge: none
- depends on: `participant.starting_attributes`
- validation: a test asserts the adapter emits no such event until the decoder lands
- evidence: specs/006-replay-analysis-foundations/research.md D1

### `map.starting_objects`

- status: blocked
- blocked on: the starting-object-table decoder (feature 007, research D1 tier B)
- source: the Gaia and per-player object table in the decompressed header, present in the file and behind a variable-length grammar
- method: a repository-local decoder ported from an existing open grammar, golden-tested against committed recordings
- requires knowledge: none
- depends on: none
- validation: packages/replay-engine/tests — golden object table (feature 007)
- evidence: specs/006-replay-analysis-foundations/research.md D1

### `event.starting_object.attributes`

- status: blocked
- blocked on: the starting-object-table decoder (feature 007, research D1 tier B)
- source: the object identifier, class, position and owner of the declared-only starting-object canonical event
- method: emitted by the starting-object-table decoder once it exists; the type is declared now so its arrival changes no type
- requires knowledge: none
- depends on: `map.starting_objects`
- validation: a test asserts the adapter emits no such event until the decoder lands
- evidence: specs/006-replay-analysis-foundations/research.md D1

### `participant.start_position`

- status: blocked
- blocked on: the starting-object-table decoder (feature 007, research D1 tier B)
- source: the position of the participant's starting town centre among the decoded starting objects
- method: read from the decoded object table; the participant is the object's owner
- requires knowledge: none
- depends on: `map.starting_objects`
- validation: packages/replay-engine/tests — golden object table (feature 007)
- evidence: specs/006-replay-analysis-foundations/research.md D1

### `map.resource_geometry`

- status: blocked
- blocked on: the starting-object-table decoder (feature 007, research D1 tier B)
- source: the positions of gold, stone, berries, huntables and forest among the decoded objects and the terrain
- method: read from the decoded object table and the terrain grid; deferred behind feature 007's income work
- requires knowledge: none
- depends on: `map.starting_objects`
- validation: packages/replay-engine/tests — golden object table (feature 007)
- evidence: specs/006-replay-analysis-foundations/research.md D1

## reconstructed (7)

Rebuilt from several recorded facts.

### `reconstruction.resources_spent`

- status: planned
- source: queued units, researched technologies and placed buildings, priced by the versioned knowledge base for the participant's civilisation
- method: sum, per resource, of the knowledge base's cost for each ordered entity, cancellations subtracted; an order is a command, not a completion
- requires knowledge: `cost`
- depends on: `event.unit_queued.unit_id`, `event.unit_queued.count`, `event.research_queued.technology_id`, `event.building_placed.building_id`, `event.match_started.participants`
- validation: feature 007 golden reconstruction fixtures and reconstruction invariants
- evidence: specs/006-replay-analysis-foundations/spec.md (Out of Scope: feature 007)

### `reconstruction.ordered_production_ms`

- status: planned
- source: queued units and researched technologies, timed by the versioned knowledge base for the participant's civilisation
- method: sum of the knowledge base's production time for each order against the producing building, per building; an order is a command, not a completion
- requires knowledge: `production_time`, `produced_at`
- depends on: `event.unit_queued.unit_id`, `event.unit_queued.count`, `event.unit_queued.producing_building`, `event.research_queued.technology_id`, `event.research_queued.researching_building`, `event.match_started.participants`
- validation: feature 007 golden reconstruction fixtures and reconstruction invariants
- evidence: specs/006-replay-analysis-foundations/spec.md (Out of Scope: feature 007)

### `reconstruction.age_up_modelled_arrival_ms`

- status: planned
- source: the age-up research command and the knowledge base's research time for that age and civilisation
- method: command time plus the modelled research time; a model of an arrival, kept apart from the observed command time
- requires knowledge: `production_time`
- depends on: `participant.age_up_commands`, `event.match_started.participants`
- validation: feature 007 golden reconstruction fixtures and reconstruction invariants
- evidence: specs/006-replay-analysis-foundations/spec.md (Out of Scope: feature 007)

### `reconstruction.prerequisite_order_check`

- status: planned
- source: ordered entities and their required age and prerequisite buildings from the versioned knowledge base
- method: for each order, whether its age requirement and prerequisites were commanded earlier on the match clock
- requires knowledge: `age_requirement`, `prerequisites`, `available_to`
- depends on: `event.unit_queued.unit_id`, `event.research_queued.technology_id`, `event.building_placed.building_id`, `event.clock_ms`, `event.match_started.participants`
- validation: feature 007 golden reconstruction fixtures and reconstruction invariants
- evidence: specs/006-replay-analysis-foundations/spec.md (Out of Scope: feature 007)

### `reconstruction.income_model`

- status: blocked
- blocked on: the starting-attributes decoder (feature 007, research D1 tier A)
- source: the reconstructed spending and the participant's decoded starting resources
- method: starting resources plus modelled income less modelled spending over the match clock
- requires knowledge: `cost`
- depends on: `participant.starting_resources`, `reconstruction.resources_spent`
- validation: feature 007 golden reconstruction fixtures and reconstruction invariants
- evidence: specs/006-replay-analysis-foundations/spec.md (Out of Scope: feature 007)

### `reconstruction.exploration_coverage`

- status: blocked
- blocked on: the starting-object-table decoder (feature 007, research D1 tier B)
- source: the participant's start position, commanded movement and the map's decoded objects
- method: tiles within modelled line of sight of commanded positions; a model of sight, never an observation of what was seen
- requires knowledge: `line_of_sight`
- depends on: `participant.start_position`, `map.starting_objects`, `event.units_commanded.unit_object_ids`
- validation: feature 007 golden reconstruction fixtures and reconstruction invariants
- evidence: specs/006-replay-analysis-foundations/spec.md (Out of Scope: feature 007)

### `reconstruction.map_control_model`

- status: blocked
- blocked on: the starting-object-table decoder (feature 007, research D1 tier B)
- source: decoded starting objects, placed buildings and commanded movement
- method: a modelled reading of where each participant had presence; not a measurement of control
- requires knowledge: `line_of_sight`
- depends on: `map.starting_objects`, `event.building_placed.position`, `event.units_commanded.unit_object_ids`
- validation: feature 007 golden reconstruction fixtures and reconstruction invariants
- evidence: specs/006-replay-analysis-foundations/spec.md (Out of Scope: feature 007)

## derived (1)

Computed from other published data.

### `reconstruction.ordered_army_cost`

- status: planned
- source: the reconstructed resources spent on military units ordered
- method: resources spent restricted to units the knowledge base classes as military; a spending figure, not an army value, since losses are unknowable
- requires knowledge: `cost`
- depends on: `reconstruction.resources_spent`
- validation: feature 007 golden reconstruction fixtures and reconstruction invariants
- evidence: specs/006-replay-analysis-foundations/spec.md (Out of Scope: feature 007)

## inferred (1)

A signal read from behaviour, not a recorded fact.

### `participant.group_silence_episodes`

- status: planned
- source: unit object identifiers named by move, interact and order commands, and the match clock
- method: an episode is a group of unit identifiers commanded together repeatedly and then named by no later command; the confidence basis is the ratio of commands naming the group before the silence to the length of the silence, banded into the closed confidence levels. It sees only three command kinds, so a group told to hold or patrol and never moved again reads as silent. The band thresholds are fixed by the method's identifier and version when the algorithm lands, and this entry is amended in the same change
- non-claim: this is not a casualty count and not a count of units lost: a unit leaves the command log when its owner stops selecting it, alive or dead, and a unit never individually selected is never in the log at all; a group told to hold, patrol or stop reads as silent
- confidence method: ratio of commands naming the group before the silence to the length of the silence, banded into the closed confidence levels; algorithm identifier and version recorded with each value
- requires knowledge: none
- depends on: `event.units_commanded.unit_object_ids`, `event.clock_ms`, `event.participant`
- validation: packages/replay-engine/tests — synthetic silence streams and both committed recordings (feature 006 phase 3)
- evidence: specs/006-replay-analysis-foundations/research.md D10
