# Native AoE2 DE simulation extraction: feasibility report

- **Feature**: 009 (`specs/009-native-simulation-feasibility/spec.md`)
- **Assessed**: 2026-11-08, on the three committed reference recordings (builds 180059 and 185872)
- **Status**: findings recorded; independent review in §13
- **Companion documents**: the capability matrix
  (`docs/research/native-simulation-capability-matrix.md`), the reverse-engineering assessment
  (`docs/research/native-engine-reverse-engineering.md`), the prototype
  (`scripts/research/009-native-simulation/`)

This document records measured and sourced properties of things outside this repository: the game,
its interfaces, third-party engines and tools. Like `docs/data-sources.md`, it is dated, and a
claim here is either tied to an experiment in this repository or to a source. Labels follow the
spec: **DEMONSTRATED** (run here, or shown working in cited code or a cited recording),
**DOCUMENTED** (a source says so, including a reverse-engineered definition), **INFERRED**
(reasoning, stated as such), **UNKNOWN**. The numbers about the recordings' checkpoints are held
by the prototype's tests, not restated beyond what §6 needs; figures from features 006 and 008 are
cited by their research sections and not copied.

## 1. Executive summary

The question (spec §"What this feature is"): CaptureAge states exactly which building fell, which
technology finished, which unit died and what the population was; can this project reach the same
simulation instead of deducing from the command log?

1. **A `.aoe2record` is a command log plus a header, and the game rebuilds the match by running its
   own simulation over it.** Every exact per-object outcome CaptureAge shows exists only inside a
   running copy of the game, or inside a bit-exact reimplementation of it. Both routes were
   investigated. Neither can be run by this project today without a cost it has not accepted.
2. **Approach A, the game's own gRPC server, exists in the Windows client and is how CaptureAge
   works.** Its existence, and the decoding of hit points, owner, type, position and deaths from
   its stream, are DEMONSTRATED by CaptureAge's own bundled client and by two third-party clients
   (§3); everything else it is said to carry (resource stocks, population, research states, queues,
   construction progress, age, kill events) is DOCUMENTED from reverse-engineered model and proto
   definitions, with fidelity UNKNOWN because the published decoders resynchronise heuristically
   against a per-build model. Three things stand between this project and that route: the client
   certificate is CaptureAge BV's credential, not ours; the state is an opaque binary patch against
   a build-specific model; and it needs the Windows client running. The native macOS build installed
   on the development machine during the spike carries no gRPC code (§2a).
3. **Approach B, `librematch/genie`, is a genuine deterministic engine port** (READ IN CODE, §4)
   but it targets exactly one game build, 158041, cannot read a build 185872 recording, documents
   that a player's objects stop at the first of 236 unsupported situations, has one maintainer, is
   AGPL-3.0 and is ported from the game's decompiled routines. Not viable as a dependency today.
4. **Approach C found nothing else** (§5).
5. **Approach D, reverse engineering with REA, found no evidence of a route A does not cover**
   (INFERRED; `docs/research/native-engine-reverse-engineering.md`). No disassembler ran; the
   installed Mac binary was inspected statically.
6. **One new fact was measured here (DEMONSTRATED, §6): every recording carries the game's own
   state checkpoints.** Every 500 syncs the simulation writes, for each player, eleven 32-bit words.
   Two are corroborated: word 8 is the player id, and word 1 is the four resource stocks summed,
   equal on seven of eight players to the header's starting stocks minus the costs queued before
   the first checkpoint, to the unit. Neither `aoe2rec-py` nor `aoc-mgz` decodes the block; a
   standard-library reader with eighteen tests does. This narrows feature 006's finding that a
   recording carries intent and no outcomes: it carries no per-object outcome and no event, and a
   coarse per-player engine-state sample every 500 syncs.
7. **Recommendation C, hybrid, with a CONDITIONAL GO** (§11). What is GO now: command-log values
   anchored by the recording's own checkpoints (exact, recomputable from the raw file, independent
   of any game install), which is recommendation D plus one engine-written anchor, and is called C
   only because the anchor is the engine's. What is conditional: route A as an owner-run instrument
   for validation and calibration, never a dependency of the deployed product, under the five
   conditions of §11. Route B is a watch item. The product does not promise CaptureAge parity and
   says so.

## 2. Environment, corpus, builds, constraints

**Environment assessed 2026-11-08** (spec FR-006):

| Item           | Finding                                                                                                                                                                                                                                                                                                                                                                                        |
| -------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Host           | MacBook (Mac15,13), Apple M3, 16 GiB, macOS 15.1.1, arm64, System Integrity Protection enabled                                                                                                                                                                                                                                                                                                 |
| Game installed | At the start, no. During the spike (2026-11-08, 15:44 local) the owner installed the native macOS build through Steam: Feral Interactive, bundle version 1.3 (`FeralVersionSuffix` RC5), game version `101.103.57257.0 (#188329)`, Steam build id 26272505, 23.2 GB, one arm64 Mach-O executable of 89 MB with a hardened runtime, `LSMinimumSystemVersion` 14.4. Not launched in this session |
| Windows        | None: no installation, no Parallels, UTM or VMware Fusion, no CrossOver, Whisky or Wine                                                                                                                                                                                                                                                                                                        |
| Analysis tools | No Ghidra, IDA, Hopper or Java; `strings`, `nm`, `otool`, `codesign`, `plutil` from the command-line tools                                                                                                                                                                                                                                                                                     |
| Toolchains     | cargo 1.95.0 and rustc, Docker 28.1.1 with colima, node 24, uv, Python 3.13 and 3.14; no protoc, no grpcurl                                                                                                                                                                                                                                                                                    |
| Recordings     | the three committed fixtures only; no other `.aoe2record` on disk                                                                                                                                                                                                                                                                                                                              |
| Remote hosts   | none configured                                                                                                                                                                                                                                                                                                                                                                                |

**What ran and what did not.** Route CP (the recordings' checkpoints, §6) ran end to end on all
three recordings. Route A was not run: the only client here carries no server (§2a). Route B was
not run: the session's development policy refused building and executing third-party code, and
the engine needs the game's data file of its build (present in the Mac install as
`empires2_x2_p1.dat`, not opened: `docs/data-sources.md` §6's ruling is unchanged). Route D ran no
disassembler.

**Minimum setups that would unblock each route** (spec FR-008, one line each):

- **A**: a Windows 10/11 x64 machine with its own Steam copy and account, the game running a
  recording made on that client's build, and a lawful basis for the client credential (§9). Linux
  with Proton is UNKNOWN: ProtonDB rates the game Gold and one client targets Proton (Sources 41,
  5), while the Windows build's `WinVerifyTrust` check is reported to make it quit under unpatched
  Wine (Source 57); which holds for current Proton was not established.
- **B**: a build 158041 recording and that build's data file (the latter barred by
  `docs/data-sources.md` §6), plus permission to build and run the engine. No path to the project's
  builds exists until genie publishes a layer for them.
- **D**: a lawfully held Windows executable and Ghidra 12.1 with an arm64 JDK 21; static only.
- **The Mac install**: the dynamic check the static finding of §2a awaits: start the game, record
  any short game (a skirmish against the computer, a minute, with "Record Game" on), open it from
  the Replays screen, and while it plays run `lsof -nP -iTCP:4341 -sTCP:LISTEN`; an empty result
  confirms §2a. The committed fixtures cannot serve for this: a replay plays only on the build that
  recorded it (§3.8) and this client is build 188329 where they are 180059 and 185872.

**2a. What the installed macOS build contains (DEMONSTRATED, static, 2026-11-08).** The
executable's printable strings (98,944 at six characters and more; the reviewer re-ran at four and
found the same) and the six bundled frameworks (HttpClient, PlayFab Party, QuincyKit, Xal, xsapi-c,
`libsteam_api.dylib`) hold **no gRPC code**: zero matches for `grpc`, `CadeRemote`, `cade_api`,
`ca-game-api`, `cade-client`, `4341` and `application/grpc`. For comparison, CaptureAge's own
Electron client bundle carries all of these constants (§3.1), and the Windows game executable is
reported to embed gRPC 1.51.1 and to resolve `localhost svc=4341` at start-up (DOCUMENTED, a hobby
analysis of a cracked copy, Source 58). The only `CaptureAge` strings in the Mac binary are six
video subtitle style names; the only spectate-with-CaptureAge traces are three UI widget paths
(`ButtonSpectateCA`) and a `screenloadgame.json` reference in the UI definitions the Mac build
shares with the Windows one. Protobuf is present, in a Feral namespace, for Steam networking
messages only. `otool -L` lists Apple frameworks and PlayFab only. INFERRED, strongly: Feral's port
omits the CaptureAge server, consistent with the absence of any CaptureAge for macOS; the run-time
confirmation is the owner's check above. The binary also carries the version string
`101.103.57257.0 (#188329)`, 3,519 exported function symbols (third-party code; the game's own
functions are stripped) and 6,419 C++ RTTI type names, among them the complete command hierarchy
(`RGE_Command_*`, `TRIBE_Command_*`, including `TRIBE_Command_Cancel_Build`,
`TRIBE_Command_XsData`, `RGE_Command_Chapter`) and the object model. The commands behind these
counts are listed in the reverse-engineering document. The web sources' macOS 15.7 requirement
(Source 40) is contradicted by the bundle's own `LSMinimumSystemVersion` of 14.4 and by Steam
installing the game on this 15.1.1 host; whether it launches here was not observed.

**Corpus** (spec FR-009), the three committed recordings; checksums, sizes and operation counts are
in `tests/fixtures/replays/README.md`, event counts in the canonical goldens beside them:

| Recording | Build  | Players | Map id | Civilisation ids by slot | Duration | Scenarios covered by commands                                                         |
| --------- | ------ | ------- | ------ | ------------------------ | -------- | ------------------------------------------------------------------------------------- |
| 500546441 | 180059 | 1v1     | 9      | 1: 9, 2: 26              | 53:29    | economy, age-ups, buildings, military production, research, market, deletions, resign |
| 504695319 | 180059 | 2v2     | 73     | 1: 2, 2: 8, 3: 4, 4: 33  | 51:56    | the same, with four players and two teams                                             |
| 511523321 | 185872 | 1v1     | 216    | 1: 23, 2: 37             | 37:23    | the same, on the newer build, with the first chat on a channel other than 0           |

Combat, unit deaths, building destruction and technology cancellation are not observable as
commands and could only be validated through an engine route; no recording was added for them
because no engine route could run.

**Build situation, per interface** (spec FR-005, SC-006):

| Interface                             | Build 185872 (newest fixture)                                                             | Build 188329 (installed Mac client)        | Current Windows build                                                      |
| ------------------------------------- | ----------------------------------------------------------------------------------------- | ------------------------------------------ | -------------------------------------------------------------------------- |
| A, gRPC stream                        | UNKNOWN; the stream is build-agnostic in transport, the decoder model is per build (§3.8) | not present in the Mac client (§2a)        | UNKNOWN; last third-party decoder patches are for 177723 and 178524 (§3.8) |
| B, genie                              | not supported; only the data-file reader accepts it                                       | not supported                              | not supported; 158041 only                                                 |
| CP, recording checkpoints             | DEMONSTRATED (344 checkpoints)                                                            | UNKNOWN: no 188329 recording was read      | UNKNOWN                                                                    |
| CL, command log (`aoe2rec-py` 0.1.24) | DEMONSTRATED (006, 008)                                                                   | UNKNOWN until a 188329 recording is parsed | UNKNOWN                                                                    |
| 185872 still obtainable?              | UNKNOWN: the live Windows build was not verified; the Mac client is already 188329        |                                            |                                                                            |

**Constraints that bear on the routes** (spec FR-019), from the constitution and the governing
specs:

- **III, external data through providers.** A gRPC stream from a running game is an outbound
  connection and an external source: behind a provider in `packages/providers`, with fixtures and
  contract tests, never from `apps/*` or `packages/core`. The checkpoint reader opens no connection
  and is research code outside the application; constitution III does not apply to it.
- **V, parsing in an isolated, pluggable engine.** The checkpoints are in the recording but
  `aoe2rec-py` does not decode them; using them in the product means the engine interface grows (a
  second decoder beside the adapter, or a parser upgrade), behind the same Protocol.
- **XII, portable across the two hosting phases.** Nothing in either phase can run the game; an
  extraction host would be a third kind of machine, outside XII as written.
- **X, non-commercial, and the data-file ruling** (`docs/data-sources.md` §6): unchanged; genie's
  need for the data file is one reason B is not viable here.
- **IV, derived is recomputable from the raw.** A value from a running game can only be recomputed
  while a client of the recording's build exists; a value from the checkpoints always can.
- **Feature 008's governing requirements**: FR-003b (spending), FR-007a (completion demonstrated
  by absence of obstacles), FR-001a and FR-012 (population and idle time), gate G1.

## 3. Approach A: the game's gRPC interface (CaptureAge's route)

Every answer is from the research agent's sourced report, re-read here; URLs in Sources.

1. **What it is.** A gRPC server inside the Windows game process (`AoE2DE_s.exe`), service
   `cade_api.rpc.CadeRemote`, on `localhost:4341` (IPv4 and IPv6 loopback), HTTP/2 over TLS with
   mutual TLS. The game is the server; CaptureAge is the client. DEMONSTRATED by CaptureAge's own
   Electron worker bundle (constants `localhost:4341`, client stubs for twelve RPCs) and by three
   third-party clients that receive frames (Sources 1–6). LibreMatch's lobby and matchmaking work
   is unrelated.
2. **When it is active.** Replay playback (DEMONSTRATED: third-party capture scripts wait for the
   port "while a replay plays", and a 2021 replay capture is published); live spectating
   (DOCUMENTED: game update 50292); an editor scenario test (DOCUMENTED: a 2026 lab's tooling is
   written for it; its go/no-go result file is not published); a player's own live game only with
   cheats enabled (DOCUMENTED, CaptureAge docs). A normal ranked game from the player's own
   client: INFERRED not available. No enabling flag is documented; clients poll the port
   (INFERRED: always on in observable modes). Sources 5–9.
3. **Without CaptureAge.** Technically yes, DEMONSTRATED: three code bases connect with no
   CaptureAge process, all presenting the same three files, a certificate authority, a client
   certificate with CN `cade-client` and its private key, issued by `O=CaptureAge BV`, valid
   2020-11-13 to 2040-11-08. The key sits in the public `librematch/delta-play-replay`
   repository; another project says it extracted the files "from the local game install". There is
   no Steam ticket or token: the certificate is the authentication. Sources 3, 10–12. §9 has the
   legal reading.
4. **Playback control.** Current API (CaptureAge 1.11.0 bundle, DOCUMENTED by message
   definitions): `LoadGame` (a replay by file path, or a lobby to spectate), `Pause`,
   `SetGameSpeed`, `SetFogOfWar`, `SetPerspective`, `ChangeScreen`, `ChangeWindowState`, an
   `Oracle` stream that drives the game UI. **No seek RPC**: CaptureAge's rewind is client-side
   over buffered frames and the optional `reversePatch`. No command-line flag opens a replay
   (DOCUMENTED launch-option list). No headless or no-render mode; software and reference
   renderers and windowed mode exist; the window may be minimised while streaming. Sources 2, 13–16.
5. **What state is exposed.** Nothing is a named protobuf field: `Frame.patch` is an opaque
   stack-machine delta against a reverse-engineered object model (Source 17). DOCUMENTED, as
   definitions in that model: `World.entities` keyed by stable id; `Entity.owner_id`, `master_id`,
   `world_x/y/z`, `hp`, `state`; `BuildingEntity.build_pts`, `built`, `num_builders`,
   `production_queue`; `Player.research_states[tech]{research_done, state, times_researched}`;
   `PlayerAttributes` `food/wood/stone/gold` (f32), `population`, `max_pop`, `civilian_pop`,
   `military_pop`, `current_era`, cumulative totals, `kills`, `razings`, scores; `GameOptions` (48
   fields incl. `game_id`, `is_ranked`, `population_limit`, Steam ids, `dat_file_crc`). Events:
   `EntityKilled{id, killerId}`, `MarketTransaction`, `Tribute`, `PlayerChat`, and in the current
   API `Damage`, `MonkConversion`, `NotificationResearchDone`, `NotificationTrainDone`. Commands:
   the same intent stream the recording holds. DEMONSTRATED by others, decoding from live frames:
   hit points, owner, type, position, deaths (by hp reaching zero and removal, not by the event),
   production commands. **Cancellation has no event**: INFERRED from a research state reverting or
   a queue shrinking. **Gather rates are not direct**: differences of cumulative totals. The
   per-fact classification is the matrix.
6. **Snapshots and deltas; completeness.** The first patch after connecting is a full snapshot
   (0.4 to 5 MB), then deltas; reconnecting yields a fresh snapshot; `timeStepsSkipped` reports
   dropped steps; `metrics` name the regions covered. DEMONSTRATED by client code. A third-party
   decoder _skipped_ full snapshots "to avoid desync" and re-anchors with heuristics: what a decoder
   reads out is as exact as its model for that build, and no published measurement of that
   fidelity exists (UNKNOWN). Sources 18–19. **FR-015**: full snapshot on connect, deltas after,
   skipped steps reported but their content lost, recovery by reconnecting with a fresh snapshot,
   final state as the last frame; whether a client can lose events silently between frames is
   UNKNOWN beyond `timeStepsSkipped`.
7. **Time.** `Frame.time` is game time in milliseconds; CaptureAge requests 50 ms steps for
   high-priority state and 100, 500 and 1000 ms for lower categories; wall-clock rate follows
   `SetGameSpeed`. No wall-clock field. DOCUMENTED from the bundle's constants; no independent
   measurement. Sources 2, 20.
8. **Builds.** `Info()` returns `gameVersion` and `apiVersion`. The proto grew from 5 RPCs (May
   2021 snapshot) to 12 (June 2024). The binary model drifts with builds: the 2026 lab carries
   hand patches for game versions 177723 and 178524 and advises "after a game patch, re-validate
   with a fresh capture". CaptureAge ships a compatibility release after most game updates. The
   interface has existed since 2020, has never been removed, and has never been published by
   World's Edge as an API: it is a partner integration. **A replay plays only on the build that
   recorded it** (DOCUMENTED, forum; consistent with the recording being a command log). Sources
   13, 19, 21–24.
9. **Protos and clients.** Protos in `librematch/delta-play-replay` (AGPL-3.0-or-later for the
   repository; the protos carry no licence header and were recovered from CaptureAge's bundle, so
   that licence cannot cover them: INFERRED). Clients: `librematch/delta-play-replay` (Rust,
   dormant since 2024-09), `ddk220-light/aoe2_matchup` (Python, active 2026-11, no licence),
   `DeadMeme5441/aoe2-de-bridge` (Python probe, 2026-09, MIT). Sources 1, 4–6, 25.
10. **Platform.** Official: Windows 10/11 x64. Native macOS (Apple silicon) since 2026-05-28; no
    CaptureAge for macOS; the installed Mac build's images contain no gRPC code (§2a, static).
    Linux/Proton: UNKNOWN (§2). Windows on ARM under Parallels: one 2021 anecdote, unsupported by
    Microsoft. Rendering cannot be disabled. Sources 36–41, 57.
11. **Does it suffice to reconstruct a whole match** (FR-002)? By its documented content, yes for
    every fact in the matrix except cancellation (inferred) and gather rates (derived); by what is
    DEMONSTRATED, only for object identity, position, hit points and deaths. UNKNOWN until run.

**Verdict on A.** The only route to actual per-object state, documented in the Windows client,
partly demonstrated by others, not run by this project; legally and operationally unresolved (§9,
§10); absent from the Mac client by the static evidence.

## 4. Approach B: `librematch/genie`

From a read-only inspection of the source at commit `2cac47b3` (2026-11-07), obtained through the
GitHub API, nothing built or run; labels READ IN CODE, DOCUMENTED, ABSENT.

1. **What it is.** An import of `SiegeEngineers/genie-rs`'s format crates (2019 to 2022, GPL-3.0),
   plus a new engine, `crates/engine/genie-core`: 313,644 lines of Rust in 704 files written
   between 2026-10-15 and 2026-11-07 by one author; 1,553 of 1,603 commits since the import carry a
   Claude co-author trailer. 12 stars, 4 forks, issues disabled, no release.
2. **Does it load `.aoe2record`?** READ IN CODE for one build: the DE reader splits chapters,
   reads `VER 9.4`, minor, major and build; the world-save layout is "generated from build
   158041's load routines"; the corpus tests filter on build 158041 and skip unless a private
   corpus and the game's data file are supplied. Build 185872 appears once in the repository, as a
   `.dat` version the data-file reader accepts. DOCUMENTED: "genie cannot read the recordings of
   other builds yet". No `.aoe2record` fixture is in the repository.
3. **Is there a simulation?** Yes, READ IN CODE, and substantial: a 20-step tick schedule,
   pathfinding, movement, combat and damage, missiles, gathering, construction and repair,
   production queues, technology effects, garrison and transport, groups and formations, unit AI,
   vision, players' history and victory; determinism ports of the game's `f32` math, random
   streams, sort and float-to-int conversion. Replay-driven: the header's world save is loaded, each
   command packet decoded, `World::tick_with(dt, &commands)` advances state per sync; `genie-oracle`
   compares the engine's per-player 11-word checkpoint with the one the recording stores (the same
   block §6 reads).
4. **Coverage.** 679 `unsupported` call sites with 236 distinct reasons (READ IN CODE); when a
   player hits one, its objects freeze for the rest of the replay. Monk conversion is not ported;
   computer players' behaviour is not run; cheats, siege pack and unpack, several transport and
   trade-cart states are unsupported; any command packet that does not re-encode byte-identically
   stops its player. DOCUMENTED: the project's own census output shows players stopping between
   updates 1154 and 1759 of a recording.
5. **State and events.** `World` fields are public (players' attribute arrays, objects with
   master, state, hit points; research states; history). No serde on `World`, no snapshot or event
   CLI, no facade crate (the one the docs name does not exist); `tracing` events exist. ABSENT: the
   gRPC/CaptureAge bridge the README describes.
6. **Headless.** READ IN CODE: no filesystem, network or clock calls in the core; no renderer
   crate; CI builds the engine for WebAssembly.
7. **Data it needs.** The recording of the same build **and the game's data file of the same
   build** with two JSON tables beside it. Not redistributed by genie; not extractable by this
   project under `docs/data-sources.md` §6.
8. **Performance.** UNKNOWN: nothing was run and the repository publishes no timing.
9. **Supporting 185872.** Regenerate the save layout, the command-packet layouts and the build
   layer from the 185872 executable with a reverse-engineering pipeline that is not in the
   repository; re-port every routine the game changed; validate against a 185872 corpus with its
   data file. Each game update repeats this. Without the pipeline, a downstream project can only
   wait for the single maintainer.
10. **Licence.** Engine and tools AGPL-3.0-only; format crates GPL-3.0. Linking the engine into a
    server-side analyser makes a combined work under AGPL §13; running it as a separate process is
    the usual isolation. Provenance: every port cites a routine address in the game's executable;
    not clean-room; a dependent project inherits the exposure (§9).

**Verdict on B.** The only reimplementation with real DE replay simulation, and today it cannot
replay a build 185872 recording, is documented not to replay its own build to completion for every
player, needs the game's data file, and is maintained by one person through unpublished tooling.
Not viable as a dependency today; revisit if it publishes a current build layer, a stable facade
and a corpus-backed CI. Also checked: `SiegeEngineers/genie-rs` (format readers, last commit
2022-11, no simulation) and `SFTtech/openage` (README: gameplay "basically non-functional", no
binary compatibility, no recorded-game support). Sources 26–30.

## 5. Approach C: other routes

1. **CaptureAge itself.** No export, API, file output, scripting hook, overlay data feed, CLI or
   developer programme anywhere in its docs, FAQ, tier lists or the publisher's announcements
   (DOCUMENTED absence). It opens replays and, in the paid tier, saves a proprietary `.caderec`
   that plays without the game at up to 8x; no reader for it is documented. In-game replay speed
   tops out at 4x; CaptureAge's 8x is its own playback; the game simulates on one core and slows
   under load. Sources 31–34.
2. **Open-source engines.** openage (gameplay non-functional, no binary compatibility), freeaoe
   (AoC/HD assets, early), OpenAOE (dead): none runs a DE recording. DOCUMENTED.
3. **In-game XS scripting.** Since update 42848 (2020) XS can read unit hit points, positions,
   owners, object counts, technology states, resources and game time and write `.xsdat` files
   (DOCUMENTED function reference). The script comes from the map's random-map script or scenario,
   which a ranked replay fixes by identifier; changing it changes the simulation and desyncs the
   replay (INFERRED from documented out-of-sync behaviour). Viable only for maps one controls;
   useless for third-party ranked recordings.
4. **Playback automation.** No documented command-line argument opens a replay; `aoe2de://` joins a
   lobby for live spectating; two third-party "one-click replay" tools do not disclose their
   mechanism; no headless, server or no-graphics mode in any source. Hardware: DirectX 11, 2 GB
   VRAM minimum; no source shows the game on a GPU-less server (UNKNOWN). Sources 35, 42–43.
5. **Off Windows.** Native macOS build 2026-05-28 (Apple silicon; no cross-play with Windows;
   replay compatibility with Windows recordings UNKNOWN; no gRPC code, §2a); Proton UNKNOWN (§2);
   Parallels on Apple silicon "playable" from one 2021 report; CrossOver "playable". Sources
   36–41, 56–57.
6. **A Windows extraction machine.** Indicative, third-party trackers, 2026-11: Windows VPS
   without GPU EUR 10 to 40 per month; with a small GPU USD 520 to 640 per month on demand (AWS
   g4dn.xlarge, Azure NV A10 v5), Paperspace USD 0.51 per hour, Shadow PC EUR 19 to 50 per month;
   a used mini PC USD 110 to 250 once. Steam: one account plays on one machine at a time, sharing
   credentials is banned, use is "personal, non-commercial", scripts and bots are banned, so a
   dedicated machine needs its own purchased copy and account. Sources 44–48.
7. **Memory reading and injection.** Bartender reports DE "crashes as soon as you attach the
   debugger"; AoE2Control injects a DLL and exposes Lua facts for single player only, unlicensed;
   pyage2 targets the old engine; DE closes when "a running process may be interfering". Nothing
   maintained reads DE state in replay mode, and the spec forbids building such a thing (FR-001a).
   Sources 49–51.

**Verdict on C.** Outside the gRPC interface there is no documented or demonstrated route to actual
simulated state from a third-party ranked DE recording.

## 6. What the recording itself proves: the game's state checkpoints (DEMONSTRATED)

Found while reading genie's recording reader and verified here on all three fixtures with
`scripts/research/009-native-simulation/checkpoints.py` (standard library only; eighteen tests,
`uv run pytest -q scripts/research/009-native-simulation/tests`, hold every number below).

**The fact.** Every 500 syncs (the pregame record's `checksum_interval`, 500 on all three
recordings) the game appends to the sync operation eight lanes of eleven 32-bit words and a world
time. Each lane is one lobby slot; unused lanes are zero. The words are sums and counts the
simulation computes from its live state at that instant. Their published semantics (genie
`world/checkpoint.rs`): word 0 sleeping objects, word 1 the four resource stocks summed after
truncation, word 2 sum of master ids, word 3 sum of object states, word 4 sum of amounts held, word
5 always 0, word 6 live object count, word 7 sum of positions times 100, word 8 player id, word 9
action terms, word 10 sum of object ids. `aoe2rec-py` 0.1.24 exposes the block as an opaque
`checksum` of five mislabelled fields and does not decode the rest; `aoc-mgz` treats it as padding.

**Measured** (the test file holds the exact values):

| Recording | Checkpoints | Game time between checkpoints                                       | Players' first checkpoint, world time, word 1 |
| --------- | ----------- | ------------------------------------------------------------------- | --------------------------------------------- |
| 500546441 | 473         | 6.5 s for 411 of 472 gaps; 61 longer, 43 above 7 s, longest 12.04 s | 8.684 s: 500 and 508                          |
| 504695319 | 226         | 6.5 s to 15.32 s, median 14.0 s                                     | 9.349 s: 450, 500, 450, 450                   |
| 511523321 | 344         | 6.5 s, every gap                                                    | 8.684 s: 550 and 650                          |

The spacing is 500 syncs exactly on every recording (tested on all three); the game time it spans
varies because a sync's length varies with the match.

**What is corroborated, and how** (the FR-010 record for the resources scenario, pinned by
`test_word_1_is_the_starting_stocks_minus_the_costs_queued_before_the_first_checkpoint`):

- _Expected_: each player's four starting stocks read from the header anchor feature 006 settled
  (`docs/data-sources.md` §2; 700 for six players, 800 for the two whose civilisation starts with
  more), minus 50 food per villager queued and 25 wood per house placed before the first
  checkpoint's world time, from the canonical goldens.
- _Extracted_: word 1 of that player's first checkpoint. _Source_: `ENGINE_STATE`, written by the
  game into the recording. _Timestamp_: the checkpoint's `world_time_ms`.
- _Verdict_: **exact for seven of eight players**. The eighth (500546441, slot 2) reads 508 where
  the expectation is 475; it placed three houses and deleted one object before 8.7 s and the
  difference is unexplained (a refund or a civilisation effect are candidates, INFERRED, untested).
  After the first checkpoint the sums move in multiples of 10 consistent with drop-offs (observed,
  not pinned).
- _Falsifiers_: any pre-income checkpoint where word 1 differs from the header's stocks minus the
  debited costs; a market transaction that does not move the sum by exactly what was bought minus
  what was paid; a tribute that does not move the giver by the amount plus tax and the receiver by
  the amount.
- Word 8 is corroborated too: it equals the lane number plus one on every checkpoint of every
  recording.

**What is not corroborated.** Word 0 is zero on every lane sample and cannot be verified. **Word 6
is not a creation-minus-death counter**: it decreases three times before any combat is possible
(511523321 slot 2 between 28.2 s and 34.7 s, 504695319 slot 4 between 35.3 s and 41.8 s, 504695319
slot 1 between 91.0 s and 105.0 s), and its first values (12 to 15 in the 1v1s, 100 to 105 in the
2v2 at 9 s) are unexplained, so what it counts is UNKNOWN; the matrix therefore treats it as
unavailable. Words 2, 3, 4, 7, 9 and 10 are carried as published, unverified. A falsifier for
word 6 would be its first value against the count of the player's objects in the header's world
save, which genie's first-checkpoint oracle computes and this project did not.

**Determinism** (spec FR-013, SC-005): **not tested**. The block is produced by the game's
simulation during the recorded match; nothing here re-simulates anything. The reader's own output is
stable (a property of the reader, tested as such), which is not replay determinism.

**Time bases** (spec FR-014): each observation carries both the block's own `world_time_ms` and
`clock_ms`, the sum of sync increments before the checkpoint's sync; they differ by that sync's own
increment on all 1,043 checkpoints (tested). Feature 008's clock is the sum of increments.

**Provenance** (spec FR-012): every word is `ENGINE_STATE`, sampled by the game and stored in the
recording, exact as an integer. Any fact derived from a word is `INFERRED` or, where it follows
arithmetically, `DETERMINISTIC_DERIVATION`: a resource spend between two checkpoints is the sum's
drop plus the income in between, as one number; a death or a creation cannot be read from it.

**What it changes.** Feature 006's finding "replays carry intent, never outcomes" becomes "replays
carry intent, no per-object outcomes, and a per-player state sample every 500 syncs". For feature
008 it supplies, from the raw file alone and for the builds read, one exact anchor its spending
reconstruction lacked: at every checkpoint the sum of the four stocks is known, so cumulative
spending plus income is pinned every 6.5 to 15 s. It supplies nothing for population. It is also
the correctness oracle genie uses, which says how weak it is as a full-state check.

## 7. Validation scenarios (spec FR-010, SC-003)

| Scenario              | Route that could validate it | Status on 2026-11-08       | Evidence                                                                                                |
| --------------------- | ---------------------------- | -------------------------- | ------------------------------------------------------------------------------------------------------- |
| Unit creation         | A                            | not run                    | A: entity insertion in the patch (documented). Checkpoints: no (word 6 is not a creation counter)       |
| Unit death            | A                            | not run                    | A: hp reaching zero and removal (demonstrated by others), `EntityKilled` (documented). Checkpoints: no  |
| Building construction | A                            | not run                    | A: `build_pts`, `built`, `num_builders` (documented). Command log: placement only                       |
| Building destruction  | A                            | not run                    | A: removal, `razings` (documented)                                                                      |
| Technology research   | A                            | not run                    | A: `research_states`, `NotificationResearchDone` (documented); cancel inferred on every route           |
| Population            | A                            | not run                    | A: `population`, `max_pop` (documented). Checkpoints: no                                                |
| Resources             | A, checkpoints               | **checkpoints: validated** | word 1 equals starting stocks minus debited costs on 7 of 8 players, exact (§6, tested); A documented   |
| Resource gathering    | A                            | not run                    | A: cumulative totals differenced (derived). Checkpoints: income minus spend as one number               |
| Production queues     | A                            | not run                    | A: `production_queue` (documented)                                                                      |
| Age advancement       | A, command log               | command-log bound (008)    | A: `current_era` (documented). Command log: click and first age-gated order, a two-sided bound (008 R3) |

Validated experimentally here: **one** scenario (resources, as the sum of the four stocks). The
other nine depend on route A and were not run. **SC-003 (five scenarios) is not met** by this
spike; the matrix says so row by row.

## 8. Architecture assessment (spec FR-016, FR-017)

The brief's pipeline, replay execution adapter → extraction layer → normalised state and event
model → persisted match data → deterministic analysis → coaching metrics, is evaluated, not adopted.
Everything in this section about route A is INFERRED from §3; nothing was measured.

- **Replay execution adapter.** Only A exists to adapt to. Lifecycle per replay: `LoadGame` by
  file path on a Windows host where the game of the recording's build is running and signed in,
  `SetGameSpeed` to the maximum the game allows in replay (4x, §5.1), `SetFogOfWar(false)`,
  stream `Frames` until the game ends, decode the snapshot and deltas against a per-build model,
  detect the clock reset for the next game. Error handling: reconnect yields a fresh snapshot;
  desync between decoder and model is the known failure and is detected only heuristically. Retry:
  replay again from the start, no seek.
- **Version compatibility.** Two couplings: the replay to its build (the client must be on it;
  with frequent patches a recording older than the current patch cannot be replayed by a current
  client unless old builds are kept installed) and the decoder to the build's object model.
  CaptureAge's `.caderec` exists because of exactly this.
- **Throughput.** Game time runs at 1.7x real time at normal speed and at most 4x in replay, on one
  core, slower on large games: a 50-minute match takes at least 12 minutes and plausibly 30 of a
  machine that renders a window (INFERRED from §5.1). Parallelism is one game instance per Steam
  account and machine.
- **Storage.** A snapshot is 0.4 to 5 MB (DEMONSTRATED by client code); the size of a full delta
  stream over a match is UNKNOWN (no published figure); a normalised event stream would be far
  smaller. The raw stream would be the irrecoverable artifact once the replay can no longer be
  re-run, so constitution III's verbatim-persistence rule would apply to it.
- **Hosting.** Nothing in either hosting phase can run the game. An extraction host is a third kind
  of machine with a display, a Steam account and the Windows game: a Windows VM with a GPU (USD 520
  to 640 per month on demand, §5.6) or a physical machine at the owner's. It is outside constitution
  XII as written and would need an amendment naming it as an optional, non-required instrument.
- **Security and isolation.** The host holds a Steam session and a credential that is not ours; it
  must never be reachable from the application, and its output enters the system as a provider's
  data (constitution III) with the fixtures-and-contract-tests discipline of every other source.
- **Independence from the provider.** A normalised model (object lifecycle, research lifecycle,
  stocks, population, events) keeps the analysis independent of A, B or the checkpoints; the
  recording's checkpoints feed the same model today, for the one quantity they carry.

## 9. Licensing and terms (spec FR-018)

This section states what the texts say; it is not legal advice. Technical risks are in §10.

| Dependency or act                                  | Licence or term                                                                                                                                                                                           | What it means here                                                                                                                         |
| -------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| Connecting to `:4341` with CaptureAge's client key | CaptureAge Terms: no reverse engineering, no working around technical limitations, no making the application available to third parties                                                                   | The credential is CaptureAge BV's; presenting it is the central exposure. Sanctioned path: an agreement with CaptureAge BV or World's Edge |
| Automating the game client                         | Steam Subscriber Agreement §2.G (reverse engineering, emulating or redirecting protocols, with an applicable-law carve-out), §4.B, §4.C (scripts, bots); Microsoft Services Agreement §8.b.ii, §14.a.viii | Replaying one's own recordings is not cheating, but driving the client programmatically sits inside these clauses                          |
| Microsoft Game Content Usage Rules                 | Non-commercial only; no reverse engineering "to access the assets"                                                                                                                                        | Constitution X's anchor; a commercial extraction service is excluded                                                                       |
| `librematch/genie`                                 | AGPL-3.0-only engine, GPL-3.0 formats; ported from decompiled routines                                                                                                                                    | AGPL §13 on a linked server; takedown exposure inherited; not clean-room                                                                   |
| `librematch/delta-play-replay` protos and bundle   | Repository AGPL-3.0-or-later; protos and the redistributed CaptureAge bundle and key are not the repository's to license                                                                                  | The protos are usable as documentation of a wire format; nothing else from it may be copied                                                |
| The game's data file (needed by B)                 | Rejected by `docs/data-sources.md` §6 for three independent reasons                                                                                                                                       | Unchanged by this spike                                                                                                                    |
| EU law on decompilation                            | Directive 2009/24/EC Art. 5(3), 6, 8; CJEU C-13/20                                                                                                                                                        | Observation and interoperability decompilation are preserved against contrary terms, under conditions; see the REA document                |

No game asset, executable, data file, certificate or key was copied into this repository.

## 10. Operational requirements and technical risks

An engine-backed pipeline needs: a Windows machine with the game installed and signed in, on the
build of each recording it processes, with a display, running one replay at a time at up to 4x
game speed; a per-build object-model maintenance task after every game update; a lawful basis for
the client credential; and an amended constitution (III: the stream is an external source behind
a provider; XII: the host is outside both hosting phases). A checkpoint-anchored command-log
pipeline needs none of these: it reads the raw file this project already holds, for the builds
read, in milliseconds; it needs the engine interface to grow by one decoder (constitution V).

Technical risks, separately from the legal ones of §9:

| Risk                                                          | Route | Severity | Evidence                                 |
| ------------------------------------------------------------- | ----- | -------- | ---------------------------------------- |
| Decoder desynchronises from the per-build model after a patch | A     | high     | third-party decoders' hand patches, §3.8 |
| A recording older than the current patch cannot be replayed   | A     | high     | §3.8                                     |
| Dropped frames (`timeStepsSkipped`) lose state silently       | A     | medium   | §3.6, UNKNOWN extent                     |
| Interface changed or removed by the publisher                 | A     | medium   | never published as an API, §3.8          |
| Engine at the wrong build, single maintainer, private tooling | B     | high     | §4                                       |
| Checkpoints absent or changed on a newer build                | CP    | medium   | 188329 not read, §2                      |
| Word semantics beyond words 1 and 8 misread                   | CP    | medium   | §6, only two words corroborated          |

## 11. Recommendation and decision (spec FR-022)

Two letter lists exist in this feature: FR-001's approach letters (A gRPC, B genie, C other routes,
D REA) and FR-022's recommendation letters (A official engine through gRPC, B genie, C hybrid, D
command-based reconstruction for limited use cases, E none viable). This section uses the
recommendation letters.

**Recommendation: C, hybrid**, stated as the framing choice it is. What ships is recommendation D,
command-log reconstruction for explicitly limited use cases, plus one engine-written anchor the
recording itself carries (§6). It is called hybrid because that anchor is the simulation's own
output, not an inference; if the owner prefers to call it D with a new anchor, nothing else in this
section changes.

**Decision: CONDITIONAL GO**, split in two:

- **GO now**, no condition: publish command-log values anchored and bounded by the recordings'
  checkpoints. The checkpoints are exact, recomputable from the raw file (constitution IV), need no
  game install and no credential. Their one corroborated quantity is the sum of the four stocks
  every 500 syncs; feature 008 uses it as the oracle of its gate G1 and as a bound on FR-003b's
  spending, and uses nothing from them for population (FR-001a, FR-012), which stays as 008 left it.
- **Conditional**: route A as an owner-run instrument for validation and calibration, never a
  dependency of the deployed product, only once all of the following hold:
  1. **A lawful credential** (§9): an agreement with CaptureAge BV or World's Edge for access to
     the interface, or the owner's recorded decision to accept the exposure for a private,
     non-commercial, owner-operated instrument. The repository never holds the key.
  2. **The owner's experiments** (§2): first the one-minute check on the installed Mac build (the
     static reading predicts an empty result); then, on a Windows host with its own Steam copy,
     whether `:4341` answers during replay playback, whether a recording made on that client's
     build streams, and whether resources, population, deaths and research completion can be
     decoded for one match and compared with the checkpoints of §6 and with CaptureAge's display.
     This is the demonstration SC-001, SC-002, SC-003 and SC-005 still lack.
  3. **A per-build model plan** (§3.8, §10): who re-validates the decoder after each game update,
     and what the product shows for a recording whose build the instrument can no longer replay.
  4. **Constitution amendments** for III and XII (§2, §8) and the processing-register entry for the
     instrument's host, before anything it produces is published.
  5. **Product honesty**: the site states that it shows what a player ordered, what the recording
     proves and the game's own checkpoints, and never claims the per-object exactness of a tool
     that runs the game, unless and until the instrument is in place.

Route B: not viable as a dependency today (§4); revisit on the three triggers named there. Approach
D of FR-001 (REA): no further work for state access (its document).

**For feature 008** (spec FR-020, SC-010), without this spike amending it: the checkpoints are a
new tier-A fact to decode behind the engine Protocol (constitution V) and the exact oracle its gate
G1 lacked for the sum of stocks (FR-003b); FR-007a's completion discipline is unchanged; FR-001a and
FR-012 (population, idle time) gain nothing from them and keep their open method; the owner's rule
of one exact value per datum is unaffected for what the log proves, and the deductive rules remain
deductions.

**Owner's decision, 2026-11-10.** The spike closes in this state.

- Route A, the conditional half, is on hold: the owner is waiting for information from the CaptureAge team. A follow-up spike will be specified when it arrives; no work on route A happens before then.
- The GO-now half is not adopted on its own here. It goes to feature 008, where D-CONTROL-1 is re-derived in the light of this report's findings before it is put to the owner again (008 plan, Complexity Tracking).
- §13's second review pass is not awaited.

## 12. Remaining unknowns

- Whether the macOS native build serves `:4341` at run time (its images carry no gRPC code; the
  owner's dynamic check is pending), whether it launches on this macOS 15.1.1 host, and whether it
  plays recordings made on Windows.
- The live Windows game build on 2026-11-08 and whether build 185872 is still obtainable; the
  installed Mac build is 188329.
- Whether build 188329 recordings still carry the checkpoints (none was read).
- The fidelity of any route A field beyond hit points, owner, type, position and deaths, on any
  build; A's compatibility with 185872 and with the current Windows build; the exact semantics of
  `AccessFlag` and of the `Oracle` stream; whether the Windows executable embeds the `CadeRemote`
  descriptor and pins CaptureAge's root.
- Whether the interface can be used lawfully by anyone other than CaptureAge BV without an
  agreement; whether the game runs under current Proton given `WinVerifyTrust`.
- Genie's actual behaviour on any recording, and real extraction throughput on any route (nothing
  was run).
- What checkpoint word 6 counts and what word 0 means; why 500546441 slot 2's first sum is 508.

## 13. Independent review

Reviewed 2026-11-08 by the repository's `reviewer` agent (read-only), against the spec's success
criteria, the raw research reports, the fixtures and the installed binary (spec FR-021, SC-008).

**First pass: REJECT**, twenty-three findings. Verified correct: the checkpoint counts, builds,
interval, sync and command counts, the 500-sync spacing on all three recordings, the first and
last values of all eight players, word 5 always zero, word 8 equal to lane plus one, the time-base
relation on every checkpoint, the word semantics against genie's source, the Mac binary's size,
signature, version string, symbol counts and the absence of gRPC strings (re-run with a stricter
`strings` setting), and §3, §4 and §9 against the raw reports. Downgraded or corrected in this
version, in the reviewer's words where short: route A cells "demonstrated by others" where only
model or proto _definitions_ exist (now DOCUMENTED, with "exact" replaced by fidelity UNKNOWN);
the matrix's missing provenance and inferred counts labelled `ENGINE_STATE` (now one class and one
provenance per cell, derived facts `INFERRED` or `DETERMINISTIC_DERIVATION`); the "two partially
validated" scenarios, falsified by three pre-combat decreases of word 6 (withdrawn; now a test);
the word-1 corroboration, which used a 700 starting stock for every player and a sheep-income
residue where the header gives 800 to two players and no income arrives before 54 s (replaced by
the exact 7-of-8 reconciliation, now a test); the decision text, which gated the deployed product on
conditions meant for an instrument (now split into GO now and conditional); "determinism" claimed
from reading bytes twice (now stated as not tested); the 1v1 gap statistics, the "13 ms steps", the
reader's line count, the "12 to 489" range and the "the test pins these" header (corrected or
removed, the statistics now pinned); route B's "NO-GO" wording and missing minimum setup; the
reverse-engineering document's "No" and its unlabelled inferences; §2a's comparison baseline (the
Electron client, not the Windows executable); the missing per-interface build table, FR-019
constraint list and technical-risk table; the 8x throughput and the unsourced storage figure; the
Proton assumption; the "projectiles and dopplegangers" gloss on word 6; the docstring's licence for
genie's engine crate (AGPL-3.0-only); the duplicated 006 and 008 figures (now cited, not copied);
and the formatter's unrelated re-padding of two `data-sources.md` tables (reverted).

**Second pass**: not run. The owner closed the spike on 2026-11-10 in the state the first pass left it (§11).

## Sources

1. librematch wiki, gRPC: https://librematch.github.io/wiki/grpc/index.html and
   https://librematch.github.io/wiki/grpc/main.html
2. CaptureAge worker bundle redistributed in librematch/delta-play-replay (constants extracted):
   https://raw.githubusercontent.com/librematch/delta-play-replay/main/crates/uncage-model/docs/electronWorkerThread.js
3. librematch/delta-play-replay client and certificates:
   https://raw.githubusercontent.com/librematch/delta-play-replay/main/crates/uncage-client/src/lib.rs ,
   https://raw.githubusercontent.com/librematch/delta-play-replay/main/crates/uncage-client/cert/cade-client.pem
4. ddk220-light/aoe2_matchup: https://github.com/ddk220-light/aoe2_matchup (lab/info_test.py,
   lab/capture_state.py, lab/capture_session.py, aoe2x/grpc/README.md, lab/patch_decode.py,
   aoe2x/grpc/decode_state_v2.py)
5. DeadMeme5441/aoe2-de-bridge: https://github.com/DeadMeme5441/aoe2-de-bridge (observer_probe.py)
6. librematch organisation: https://github.com/librematch
7. Game update 50292: https://www.ageofempires.com/news/aoe2de-update-50292/
8. CaptureAge docs overview and recordings: https://captureage.com/cade/docs/cade-latest/overview ,
   https://captureage.com/cade/docs/cade-latest/caderecs
9. ddk220-light lab validation and recorder: lab/_validate_capture.py, aoe2x/grpc/grpc_hp_log.py in
   Source 4
10. aoe2_matchup gRPC README (certificates "extracted from the local game install"): in Source 4
11. aoe2-de-bridge ("No credentials are included"): Source 5
12. librematch/delta-play-replay repository: https://github.com/librematch/delta-play-replay
13. cade_api.proto (May 2021 snapshot):
    https://raw.githubusercontent.com/librematch/delta-play-replay/main/crates/uncage-client/proto/cade_api.proto
14. CaptureAge time controls: https://captureage.com/cade/docs/cade-latest/time-controls
15. CaptureAge updates (1.4.0, 1.4.8, 1.19.0, 1.26.0): https://captureage.com/cade/updates
16. Launch options: https://librematch.github.io/wiki/aoe2de/launch.html
17. Object model: https://raw.githubusercontent.com/librematch/delta-play-replay/main/crates/uncage/src/model.rs
18. Delta format: https://librematch.github.io/wiki/grpc/delta_format.html
19. aoe2_matchup redecode and decoder heuristics: aoe2x/grpc/redecode_hp.py, decode_state_v2.py in
    Source 4
20. Frame cadence constants: Source 2
21. Minor update 155976:
    https://www.ageofempires.com/news/age-of-empires-ii-definitive-edition-minor-update-155976/
22. World's Edge and CaptureAge partnership: https://www.ageofempires.com/news/we-and-ca-partnership/
23. Replays play only on their build (forum):
    https://forums.ageofempires.com/t/make-aoe-ii-de-recs-compatible-with-previous-patches/91398
24. librematch wiki commits (gRPC section written 2026-02-15):
    https://api.github.com/repos/librematch/wiki/commits?path=src/grpc
25. AoE2Control: https://github.com/aoe2control/AoE2Control
26. librematch/genie: https://github.com/librematch/genie (commit 2cac47b3f1d1ad2b1e63156e11df38aff95d5418;
    files cited: crates/formats/genie-rec/src/de/body.rs, crates/formats/genie-save/src/lib.rs,
    crates/engine/genie-core/src/world/checkpoint.rs, docs/DEBUGGING.md, docs/ENGINE_SYSTEMS.md,
    NOTICE, LICENSE-AGPL-3.0, LICENSE-GPL-3.0)
27. genie data-file test naming build 185872: crates/formats/genie-dat/tests/de.rs in Source 26
28. genie command codec: crates/engine/genie-command-codec/src/decode.rs in Source 26
29. SiegeEngineers/genie-rs: https://github.com/SiegeEngineers/genie-rs
30. SFTtech/openage: https://github.com/SFTtech/openage
31. CaptureAge spectate and docs index: https://captureage.com/spectate ,
    https://captureage.com/cade/docs/cade-latest
32. CaptureAge FAQ and tiers: https://captureage.com/cade/docs/cade-latest/faq
33. CaptureAge terms: https://captureage.com/terms
34. Single-core simulation note (second-hand, Nolt thread 172 unreachable)
35. SiegeEngineers/aoc-docker (old engine, Wine and Xvfb): https://github.com/SiegeEngineers/aoc-docker
36. Age of Empires II: DE on Mac (publisher):
    https://www.ageofempires.com/news/age-of-empires-ii-definitive-edition-available-now-on-mac/
37. Feral Interactive release note:
    https://www.feralinteractive.com/en/news/real-time-royalty-age-of-empire-ii-definitive-edition-is-out-now-on-macos-/
38. 9to5Mac, 2026-05-28: https://9to5mac.com/2026/05/28/age-of-empires-ii-definitive-edition-now-available-for-macos/
39. CaptureAge on CrossOver (lost connection): https://www.codeweavers.com/compatibility/crossover/captureage-190
40. Mac requirements as reported (macOS 15.7, Apple silicon):
    https://www.neowin.net/forum/topic/1466813-age-of-empires-ii-definitive-edition-is-now-available-on-macos/
41. ProtonDB summary API: https://www.protondb.com/api/v1/reports/summaries/813780.json
42. URL scheme for spectating (forum):
    https://forums.ageofempires.com/t/url-scheme-to-launch-the-game-and-spectate-a-match/88216
43. Linux spectating guide: https://gist.github.com/michaeljcaboose/8e285c8afbbf2bec13203d1453aae69b
44. AWS EC2 Windows pricing (g4dn): https://aws.amazon.com/ec2/pricing/on-demand/
45. Azure NV A10 v5 pricing: https://azure.microsoft.com/en-us/pricing/details/virtual-machines/windows/
46. Paperspace pricing: https://www.paperspace.com/pricing
47. Shadow PC pricing: https://shadow.tech/
48. Steam Subscriber Agreement: https://store.steampowered.com/subscriber_agreement/
49. Bartender (debugger crash report): https://github.com/dkrahn/bartender
50. pyage2: https://github.com/sandsmark/pyage2
51. AoE2 DE anti-tamper message (forum reports, several threads, 2021 to 2025)
52. Microsoft Services Agreement: https://www.microsoft.com/en-us/servicesagreement
53. Microsoft Game Content Usage Rules: https://www.xbox.com/en-US/developers/rules
54. XS scripting reference: https://ugc.aoe2.rocks/general/xs/functions/functions/
55. Game update 42848 (XS scripting): https://www.ageofempires.com/news/aoeiide-update-42848/
56. AppleGamingWiki (Parallels report):
    https://www.applegamingwiki.com/wiki/Age_of_Empires_II:_Definitive_Edition
57. Wine bug 55165 (`WinVerifyTrust`):
    https://list.winehq.org/hyperkitty/list/wine-bugs@list.winehq.org/message/NZPAMF6YB2ROVVOMCVOAG37BNNFB5R4W/
58. bijoymuzid/AoE2DE-LAN (gRPC 1.51.1 and `localhost svc=4341` in the Windows executable; a
    cracked copy, not a lawful-copy precedent): https://github.com/bijoymuzid/AoE2DE-LAN
