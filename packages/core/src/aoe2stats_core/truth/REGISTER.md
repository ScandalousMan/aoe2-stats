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

## observed (45)

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

### `event.unit_queued.building_type`

- status: planned
- source: a named field of the training-queue command
- method: read unchanged
- requires knowledge: none
- depends on: none
- validation: packages/replay-engine/tests — golden canonical stream (feature 006 phase 3)
- evidence: specs/006-replay-analysis-foundations/research.md D10

### `event.unit_queued.building_object`

- status: planned
- source: the training-queue command's list of producing-building object ids
- method: the first id in the list is kept; a command naming several producing buildings still yields one event, and the rest are not represented — a narrowing of the vocabulary, not a re-decoding of the omitted ones
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

### `event.unit_unqueued.unit_id`

- status: planned
- source: a named field of a top-level cancellation command (Unqueue, FarmUnqueue, FishtrapUnqueue)
- method: read unchanged, only when the payload carries both an integer unit id and an integer amount; any other shape stays undecoded rather than guessed
- requires knowledge: none
- depends on: none
- validation: packages/replay-engine/tests/test_canonical.py::test_a_top_level_cancellation_is_a_unit_unqueued_event — synthetic: neither committed recording produces a cancellation (feature 006 phase 3, T633)
- evidence: specs/006-replay-analysis-foundations/research.md D10

### `event.unit_unqueued.count`

- status: planned
- source: a named field of a top-level cancellation command (Unqueue, FarmUnqueue, FishtrapUnqueue)
- method: read unchanged, only when the payload carries both an integer unit id and an integer amount; any other shape stays undecoded rather than guessed
- requires knowledge: none
- depends on: none
- validation: packages/replay-engine/tests/test_canonical.py::test_a_top_level_cancellation_is_a_unit_unqueued_event — synthetic: neither committed recording produces a cancellation (feature 006 phase 3, T633)
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

### `event.unit_queued.building_objects`

- status: planned
- source: the training-queue command's full list of producing-building object ids
- method: every id in the list is kept, in order; a command naming several producing buildings yields all of them, so none is narrowed away (FR-030)
- requires knowledge: none
- depends on: none
- validation: packages/replay-engine/tests — golden canonical stream (feature 008)
- evidence: specs/008-match-reconstruction/spec.md FR-030

### `participant.units_seen`

- status: planned
- source: the object ids a participant's commands name in a unit list, and the match clock
- method: for each object id named in a unit list from which no order is issued as a building, the first and last clock at which the participant's commands name it, and who names it afterwards when another participant does; neither a birth, a completion nor a death
- requires knowledge: none
- depends on: `event.units_commanded.unit_object_ids`, `event.unit_queued.building_objects`, `event.clock_ms`, `event.participant`
- validation: feature 008 golden seen-data fixtures (contracts/estimates.md)
- evidence: specs/008-match-reconstruction/contracts/estimates.md

### `participant.producing_buildings_seen`

- status: planned
- source: the producing-building object ids a participant's orders name, and the match clock
- method: for each building a participant issues an order from, every building of a command included, the first and last clock of those orders; neither a completion nor a destruction
- requires knowledge: none
- depends on: `event.unit_queued.building_objects`, `event.research_queued.researching_building`, `event.clock_ms`, `event.participant`
- validation: feature 008 golden seen-data fixtures (contracts/estimates.md)
- evidence: specs/008-match-reconstruction/contracts/estimates.md

## decoded (21)

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

### `event.market_transaction.steps`

- status: planned
- source: the raw payload of a market sell or buy command; the pinned wheel returns it as undecoded bytes
- method: the repository's own market-payload decoder, golden-tested over every committed recording; exact, and never blended into an inferred quantity. The payload carries a count of market steps, only 1 and 5 occurring, and that count is published unmultiplied — the step's size in resource units (100) is the game's fixed constant, not carried by any recording, and multiplying it is 008's reconstruction layer's job, behind a versioned constant that can gap
- requires knowledge: none
- depends on: none
- validation: packages/replay-engine/tests — golden canonical stream (feature 006 phase 3)
- evidence: specs/006-replay-analysis-foundations/research.md D10

### `participant.starting_attributes`

- status: blocked
- blocked on: the starting-attributes decoder (feature 008, research D1 tier A)
- source: the per-player attribute array in the decompressed header, present in the file and reachable by no working parser
- method: a repository-local decoder anchored on the participant's name string, golden-tested against committed recordings
- requires knowledge: none
- depends on: none
- validation: packages/replay-engine/tests — golden starting attributes (feature 008)
- evidence: specs/006-replay-analysis-foundations/research.md D1

### `participant.starting_resources`

- status: blocked
- blocked on: the starting-attributes decoder (feature 008, research D1 tier A)
- source: the first entries of the participant's starting attribute array: food, wood, stone and gold
- method: read from the decoded attribute array in the engine's own resource order
- requires knowledge: none
- depends on: `participant.starting_attributes`
- validation: packages/replay-engine/tests — golden starting attributes (feature 008)
- evidence: specs/006-replay-analysis-foundations/research.md D1

### `event.starting_attributes.values`

- status: blocked
- blocked on: the starting-attributes decoder (feature 008, research D1 tier A)
- source: the per-participant attribute values of the declared-only starting-attributes canonical event
- method: emitted by the starting-attributes decoder once it exists; the type is declared now so its arrival changes no type
- requires knowledge: none
- depends on: `participant.starting_attributes`
- validation: a test asserts the adapter emits no such event until the decoder lands
- evidence: specs/006-replay-analysis-foundations/research.md D1

### `map.starting_objects`

- status: blocked
- blocked on: the starting-object-table decoder (feature 008, research D1 tier B)
- source: the Gaia and per-player object table in the decompressed header, present in the file and behind a variable-length grammar
- method: a repository-local decoder ported from an existing open grammar, golden-tested against committed recordings
- requires knowledge: none
- depends on: none
- validation: packages/replay-engine/tests — golden object table (feature 008)
- evidence: specs/006-replay-analysis-foundations/research.md D1

### `event.starting_object.object_id`

- status: blocked
- blocked on: the starting-object-table decoder (feature 008, research D1 tier B)
- source: the object identifier of the declared-only starting-object canonical event
- method: emitted by the starting-object-table decoder once it exists; the type is declared now so its arrival changes no type
- requires knowledge: none
- depends on: `map.starting_objects`
- validation: a test asserts the adapter emits no such event until the decoder lands
- evidence: specs/006-replay-analysis-foundations/research.md D1

### `event.starting_object.object_class`

- status: blocked
- blocked on: the starting-object-table decoder (feature 008, research D1 tier B)
- source: the object class of the declared-only starting-object canonical event
- method: emitted by the starting-object-table decoder once it exists; the type is declared now so its arrival changes no type
- requires knowledge: none
- depends on: `map.starting_objects`
- validation: a test asserts the adapter emits no such event until the decoder lands
- evidence: specs/006-replay-analysis-foundations/research.md D1

### `event.starting_object.position`

- status: blocked
- blocked on: the starting-object-table decoder (feature 008, research D1 tier B)
- source: the position of the declared-only starting-object canonical event
- method: emitted by the starting-object-table decoder once it exists; the type is declared now so its arrival changes no type
- requires knowledge: none
- depends on: `map.starting_objects`
- validation: a test asserts the adapter emits no such event until the decoder lands
- evidence: specs/006-replay-analysis-foundations/research.md D1

### `event.starting_object.owner`

- status: blocked
- blocked on: the starting-object-table decoder (feature 008, research D1 tier B)
- source: the owning participant of the declared-only starting-object canonical event
- method: emitted by the starting-object-table decoder once it exists; the type is declared now so its arrival changes no type
- requires knowledge: none
- depends on: `map.starting_objects`
- validation: a test asserts the adapter emits no such event until the decoder lands
- evidence: specs/006-replay-analysis-foundations/research.md D1

### `participant.start_position`

- status: blocked
- blocked on: the starting-object-table decoder (feature 008, research D1 tier B)
- source: the position of the participant's starting town centre among the decoded starting objects
- method: read from the decoded object table; the participant is the object's owner
- requires knowledge: none
- depends on: `map.starting_objects`
- validation: packages/replay-engine/tests — golden object table (feature 008)
- evidence: specs/006-replay-analysis-foundations/research.md D1

### `map.resource_geometry`

- status: blocked
- blocked on: the starting-object-table decoder (feature 008, research D1 tier B)
- source: the positions of gold, stone, berries, huntables and forest among the decoded objects and the terrain
- method: read from the decoded object table and the terrain grid; deferred behind feature 008's income work
- requires knowledge: none
- depends on: `map.starting_objects`
- validation: packages/replay-engine/tests — golden object table (feature 008)
- evidence: specs/006-replay-analysis-foundations/research.md D1

## reconstructed (9)

Rebuilt from several recorded facts.

### `reconstruction.resources_spent`

- status: planned
- source: queued units, researched technologies and placed buildings, priced by the versioned knowledge base for the participant's civilisation
- method: sum, per resource, of the knowledge base's cost for each ordered entity, cancellations subtracted; an order is a command, not a completion
- requires knowledge: `cost`
- depends on: `event.unit_queued.unit_id`, `event.unit_queued.count`, `event.research_queued.technology_id`, `event.building_placed.building_id`, `event.match_started.participants`
- validation: feature 008 golden reconstruction fixtures and reconstruction invariants
- evidence: specs/006-replay-analysis-foundations/spec.md (Out of Scope: feature 008)

### `reconstruction.ordered_production_ms`

- status: planned
- source: queued units and researched technologies, timed by the versioned knowledge base for the participant's civilisation
- method: sum of the knowledge base's production time for each order against the producing building, per building; an order is a command, not a completion
- requires knowledge: `production_time`, `produced_at`
- depends on: `event.unit_queued.unit_id`, `event.unit_queued.count`, `event.unit_queued.building_object`, `event.research_queued.technology_id`, `event.research_queued.researching_building`, `event.match_started.participants`
- validation: feature 008 golden reconstruction fixtures and reconstruction invariants
- evidence: specs/006-replay-analysis-foundations/spec.md (Out of Scope: feature 008)

### `reconstruction.age_up_modelled_arrival_ms`

- status: planned
- source: the age-up research command and the knowledge base's research time for that age and civilisation
- method: command time plus the modelled research time; a model of an arrival, kept apart from the observed command time
- requires knowledge: `production_time`
- depends on: `participant.age_up_commands`, `event.match_started.participants`
- validation: feature 008 golden reconstruction fixtures and reconstruction invariants
- evidence: specs/006-replay-analysis-foundations/spec.md (Out of Scope: feature 008)

### `reconstruction.prerequisite_order_check`

- status: blocked
- blocked on: a lawful source that states the game's own prerequisites — the vendored aoe2techtree pack's tree entries carry only the tech-tree screen's display link, not a game rule (T652y, research.md D3)
- source: ordered entities and their required age and prerequisite buildings from the versioned knowledge base
- method: for each order, whether its age requirement and prerequisites were commanded earlier on the match clock
- requires knowledge: `age_requirement`, `prerequisites`, `available_to`
- depends on: `event.unit_queued.unit_id`, `event.research_queued.technology_id`, `event.building_placed.building_id`, `event.clock_ms`, `event.match_started.participants`
- validation: feature 008 golden reconstruction fixtures and reconstruction invariants
- evidence: specs/006-replay-analysis-foundations/spec.md (Out of Scope: feature 008)

### `reconstruction.income_model`

- status: blocked
- blocked on: the starting-attributes decoder (feature 008, research D1 tier A)
- source: the reconstructed spending and the participant's decoded starting resources
- method: starting resources plus modelled income less modelled spending over the match clock
- requires knowledge: `cost`
- depends on: `participant.starting_resources`, `reconstruction.resources_spent`
- validation: feature 008 golden reconstruction fixtures and reconstruction invariants
- evidence: specs/006-replay-analysis-foundations/spec.md (Out of Scope: feature 008)

### `reconstruction.exploration_coverage`

- status: blocked
- blocked on: the starting-object-table decoder (feature 008, research D1 tier B)
- source: the participant's start position, commanded movement and the map's decoded objects
- method: tiles within modelled line of sight of commanded positions; a model of sight, never an observation of what was seen
- requires knowledge: `line_of_sight`
- depends on: `participant.start_position`, `map.starting_objects`, `event.units_commanded.unit_object_ids`
- validation: feature 008 golden reconstruction fixtures and reconstruction invariants
- evidence: specs/006-replay-analysis-foundations/spec.md (Out of Scope: feature 008)

### `reconstruction.map_control_model`

- status: blocked
- blocked on: the starting-object-table decoder (feature 008, research D1 tier B)
- source: decoded starting objects, placed buildings and commanded movement
- method: a modelled reading of where each participant had presence; not a measurement of control
- requires knowledge: `line_of_sight`
- depends on: `map.starting_objects`, `event.building_placed.position`, `event.units_commanded.unit_object_ids`
- validation: feature 008 golden reconstruction fixtures and reconstruction invariants
- evidence: specs/006-replay-analysis-foundations/spec.md (Out of Scope: feature 008)

### `reconstruction.population`

- status: planned
- source: the participant's ordered units, the starting state and the knowledge base; the deduction strategy for what the recording does not carry is chosen by FR-012
- method: the exact population of a participant over the match; the method is chosen by FR-012 and adopted only after the candidate rules are checked against the game's playback (FR-019); until then only the estimates of FR-034 are published, under their own names
- requires knowledge: `production_time`, `produced_at`
- depends on: `event.unit_queued.unit_id`, `event.unit_queued.count`, `event.unit_queued.building_object`, `event.match_started.participants`
- validation: feature 008 golden reconstruction fixtures and reconstruction invariants
- evidence: specs/008-match-reconstruction/spec.md FR-001a, FR-012

### `reconstruction.town_center_idle_ms`

- status: planned
- source: the orders attributed to each Town Center and the knowledge base's production times
- method: the exact idle time of each Town Center, from an empty queue to its next order; the method is chosen by FR-012 and checked against the game's playback (FR-019); until then only the estimated idle periods of FR-035 are published, under their own name
- requires knowledge: `production_time`, `produced_at`
- depends on: `event.unit_queued.unit_id`, `event.unit_queued.count`, `event.unit_queued.building_object`, `event.research_queued.technology_id`, `event.research_queued.researching_building`, `event.match_started.participants`
- validation: feature 008 golden reconstruction fixtures and reconstruction invariants
- evidence: specs/008-match-reconstruction/spec.md FR-001a, FR-012

## derived (6)

Computed from other published data.

### `names.snapshot.describes_build`

- status: published
- source: the knowledge snapshot the document's own identity names, among every packaged snapshot
- method: copied from that snapshot's identity when the stored document is served; absent when the identity names no installed snapshot
- document path: `knowledge_names.snapshot.describes_build`
- requires knowledge: `name`
- depends on: none
- validation: apps/analyzer/tests/test_names.py
- evidence: docs/data-sources.md §6

### `names.snapshot.digest`

- status: published
- source: the knowledge snapshot the document's own identity names, among every packaged snapshot
- method: copied from that snapshot's identity when the stored document is served; it equals the digest the document's identity records, which is how the snapshot is matched
- document path: `knowledge_names.snapshot.digest`
- requires knowledge: `name`
- depends on: none
- validation: apps/analyzer/tests/test_names.py
- evidence: docs/data-sources.md §6

### `names.technology`

- status: published
- source: the display name the named knowledge snapshot gives a technology id
- method: the snapshot's own name for each technology id the document researched or age-upped, keyed by the stringified id, with the source's line-break markup removed by one rule: a hyphen directly after a letter, followed by a run of line-break tags and whitespace and then a lower-case letter (any Unicode lower-case letter), joins the word, so the hyphen and the whole run go; the same hyphen followed by such a run and then any other character keeps the hyphen and drops the run with no space; a hyphen not directly after a letter is left alone; every other break becomes one space, whitespace collapses and the label is trimmed; a label with no letter or digit left is not served; an id the snapshot does not name, or whose label is not served, is left out, never replaced
- document path: `knowledge_names.technology.*`
- requires knowledge: `name`
- depends on: `participant.researches.technology_id`, `participant.age_up_commands`
- validation: apps/analyzer/tests/test_names.py
- evidence: docs/data-sources.md §6

### `names.unit`

- status: published
- source: the display name the named knowledge snapshot gives a unit id
- method: the snapshot's own name for each unit id the document trained, keyed by the stringified id, with the source's line-break markup removed by one rule: a hyphen directly after a letter, followed by a run of line-break tags and whitespace and then a lower-case letter (any Unicode lower-case letter), joins the word, so the hyphen and the whole run go; the same hyphen followed by such a run and then any other character keeps the hyphen and drops the run with no space; a hyphen not directly after a letter is left alone; every other break becomes one space, whitespace collapses and the label is trimmed; a label with no letter or digit left is not served; an id the snapshot does not name, or whose label is not served, is left out, never replaced
- document path: `knowledge_names.unit.*`
- requires knowledge: `name`
- depends on: `participant.trainings.unit_id`
- validation: apps/analyzer/tests/test_names.py
- evidence: docs/data-sources.md §6

### `names.building`

- status: published
- source: the display name the named knowledge snapshot gives a building id
- method: the snapshot's own name for each building id the document built, keyed by the stringified id, with the source's line-break markup removed by one rule: a hyphen directly after a letter, followed by a run of line-break tags and whitespace and then a lower-case letter (any Unicode lower-case letter), joins the word, so the hyphen and the whole run go; the same hyphen followed by such a run and then any other character keeps the hyphen and drops the run with no space; a hyphen not directly after a letter is left alone; every other break becomes one space, whitespace collapses and the label is trimmed; a label with no letter or digit left is not served; an id the snapshot does not name, or whose label is not served, is left out, never replaced
- document path: `knowledge_names.building.*`
- requires knowledge: `name`
- depends on: `participant.builds.building_id`
- validation: apps/analyzer/tests/test_names.py
- evidence: docs/data-sources.md §6

### `reconstruction.ordered_army_cost`

- status: planned
- source: the reconstructed resources spent on military units ordered
- method: resources spent restricted to units the knowledge base classes as military; a spending figure, not an army value, since losses are unknowable
- requires knowledge: `cost`
- depends on: `reconstruction.resources_spent`
- validation: feature 008 golden reconstruction fixtures and reconstruction invariants
- evidence: specs/006-replay-analysis-foundations/spec.md (Out of Scope: feature 008)

## inferred (6)

A signal read from behaviour, not a recorded fact.

### `participant.group_silence_episodes`

- status: published
- source: unit object identifiers named by move, interact and order commands, the match clock, participant-resigned and match-ended
- method: group-silence.banding v1 (T633): a group is two or more unit object ids named together by one participant's move, interact or order command (the only classes carrying decoded ids), seen together on at least REPEAT_MIN=2 separate occasions, then never named together again before that participant's exit or the match's end. An episode publishes only when the resulting silence lasts at least MIN_SILENCE_MS=180000 ms. Confidence basis: intensity is the occurrence count above; duration_ratio is the observed silence length divided by the time remaining in the match after the group's last command, measured to the true match end even when the participant resigned first — an observed silence cut short by resignation is therefore a weaker signal than one that ran to the match's own end. Confidence bands: medium when intensity>=MEDIUM_INTENSITY=4 and duration_ratio>=MEDIUM_DURATION_RATIO=0.5, low otherwise. High is never assigned: this method sees only three command kinds — move, interact and order carry decoded unit ids; formation, stance, patrol and stop do not — so a group parked by one of those commands is indistinguishable here from one truly abandoned, and that blind spot caps the level this banding may assign at medium, structurally, not as a per-instance judgement. These four thresholds are read by the implementation from this sentence, not from a Python constant: changing one is a register edit and a regenerated view (packages/replay-engine/src/aoe2stats_replay_engine/silence.py)
- non-claim: this is not a casualty count and not a count of units lost: a unit leaves the command log when its owner stops selecting it, alive or dead, and a unit never individually selected is never in the log at all; a group told to hold, patrol or stop reads as silent
- confidence method: the ratio of the observed silence length to the match time remaining after the group's last command (duration_ratio), combined with the number of times the group was commanded together before it (intensity), banded per the method's MEDIUM_INTENSITY and MEDIUM_DURATION_RATIO thresholds; medium or low only, never high, per the method's blind-spot cap
- requires knowledge: none
- depends on: `event.units_commanded.unit_object_ids`, `event.clock_ms`, `event.participant`, `event.match_ended.final_clock_ms`
- validation: packages/replay-engine/tests/test_silence.py — synthetic silence streams and both committed recordings (feature 006 phase 3, T633)
- evidence: specs/006-replay-analysis-foundations/research.md D10

### `participant.estimated_unit_losses`

- status: planned
- source: enemy commands that target a unit object id, and the participant's own commands naming it
- method: estimated-unit-losses v1: a unit is an identified estimated loss when a command of a participant of another team targets its object id after the last command of its owner naming it and before the owner's resignation, dated at the last such command; a later command of the owner naming it counts no loss; a unit another participant later names as their own is not a loss (FR-032); explicit deletions are not read (FR-036)
- non-claim: an estimate, never a count of units lost: it finds a minority of the units that died, a unit that was attacked and then silent is counted lost whether or not it died, a deleted unit stays alive in the living population and a deleted object an enemy command had targeted is counted lost
- confidence method: level is low until playback readings have measured the estimate's error and the entry names them as its calibration (FR-029); what level a measured error earns is written here in the change that records the error
- requires knowledge: none
- depends on: `participant.units_seen`, `event.units_commanded.unit_object_ids`, `event.clock_ms`, `event.participant`
- validation: feature 008 golden seen-data and estimates fixtures (contracts/estimates.md)
- evidence: specs/008-match-reconstruction/research.md R16, R17

### `participant.estimated_buildings_destroyed`

- status: planned
- source: enemy commands that target a producing-building object id, and the orders issued from it
- method: estimated-buildings-destroyed v1: the rule of FR-032 with the orders issued from a building in place of the commands naming a unit; a building never ordered from is never seen and has no estimated destruction; explicit deletions are not read (FR-036)
- non-claim: an estimate, not a count of buildings destroyed: an attacked building that then orders nothing may have been idle, obsolete or captured; it errs toward counting a surviving building destroyed and toward missing a destroyed one that was never targeted
- confidence method: level is low until playback readings have measured the estimate's error and the entry names them as its calibration (FR-029); what level a measured error earns is written here in the change that records the error
- requires knowledge: none
- depends on: `participant.producing_buildings_seen`, `event.clock_ms`, `event.participant`
- validation: feature 008 golden seen-data and estimates fixtures (contracts/estimates.md)
- evidence: specs/008-match-reconstruction/research.md R16, R17

### `participant.estimated_population_excess`

- status: planned
- source: the estimated living population series and the lobby's population limit
- method: estimated-population-excess v1: where the estimated living population would exceed the lobby's population limit, the excess is published at that clock and removed from the living population; it names no object and no unit type; an identified loss or a change of owner counts for one population (FR-033)
- non-claim: an estimate of the population the model counted that the game's limit would not have allowed, not a count of units that died; commands the game refused are counted, so it errs toward a larger excess
- confidence method: level is low until playback readings have measured the estimate's error and the entry names them as its calibration (FR-029); what level a measured error earns is written here in the change that records the error
- requires knowledge: `production_time`, `produced_at`
- depends on: `event.match_started.participants`, `event.unit_queued.unit_id`, `event.unit_queued.count`, `participant.estimated_unit_losses`
- validation: feature 008 golden seen-data and estimates fixtures (contracts/estimates.md)
- evidence: specs/008-match-reconstruction/research.md R16, R17

### `participant.estimated_living_population`

- status: planned
- source: the starting state, the queue model, the estimated unit losses and the estimated population excess
- method: estimated-living-population v1: the value after each change of the starting units, each unit ordered at the modelled completion of its queue item less the cancellations shown, and a unit another participant named first at this participant's first command naming it, less the identified losses, the population excess and the units that changed owner; never negative, withheld with the population excess if it would be (FR-031, FR-034); interim policies: which commands the game executed and how a command spreads over its buildings until gate G1, which age is in force until the age-up rule of FR-010; explicit deletions are not read (FR-036)
- non-claim: an estimate, not the game's population: commands the game refused are counted, a deleted unit stays in it, a unit no command names enters only through its queue order and leaves only through the population limit, and a pause for want of housing is not modelled
- confidence method: level is low until playback readings have measured the estimate's error and the entry names them as its calibration (FR-029); what level a measured error earns is written here in the change that records the error
- requires knowledge: `production_time`, `produced_at`
- depends on: `participant.estimated_unit_losses`, `participant.estimated_population_excess`, `participant.units_seen`, `event.unit_queued.unit_id`, `event.unit_queued.count`, `event.unit_queued.building_objects`
- validation: feature 008 golden seen-data and estimates fixtures (contracts/estimates.md)
- evidence: specs/008-match-reconstruction/research.md R16, R17

### `participant.estimated_production_idle`

- status: planned
- source: each producing building's orders and its modelled queue
- method: estimated-production-idle v1: the stretches between a building's first and last order during which its modelled queue, built by the method of FR-031, is empty; the time from the last order to its estimated destruction, the owner's exit or the match end is published apart as after_last_order and never summed into idle time (FR-035); explicit deletions are not read (FR-036)
- non-claim: an estimate, not an exact idle time: a pause for want of housing reads as an empty queue, refused commands are counted as production, and the stretch after the last order includes the production of the last items ordered
- confidence method: level is low until playback readings have measured the estimate's error and the entry names them as its calibration (FR-029); what level a measured error earns is written here in the change that records the error
- requires knowledge: `production_time`, `produced_at`
- depends on: `participant.producing_buildings_seen`, `participant.estimated_buildings_destroyed`, `event.unit_queued.unit_id`, `event.unit_queued.count`, `event.unit_queued.building_objects`, `event.research_queued.technology_id`, `event.research_queued.researching_building`
- validation: feature 008 golden seen-data and estimates fixtures (contracts/estimates.md)
- evidence: specs/008-match-reconstruction/research.md R16, R17
