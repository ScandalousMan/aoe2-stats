# Native AoE2 DE simulation extraction: feasibility report

- **Feature**: 009 (`specs/009-native-simulation-feasibility/spec.md`)
- **Assessed**: 2026-11-08, on the three committed reference recordings (builds 180059 and 185872)
- **Status**: findings recorded; independent review in the last section
- **Companion documents**: the capability matrix
  (`docs/research/native-simulation-capability-matrix.md`), the reverse-engineering assessment
  (`docs/research/native-engine-reverse-engineering.md`), the prototype
  (`scripts/research/009-native-simulation/`)

This document records measured and sourced properties of things outside this repository: the game,
its interfaces, third-party engines and tools. Like `docs/data-sources.md`, it is dated, and a
claim here is either tied to an experiment in this repository or to a source. Labels follow the
spec: **DEMONSTRATED** (run here, or shown working in cited code or a cited recording),
**DOCUMENTED** (a source says so), **INFERRED** (reasoning, stated as such), **UNKNOWN**.

## 1. Executive summary

The question (spec §"What this feature is"): CaptureAge states exactly which building fell, which
technology finished, which unit died and what the population was; can this project reach the same
simulation instead of deducing from the command log?

1. **A `.aoe2record` is a command log plus a header, and the game rebuilds the match by running its
   own simulation over it.** Every exact per-object outcome CaptureAge shows exists only inside a
   running copy of the game, or inside a bit-exact reimplementation of it. Both routes were
   investigated. Neither can be run by this project today without a cost it has not yet accepted.
2. **Approach A, the game's own gRPC server, is real and is how CaptureAge works** (DEMONSTRATED by
   CaptureAge's own bundled client and three third-party clients, §3). The game process serves
   `localhost:4341` over mutual TLS while a replay plays or a match is spectated. It streams a full
   state snapshot then deltas at 50 ms of game time: every object with id, owner, type, position
   and hit points, construction progress, production queues, research states, resource stocks,
   population, age, kills and razings, plus events (`EntityKilled`, `Damage`, research and training
   done). It is the only route to actual per-object state. Three things stand in the way: the
   client certificate is CaptureAge BV's credential, not ours; the state is an opaque binary patch
   against a reverse-engineered, build-specific object model that third parties resynchronise with
   heuristics; and it needs the game running, which needs a Windows or Proton host, or possibly
   the native macOS build released 2026-05-28 (whether that build serves the port is UNKNOWN).
3. **Approach B, `librematch/genie`, is a genuine deterministic engine port** (313,644 lines of
   Rust, READ IN CODE, §4) but it targets exactly one game build, 158041, cannot read a build
   185872 recording, stops a player's objects at the first of 236 unsupported situations, has one
   maintainer, is AGPL-3.0 and is ported from the game's decompiled routines. It is a watch item,
   not a dependency.
4. **Approach C found nothing else** (§5): CaptureAge exposes no export or API; no open-source
   engine runs a DE recording; in-game XS scripting cannot be attached to a third-party ranked
   replay without changing the simulation; memory readers are unmaintained and the game closes when
   a process interferes; the only headless replay pipeline ever demonstrated is for the 2013-era
   engine under Wine.
5. **Approach D, reverse engineering with REA, could not run**: no binary of the game exists on the
   development machine (§2). What published evidence says about it is in
   `docs/research/native-engine-reverse-engineering.md`.
6. **One new fact was measured here (DEMONSTRATED, §6): every recording carries the game's own
   state checkpoints.** Every 500 syncs the simulation writes, for each player, eleven 32-bit sums
   and counts, among them the four resource stocks summed and the number of live objects. All three
   fixtures carry them (344, 473 and 226 checkpoints); neither `aoe2rec-py` nor `aoc-mgz` decodes
   them; a 180-line standard-library reader does, deterministically, with a test. This amends
   feature 006's finding that a recording carries intent and no outcomes: it carries no per-object
   outcome and a coarse per-player state sample every 6.5 to 15 s of game time.
7. **Recommendation C, hybrid, with a CONDITIONAL GO** (§11): the platform's published values stay
   command-log based, now anchored and bounded by the recording's checkpoints (exact, recomputable
   from the raw file, independent of any game install, constitution IV satisfied), and the engine
   route A is admitted as a validation and calibration instrument run by the owner on a lawfully
   held copy of the game, never as a production dependency, once the five conditions of §11 are
   met. The product does not promise CaptureAge parity and says so.

## 2. Environment and corpus

**Environment assessed 2026-11-08** (spec FR-006):

| Item           | Finding                                                                                                                                                                                                                                                                                                                          |
| -------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Host           | MacBook (Mac15,13), Apple M3, 16 GiB, macOS 15.1.1, arm64                                                                                                                                                                                                                                                                        |
| Game installed | At the start, no. During the spike (2026-11-08, 15:44 local) the owner installed the native macOS build through Steam: Feral Interactive bundle 1.3 RC5, game version `101.103.57257.0 (#188329)`, Steam build id 26272505, 23.2 GB, one arm64 Mach-O executable of 89 MB with a hardened runtime, `LSMinimumSystemVersion` 14.4 |
| Windows        | None: no installation, no Parallels, UTM or VMware Fusion, no CrossOver, Whisky or Wine                                                                                                                                                                                                                                          |
| Analysis tools | No Ghidra, IDA or Hopper; `strings`, `nm`, `otool` and `codesign` from the command-line tools                                                                                                                                                                                                                                    |
| Toolchains     | cargo 1.95.0 and rustc, Docker 28.1.1 with colima, node 24, uv, Python 3.13 and 3.14; no protoc, no grpcurl                                                                                                                                                                                                                      |
| Recordings     | the three committed fixtures only; no other `.aoe2record` on disk                                                                                                                                                                                                                                                                |
| Remote hosts   | none configured                                                                                                                                                                                                                                                                                                                  |

Consequences. Approach B could not be run: the development policy of this session refused
building and executing third-party code, and the engine needs the game's data file of its build,
which this project may not extract (§4; the file `empires2_x2_p1.dat` is present in the install
and was not opened). Approach D gained a binary mid-spike; what static inspection of it found is in
§2a and in the reverse-engineering document. Approach A gained a running game mid-spike, and the
static inspection says the Mac build does not carry the interface (§2a); the dynamic confirmation is
the owner's, below. The one route fully run was the recordings themselves (§6).

**2a. What the installed macOS build contains (DEMONSTRATED, static, 2026-11-08).** The
executable's 98,944 printable strings and the six bundled frameworks (HttpClient, PlayFab Party,
QuincyKit, Xal, xsapi-c, `libsteam_api.dylib`) hold **no gRPC code at all**: zero matches for
`grpc`, `CadeRemote`, `cade_api`, `ca-game-api`, `cade-client` or `4341`, where the Windows client
bundle redistributed by LibreMatch carries all of them (§3.1). The only `CaptureAge` strings are six
video subtitle style names; the only spectate-with-CaptureAge traces are three UI widget paths
(`Background/BottomButtonAnchor/ButtonSpectateCA` and two siblings) and a `screenloadgame.json`
reference in the UI definitions the Mac build shares with the Windows one. Protobuf is present, in a
Feral namespace, for Steam networking messages only. `otool -L` lists Apple frameworks and PlayFab
only. INFERRED from this: Feral's port omits the CaptureAge server, consistent with the absence of
any CaptureAge for macOS. The binary also carries the game version string
`101.103.57257.0 (#188329)`, 3,519 exported function symbols (Abseil and other third-party code;
the game's own functions are stripped) and 6,419 C++ RTTI type names, among them the complete
command hierarchy (`RGE_Command_*`, `TRIBE_Command_*`, including `TRIBE_Command_Cancel_Build`,
`TRIBE_Command_XsData`, `RGE_Command_Chapter`) and the object model (`RGE_Combat_Object`,
`RGE_Master_*`, `RGE_Doppleganger_Object`), which is what approach D can read without a
disassembler. The hardened runtime without `get-task-allow` means no debugger can attach to it on
this host; the spec forbids trying.

**What would confirm or unblock A** (spec FR-008). The confirmation is dynamic and is the owner's
to run: start the game, record any short game (a skirmish against the computer, a minute, with
"Record Game" on), open it from the Replays screen, and while it plays run
`lsof -nP -iTCP:4341 -sTCP:LISTEN` in a terminal; an empty result confirms the static finding. The
committed fixtures cannot serve for this: a replay plays only on the build that recorded it (§3.8)
and this client is build 188329 where they are 180059 and 185872. If the port is absent, A needs a
Windows 10/11 x64 machine with the game or Linux with Proton (ProtonDB Gold, Source 41), each with
its own Steam copy and account (§5.6). The web sources' macOS 15.7 requirement (Source 40) is
contradicted by the bundle's own `LSMinimumSystemVersion` of 14.4 and by Steam installing the game
on this macOS 15.1.1 host; whether it launches here was not observed in this session.

**Corpus** (spec FR-009), the three committed recordings, counts from their canonical golden
streams, checksums in `tests/fixtures/replays/README.md`:

| Recording | Build  | Players | Map id | Civilisation ids by slot | Duration | Queue commands | Placements | Research commands | Deletions | Market | Resignations |
| --------- | ------ | ------- | ------ | ------------------------ | -------- | -------------- | ---------- | ----------------- | --------- | ------ | ------------ |
| 500546441 | 180059 | 1v1     | 9      | 1: 9, 2: 26              | 53:29    | 899            | 326        | 55                | 43        | 107    | 1            |
| 504695319 | 180059 | 2v2     | 73     | 1: 2, 2: 8, 3: 4, 4: 33  | 51:56    | 810            | 386        | 103               | 16        | 115    | 2            |
| 511523321 | 185872 | 1v1     | 216    | 1: 23, 2: 37             | 37:23    | 410            | 220        | 32                | 23        | 12     | 1            |

Scenarios the corpus covers by command: economic development, several age advancements (22 age-up
commands across the three, feature 008's research), several civilisations, building construction,
military production, technology research, explicit deletions, resignation, two match sizes and
three durations. Combat, unit deaths, building destruction and technology cancellation are not
observable as commands and could only be validated through an engine route; no recording was
added for them because no route could run.

**Build situation** (spec FR-005): the reference build 185872 is the newest fixture's build; the
knowledge snapshots name 188329 as a later build; the live build on 2026-11-08 was not verified
here. Genie knows 158041 only (§4). The gRPC object model is maintained per build by its users
(§3.9). A replay plays only on its own build (§3.8).

## 3. Approach A: the game's gRPC interface (CaptureAge's route)

Every answer below is from the research agent's sourced report, re-read here; URLs in Sources.

1. **What it is.** A gRPC server inside the game process (`AoE2DE_s.exe`), service
   `cade_api.rpc.CadeRemote`, on `localhost:4341` (IPv4 and IPv6 loopback), HTTP/2 over TLS with
   mutual TLS. The game is the server; CaptureAge is the client. DEMONSTRATED by CaptureAge's own
   Electron worker bundle (constants `localhost:4341`, client stubs for twelve RPCs) and by three
   third-party clients (Sources 1–6). LibreMatch's lobby and matchmaking work is unrelated.
2. **When it is active.** Replay playback (DEMONSTRATED: third-party capture scripts wait for the
   port "while a replay plays"); live spectating (DOCUMENTED: game update 50292, 2021); an editor
   scenario test (DEMONSTRATED by a 2026 lab's tooling); a player's own live game only with cheats
   enabled in the lobby (DOCUMENTED, CaptureAge docs). A normal ranked game from the player's own
   client: INFERRED not available. No enabling flag is documented; clients poll the port
   (INFERRED: always on in observable modes). Sources 5–9.
3. **Without CaptureAge.** Technically yes, DEMONSTRATED: three code bases connect with no
   CaptureAge process, all presenting the same three files, a certificate authority, a client
   certificate with CN `cade-client` and its private key, issued by `O=CaptureAge BV`, valid
   2020-11-13 to 2040-11-08. The key sits in the public `librematch/delta-play-replay` repository;
   another project says it extracted the files "from the local game install". There is no Steam
   ticket or token: the certificate is the authentication. Sources 3, 10–12. The legal reading is
   in §9.
4. **Playback control.** Current API (CaptureAge 1.11.0 bundle, DEMONSTRATED by message
   definitions): `LoadGame` (a replay by file path, or a lobby to spectate), `Pause`,
   `SetGameSpeed`, `SetFogOfWar`, `SetPerspective`, `ChangeScreen`, `ChangeWindowState`
   (minimise, focus, render scale), an `Oracle` stream that drives the game UI. **No seek RPC**:
   CaptureAge's rewind is client-side over buffered frames and the optional `reversePatch`; forward
   seek beyond what was streamed is impossible. No command-line flag opens a replay (DOCUMENTED
   launch-option list). No headless or no-render mode exists; software and reference renderers and
   windowed mode do; the window may be minimised while streaming. Sources 2, 13–16.
5. **What state is exposed.** Nothing is a named protobuf field: `Frame.patch` is an opaque
   stack-machine delta against a reverse-engineered object model. In that model (Source 17):
   `World.entities` keyed by stable id; `Entity.owner_id`, `master_id`, `world_x/y/z`, `hp`,
   `state`; `BuildingEntity.build_pts`, `built`, `num_builders`, `production_queue`;
   `Player.research_states[tech]{research_done, state, times_researched}`; `PlayerAttributes`
   `food/wood/stone/gold` (f32), `population`, `max_pop`, `civilian_pop`, `military_pop`,
   `current_era`, cumulative `food_total` etc., `kills`, `razings`, scores; `GameOptions` (48
   fields incl. `game_id`, `is_ranked`, `population_limit`, Steam ids, `dat_file_crc`). Events:
   `EntityKilled{id, killerId}`, `MarketTransaction`, `Tribute`, `PlayerChat`, and in the current
   API `Damage`, `MonkConversion`, `NotificationResearchDone`, `NotificationTrainDone`. Commands:
   the same intent stream the recording holds. **Cancellation has no event**: it is INFERRED from a
   research state reverting or a queue shrinking. **Gather rates are not direct**: they are
   differences of cumulative totals between frames. The per-fact classification is the matrix.
6. **Snapshots and deltas; completeness.** The first patch after connecting is a full snapshot
   (0.4 to 5 MB), then deltas; reconnecting yields a fresh snapshot; `timeStepsSkipped` reports
   dropped steps; `metrics` name the regions covered. DEMONSTRATED by client code. A third-party
   decoder _skipped_ full snapshots "to avoid desync" and re-anchors with heuristics: fidelity is
   that of the model for that exact build (DEMONSTRATED limitation, Source 18–19).
7. **Time.** `Frame.time` is game time in milliseconds; CaptureAge requests 50 ms steps for
   high-priority state and 100, 500 and 1000 ms for lower categories; wall-clock rate follows
   `SetGameSpeed`. No wall-clock field. DEMONSTRATED from the bundle; no independent measurement
   published. Source 2, 20.
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
   dormant since 2024-09), `ddk220-light/aoe2_matchup` (Python, active 2026-11, no licence;
   decodes hp, owner, type, position, deaths), `DeadMeme5441/aoe2-de-bridge` (Python probe,
   2026-09, MIT). Sources 1, 4–6, 25.
10. **Platform.** Official: Windows 10/11 x64. Native macOS (Apple silicon) since 2026-05-28; no
    CaptureAge for macOS, and the installed Mac build's executable and frameworks contain no gRPC
    code (§2a, DEMONSTRATED statically; dynamic confirmation is the owner's). Linux/Proton: ProtonDB
    Gold, CaptureAge runs in the game's Proton prefix, one client targets Proton. Windows on ARM
    under Parallels: one 2021 anecdote, unsupported by Microsoft. Rendering cannot be disabled.
    Sources 36–41.

**Verdict on A.** The only demonstrated route to actual per-object state. Technically operable;
legally and operationally unresolved for this project (§9, §10). Not exercised here (§2).

## 4. Approach B: `librematch/genie`

From a read-only inspection of the source at commit `2cac47b3` (2026-11-07), obtained through the
GitHub API, nothing built or run; labels READ IN CODE, DOCUMENTED, ABSENT.

1. **What it is.** Not a fork but an import of `SiegeEngineers/genie-rs`'s format crates (2019 to
   2022, GPL-3.0), plus a new engine, `crates/engine/genie-core`: 313,644 lines of Rust in 704
   files written between 2026-10-15 and 2026-11-07 by one author; 1,553 of 1,603 commits since the
   import carry a Claude co-author trailer. 12 stars, 4 forks, issues disabled, no release.
2. **Does it load `.aoe2record`?** READ IN CODE for one build: the DE reader splits chapters,
   reads `VER 9.4`, minor, major and build; the world-save layout (`genie-save`, 12,420 generated
   lines) is "generated from build 158041's load routines"; the corpus tests filter on `(6660,
158_041)` and skip unless a private corpus and the game's data file are supplied. Build 185872
   appears once in the whole repository, as a `.dat` version the data-file reader accepts. The
   docs say "genie cannot read the recordings of other builds yet". No `.aoe2record` fixture is in
   the repository.
3. **Is there a simulation?** Yes, READ IN CODE, and it is substantial: a 20-step tick schedule,
   pathfinding (tile, long, short, hull), movement, combat and damage, missiles, gathering,
   construction and repair, production queues, technology effects, garrison and transport, groups
   and formations, unit AI, vision, players' history (population every 30 s, age, castle and
   wonder events) and victory; determinism ports of the game's `f32` math, eleven WELL512a random
   streams, MSVC introsort and `cvttss2si`. It is replay-driven: the header's world save is loaded
   into `World`, each command packet is decoded and `World::tick_with(dt, &commands)` advances
   state per sync; `genie-oracle` compares the engine's per-player 11-word checkpoint with the one
   the recording stores every 500 syncs (the same block §6 reads).
4. **Coverage.** 679 `unsupported` call sites with 236 distinct reasons; when a player hits one,
   its objects freeze for the rest of the replay. Monk conversion is not ported (named in the
   model only); computer players' behaviour is not run (so any game with an AI player cannot
   replay); cheats, siege pack and unpack, several transport and trade-cart states are
   unsupported; any command packet that does not re-encode byte-identically stops its player. The
   project's own documented census shows players stopping between updates 1154 and 1759 of a
   recording, minutes into a game.
5. **State and events.** `World` fields are public (players' attribute arrays incl. food, wood,
   stone, gold, population, kills, razings, techs researched; objects with master, state, hit
   points; research states; history). No serde on `World`, no snapshot or event CLI, no facade
   crate (the one the docs name does not exist); `tracing` events for object-state, action and
   unit-AI transitions exist and could be subscribed to. ABSENT: the gRPC/CaptureAge bridge the
   README describes.
6. **Headless.** READ IN CODE: no filesystem, network or clock calls in the core; no renderer
   crate in the lock file; CI builds the engine for WebAssembly.
7. **Data it needs.** The recording of the same build **and the game's `empires2_x2_p1.dat` of
   the same build** with two JSON tables beside it, to fill master values the save does not hold.
   Microsoft-owned, not redistributed by genie, not holdable by this project under the standing
   ruling of `docs/data-sources.md` §6 (the game's own data file: rejected).
8. **Performance.** UNKNOWN: nothing was run and the repository publishes no timing.
9. **Supporting 185872.** Regenerate the save layout, the command-packet layouts and the build
   layer from the 185872 executable with a reverse-engineering pipeline that is not in the
   repository; re-port every routine the game changed between the builds; validate against a
   185872 corpus with its data file. Each monthly game update repeats this. Without the pipeline
   being published, a downstream project can only wait for the single maintainer.
10. **Licence.** Engine and tools AGPL-3.0-only; format crates GPL-3.0. Linking the engine into a
    server-side analyser makes a combined work under AGPL §13 (source offer to every network user)
    and pulls every linked server component in; running it as a separate process is the usual
    isolation. Provenance: every port cites a routine address in the game's executable; this is a
    port of decompiled code, not a clean-room reimplementation, and a dependent project inherits
    the takedown exposure (§9).

**Verdict on B.** The only reimplementation with real DE replay simulation, and today it cannot
replay a build 185872 recording, cannot replay its own build to completion for every player, needs
the game's data file, and is maintained by one person through unpublished tooling. NO-GO as a
dependency; revisit if it publishes a current build layer, a stable facade and a corpus-backed CI.
Also checked: `SiegeEngineers/genie-rs` (format readers, last commit 2022-11, no simulation) and
`SFTtech/openage` (README: gameplay "basically non-functional", no binary compatibility, no
recorded-game support). Sources 26–30.

## 5. Approach C: other routes

1. **CaptureAge itself.** No export, API, file output, scripting hook, overlay data feed, CLI or
   developer programme anywhere in its docs, FAQ, tier lists or the publisher's announcements
   (DOCUMENTED absence). It opens replays and, in the paid tier, saves a proprietary `.caderec`
   that plays without the game at up to 8x; no reader for it is documented. Speeds 0.5x to 8x
   relative to game speed; the game simulates on one core and slows under load. Sources 31–34.
2. **Open-source engines.** openage (gameplay non-functional, no binary compatibility), freeaoe
   (AoC/HD assets, early), OpenAOE (dead): none runs a DE recording. DOCUMENTED. The structural
   reason: a recording stores commands, so playback needs the exact simulation that produced it.
3. **In-game XS scripting.** Since update 42848 (2020) XS can read unit hit points, positions,
   owners, object counts, technology states, resources and game time and write `.xsdat` files
   (DOCUMENTED function reference). The script comes from the map's random-map script or scenario,
   which a ranked replay fixes by identifier; changing it changes the simulation and desyncs the
   replay (INFERRED from documented out-of-sync behaviour; no source shows a modified-script replay
   staying in sync). Viable only for maps one controls; useless for third-party ranked recordings.
4. **Playback automation.** No documented command-line argument opens a replay; `aoe2de://` joins a
   lobby for live spectating; two third-party "one-click replay" tools do not disclose their
   mechanism; no headless, server or no-graphics mode in any source; in-game replay speed tops out
   at 4x. Hardware: DirectX 11, 2 GB VRAM minimum; no source shows the game on a GPU-less server
   (UNKNOWN; assume a GPU or GPU-partitioned instance). Sources 35, 42–43.
5. **Off Windows.** Native macOS build 2026-05-28 (Apple silicon, macOS 15.7+, no cross-play with
   Windows, replay compatibility with Windows recordings UNKNOWN); ProtonDB Gold; Parallels on
   Apple silicon "playable" from one 2021 report; CrossOver "playable". Sources 36–41.
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
`scripts/research/009-native-simulation/checkpoints.py` (standard library only, five tests,
`uv run pytest -q scripts/research/009-native-simulation/tests`).

**The fact.** Every 500 syncs (the pregame record's `checksum_interval`, 500 on all three
recordings) the game appends to the sync operation a block of eight lanes of eleven 32-bit words
and a world time. Each lane is one lobby slot; unused lanes are zero. The words are sums and counts
the simulation computes from its live state at that instant (published semantics, genie
`world/checkpoint.rs`): word 0 sleeping objects, **word 1 the four resource stocks summed after
truncation**, word 2 sum of master ids, word 3 sum of object states, word 4 sum of amounts held,
word 5 always 0, **word 6 live object count**, word 7 sum of positions times 100, **word 8 player
id**, word 9 action terms, word 10 sum of object ids. `aoe2rec-py` 0.1.24 exposes the block as an
opaque `checksum` with five mislabelled fields and skips 332 of its bytes; `aoc-mgz` treats it as
padding. Neither decodes it.

**Measured** (the test pins these):

| Recording | Checkpoints | Game time between checkpoints | First checkpoint (world time 8.7 s or 9.3 s): resource sum, live count per slot | Last: resource sum, live count |
| --------- | ----------- | ----------------------------- | ------------------------------------------------------------------------------- | ------------------------------ |
| 500546441 | 473         | 6.5 s (one gap of 12.0 s)     | slot 1: 500, 15; slot 2: 508, 15                                                | 655, 404; 1420, 489            |
| 504695319 | 226         | 6.5 to 15.3 s, median 14.0 s  | 450, 104; 500, 100; 450, 104; 450, 105                                          | 2742, 294; (see sample output) |
| 511523321 | 344         | 6.5 s, constant               | 550, 12; 650, 12                                                                | 1980, 290; 2706, 364           |

The spacing is 500 syncs exactly on every recording; the game time it spans varies because a
sync's length varies (13 ms steps in the 1v1s, longer in the 2v2). The first checkpoint's resource
sums sit within 0 to 100 of the standard 700 starting stock minus the villagers and houses queued
before it (two or three villagers at 50 food, houses at 25 wood), the residue being food gathered
from the first sheep and commands whose execution the log alone cannot settle; a full
reconciliation is feature 008's work, and this block is exactly the anchor that work lacked.

**Determinism** (spec FR-013): the block is produced by the game's own deterministic simulation
during the recorded match and stored; reading it twice yields byte-identical words (tested). Nothing
to re-simulate.

**Time bases** (spec FR-014): the checkpoint's `world_time` and the sum of sync increments up to
its operation differ by the current sync's increment (13 ms in the 1v1s), because the block is
written with the sync it belongs to; the prototype reports both. Feature 008's `clock_ms` is the
sum of increments.

**Provenance** (spec FR-012): `ENGINE_STATE`, sampled by the game and stored in the recording.
Exact as integers. Coarse: per player, every 500 syncs, sums and counts, never per-object values,
never per-resource stocks, never an event. A death is visible only as a live-count decrease net of
creations between two checkpoints; a resource spend only as a decrease of the sum net of income.

**What it changes.** Feature 006's finding "replays carry intent, never outcomes" becomes "replays
carry intent, no per-object outcomes, and a per-player state sample every 500 syncs". For feature
008 it supplies, from the raw file alone and for every build, the two bounds its spending and
population reconstruction lacked: at every checkpoint the sum of stocks is known exactly, so the
cumulative spend plus income is pinned every 6.5 to 15 s, and the live object count bounds the
population of objects (buildings included, so it is not the population figure itself). It is also
the correctness oracle genie uses, which says how weak it is as a full-state check: eleven sums per
player.

## 7. Validation scenarios (spec FR-010, SC-003)

| Scenario              | Route that could validate it | Status on 2026-11-08        | Evidence                                                                                           | Exact?                            |
| --------------------- | ---------------------------- | --------------------------- | -------------------------------------------------------------------------------------------------- | --------------------------------- |
| Unit creation         | A                            | not run                     | A: entity insertion in the patch (DEMONSTRATED by third parties). Checkpoints: live count rises    | A exact; checkpoint net count     |
| Unit death            | A                            | not run                     | A: `EntityKilled{id, killerId}`, hp ≤ 0, removal (third parties). Checkpoints: live count falls    | A exact; checkpoint net count     |
| Building construction | A                            | not run                     | A: `build_pts`, `built`, `num_builders`. Command log: placement only                               | A exact                           |
| Building destruction  | A                            | not run                     | A: removal, `razings`. Checkpoints: live count falls                                               | A exact                           |
| Technology research   | A                            | not run                     | A: `research_states`, `MakeTechAction`, `NotificationResearchDone`; cancel INFERRED from reverting | completion exact; cancel inferred |
| Population            | A                            | not run                     | A: `population`, `max_pop`, civilian/military. Checkpoints: live objects incl. buildings           | A exact                           |
| Resources             | A, checkpoints               | **checkpoints run**         | A: four f32 stocks. Checkpoints: integer sum of the four, every 500 syncs, three recordings        | sum exact                         |
| Resource gathering    | A                            | not run                     | A: cumulative totals differenced (INFERRED rate). Checkpoints: sum changes net of spend            | derived                           |
| Production queues     | A                            | not run                     | A: `production_queue`, `NotificationTrainDone`                                                     | A exact                           |
| Age advancement       | A, command log               | command-log proof run (008) | A: `current_era`. Command log: click plus first age-gated order (008 R3, 3,235/3,241 consistent)   | A exact; log a bound              |

Count validated experimentally here: one scenario fully (resources, as a sum), two partially (unit
creation and death as net live-count movement), all on three real recordings; the other seven
depend on route A and were not run (§2). SC-003 (five scenarios) is **not met** by this spike; the
matrix says so row by row.

## 8. Architecture assessment (spec FR-016, FR-017)

The brief's pipeline, replay execution adapter → extraction layer → normalised state and event
model → persisted match data → deterministic analysis → coaching metrics, is evaluated, not adopted.

- **Replay execution adapter.** Only A exists to adapt to. Lifecycle per replay: `LoadGame` by
  file path on a host where the game of the recording's build is running and signed in,
  `SetGameSpeed` to the maximum, `SetFogOfWar(false)`, stream `Frames` until the game ends,
  decode the snapshot and deltas against a per-build model, detect the clock reset for the next
  game. Error handling: reconnect yields a fresh snapshot; desync between decoder and model is the
  known failure and is detected only heuristically. Retry: replay again from the start, no seek.
- **Version compatibility.** Two couplings: the replay to its build (the client must be on it;
  with monthly patches a recording older than the current patch cannot be replayed by a current
  client unless old builds are kept installed) and the decoder to the build's object model.
  CaptureAge's `.caderec` exists because of exactly this.
- **Throughput.** Game time runs at 1.7x real time at normal speed, up to 8x relative; one core;
  slower on large games. A 50-minute match takes 6 to 30 minutes of a machine that renders a
  window. Parallelism is one game instance per Steam account and machine.
- **Storage.** A snapshot is 0.4 to 5 MB and deltas at 50 ms over 50 minutes are tens to hundreds
  of MB raw; a normalised event stream would be far smaller; the raw stream would be the
  irrecoverable artifact only if the replay could not be re-run, which it cannot after the next
  patch, so constitution III's verbatim-persistence rule would apply to it.
- **Hosting.** Nothing in either hosting phase (Vercel functions, an OVH VPS) can run the game. An
  extraction host is a third kind of machine with a display, a Steam account and the game: a
  Windows or Proton VM with a GPU (USD 520 to 640 per month on demand) or a physical machine at the
  owner's, possibly the owner's own Mac if the native build serves the port. It is outside
  constitution XII as written and would need an amendment naming it as an optional, non-required
  instrument.
- **Security and isolation.** The host holds a Steam session and a credential that is not ours; it
  must never be reachable from the application, and its output enters the system as a provider's
  data (constitution III) with the same fixtures-and-contract-tests discipline as every other
  external source.
- **Independence from the provider.** A normalised model (object lifecycle, research lifecycle,
  stocks, population, events) keeps the analysis engine independent of A, B or the checkpoints; the
  recording's checkpoints feed the same model today.

## 9. Licensing and terms (spec FR-018)

Technical and legal risk are recorded separately. This section states what the texts say; it is
not legal advice.

| Dependency or act                                  | Licence or term                                                                                                                                                         | What it means here                                                                                                                         |
| -------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| Connecting to `:4341` with CaptureAge's client key | CaptureAge Terms: no reverse engineering, no working around technical limitations, no making the application available to third parties                                 | The credential is CaptureAge BV's; presenting it is the central exposure. Sanctioned path: an agreement with CaptureAge BV or World's Edge |
| Automating the game client                         | Steam Subscriber Agreement §2.G (reverse engineering, emulating or redirecting protocols), §4.B, §4.C (scripts, bots); Microsoft Services Agreement §8.b.ii, §14.a.viii | Replaying one's own recordings is not cheating, but driving the client programmatically sits inside these clauses                          |
| Microsoft Game Content Usage Rules                 | Non-commercial only; no reverse engineering "to access the assets"                                                                                                      | Constitution X's anchor; a commercial extraction service is excluded                                                                       |
| `librematch/genie`                                 | AGPL-3.0-only engine, GPL-3.0 formats; ported from decompiled routines                                                                                                  | AGPL §13 on a linked server; takedown exposure inherited; not clean-room                                                                   |
| `librematch/delta-play-replay` protos and bundle   | Repository AGPL-3.0-or-later; protos and the redistributed CaptureAge bundle and key are not the repository's to license                                                | The protos are usable as documentation of a wire format; nothing else from it may be copied                                                |
| The game's data file (needed by B)                 | Rejected by `docs/data-sources.md` §6 for three independent reasons                                                                                                     | Unchanged by this spike                                                                                                                    |
| EU law on decompilation                            | Directive 2009/24/EC Art. 5(3), 6, 8                                                                                                                                    | Observation and interoperability decompilation are preserved against contrary terms, under conditions; see the REA document                |

No game asset, executable, data file, certificate or key was copied into this repository.

## 10. Operational requirements, summarised

An engine-backed pipeline needs: a machine with the game installed and signed in, on the build of
each recording it processes, with a display, running one replay at a time at up to 8x game speed; a
per-build object-model maintenance task after every game update; a lawful basis for the client
credential; and an amended constitution (III: the stream is an external source behind a provider;
XII: the host is outside both hosting phases). A checkpoint-anchored command-log pipeline needs
none of these: it reads the raw file this project already holds, for every build, in milliseconds.

## 11. Recommendation and decision (spec FR-022)

**Recommendation: C, hybrid.** The platform's published values stay command-log based and are now
anchored and bounded by the recording's own engine checkpoints (§6). Route A is admitted as an
instrument for validation and calibration, run by the owner on a lawfully held copy of the game,
never as a dependency of the deployed product, and only once the conditions below hold. Route B is
a watch item. Route D's standing is in its own document.

**Decision: CONDITIONAL GO.** The engine route works and is demonstrated by others; this project
has not run it, and may not run it in production until:

1. **A lawful credential.** An agreement with CaptureAge BV or World's Edge for access to the
   interface, or the owner's recorded decision to accept the exposure of §9 for a private,
   non-commercial, owner-operated instrument. The repository never holds the key.
2. **The owner's experiment.** First the one-minute check of §2 on the installed Mac build (record
   a short game, replay it, `lsof -nP -iTCP:4341 -sTCP:LISTEN`); the static reading predicts an
   empty result. Then, on a Windows or Proton host with its own Steam copy: does `:4341` answer
   during replay playback; does a recording made on that client's build stream; can resources,
   population, deaths and research completion be decoded for one match and compared with the
   checkpoints of §6 and with CaptureAge's display? This is the demonstration SC-001 and SC-003
   still lack.
3. **A per-build model plan.** Who re-validates the decoder after each game update, and what the
   product shows for a recording whose build the instrument can no longer replay.
4. **Constitution amendments** for III and XII (§8, §10) and the processing-register entry for the
   instrument's host, before anything it produces is published.
5. **Product honesty.** The site states that it shows what a player ordered, what the recording
   proves and the game's own checkpoints, and never claims the per-object exactness of a tool that
   runs the game, unless and until the instrument is in place.

What feature 008 should take from this now, without this spike amending it (spec FR-020, SC-010):
the recording's checkpoints are a new tier-A fact to decode and to use as the anchor for its
spending and population rules; its gate G1 gains an exact oracle for the sum of stocks; its
population figure cannot be the live count. The owner's rule of one exact value per datum is
unaffected for what the log proves, and the deductive rules it debated remain deductions.

## 12. Remaining unknowns

- Whether the macOS native build serves `:4341` at run time (its binary carries no gRPC code, §2a;
  the owner's dynamic check is pending), and whether it plays recordings made on Windows.
- The live game build on 2026-11-08 and whether build 185872 is still obtainable.
- The exact semantics of `AccessFlag` and of the `Oracle` stream beyond what the bundle shows.
- Whether the interface can be used lawfully by anyone other than CaptureAge BV without an
  agreement.
- Genie's actual behaviour on any recording (nothing was run).
- Checkpoint word semantics beyond words 0, 1, 6 and 8 were read from genie's source and not
  independently verified; word 1's identity as the sum of the four stocks is corroborated by the
  first-checkpoint values of all eight players (§6) and by genie's own oracle design.

## 13. Independent review

Pending: the reviewer's assessment is appended here when it returns.

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
40. Mac requirements (macOS 15.7, Apple silicon):
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
