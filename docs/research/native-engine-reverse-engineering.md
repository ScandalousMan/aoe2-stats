# Native engine reverse engineering with REA: assessment

- **Feature**: 009, approach D (`specs/009-native-simulation-feasibility/spec.md`, FR-001, FR-001a)
- **Assessed**: 2026-11-08
- **Companion**: `docs/research/native-simulation-feasibility.md` (the approaches A to C, §2a for
  the static inspection of the installed Mac build) and the capability matrix

**Decision criterion** (the owner's brief): does REA reveal a technically viable route to actual
simulation state that the gRPC investigation does not already cover? **No.** Every external surface
of the engine that published work or this inspection can name is already known: the CaptureAge
gRPC server (Windows client only), the recording file (commands plus the per-player checkpoints),
save games, in-map XS data files and AI-script facts. Static analysis can refine the first of
these; it cannot add a sixth, and anything it finds is a hypothesis until exercised in a running
game on Windows. REA is not recommended as a runtime dependency: no operational role for it has
been demonstrated, and none is foreseeable for a product that reads files.

Labels as in the companion report: DEMONSTRATED, DOCUMENTED, INFERRED, UNKNOWN. What this
document did and did not do: it inspected the installed macOS binary with the command-line tools
(`strings`, `nm`, `otool`, `codesign`, `plutil`), read-only, nothing modified, nothing attached,
nothing run; it did **not** configure REA or any disassembler, because no backend is installed on
this host and the decision criterion could be answered without one. Everything about the Windows
executable is sourced from published work.

## 1. REA and the analysis environment

**What REA is** (DOCUMENTED, `morluto/rea`, MIT, TypeScript, npm `rea-agents` 6.8.0 of 2026-10-25,
last push 2026-11-08). A local MCP server and CLI that drives analysis engines it does not bundle:
deep native providers Hopper, Ghidra 12.1 or later (a headless Java bridge over an ephemeral,
read-only project), IDA through third-party IDA MCP servers, and Kuna; auxiliaries objdump, Rizin,
GDB (Linux only), Frida, an LLDB call tracer (macOS Mach-O targets REA launches itself) and process
capture (Linux and macOS). Every result carries provenance, limitations and unknowns. Not present:
Binary Ninja, radare2, any Windows debugger. Releases are frequent and breaking (about twenty
breaking changes in 6.8.0 alone). Its disclaimer refuses help with circumventing DRM, licence
checks or anti-cheat.

**Free path on this host** (DOCUMENTED): Ghidra 12.1.x plus an arm64 JDK 21 (a JDK under Rosetta
fails REA's doctor), then `npx rea-agents setup`. Hopper (demo mode, paid licence) and IDA Free
(non-commercial, cloud decompiler) are alternatives. Nothing of this is installed here: no Java
runtime, no Ghidra, no Hopper, no IDA (checked 2026-11-08).

**Static only, from here.** For a Windows PE on macOS, REA offers no dynamic path. For the Mac
Mach-O, REA's LLDB tracer launches a binary under LLDB; the installed game is signed with the
hardened runtime and without `get-task-allow`, so a debugger cannot attach or launch it for tracing
on a stock system, and FR-001a forbids changing that.

**Demonstrated use on this game** (DOCUMENTED, two hobby repositories, Windows executable):
`gszep/age-of-empires` ran REA 6.4.0 with Ghidra 12.1.4 over builds 101.103.48987.0 and
101.103.54800.0; whole-binary analysis timed out at 180 minutes, targeted per-function
decompilation from the exception table worked in minutes (21 of 22 bodies). `bijoymuzid/AoE2DE-LAN`
ran Ghidra 11.3.2 over a build of 72,176,952 bytes; its target was a cracked copy, so it is not a
lawful-copy precedent and its injection work falls outside FR-001a.

## 2. Binary and version identification

**Installed here** (DEMONSTRATED, 2026-11-08): the native macOS build by Feral Interactive, Steam
app 813780, Steam build id 26272505, installed 15:44 local, 23.2 GB. Bundle
`com.feralinteractive.ageofempires2` version 1.3 RC5, `LSMinimumSystemVersion` 14.4. One executable,
`Age Of Empires II.app/Contents/MacOS/Age Of Empires II`, Mach-O 64-bit arm64, 89,088,304 bytes,
code-signed by team `XH73Y9BGP8` with the hardened runtime and the
`com.apple.security.cs.disable-library-validation` entitlement. The binary carries the game version
string `101.103.57257.0 (#188329)`: **the installed Mac build is game build 188329**, three builds
after the newest committed fixture (185872). Six bundled frameworks: HttpClient, PlayFab Party,
QuincyKit, Xal, xsapi-c, `libsteam_api.dylib`. The data directory holds the game's data file
(`resources/_common/dat/empires2_x2_p1.dat`, 11,963,833 bytes, not opened: the standing ruling of
`docs/data-sources.md` §6 is unchanged), the UI definitions, a curl CA bundle of 132 public roots and
no CaptureAge certificate.

**Windows executable** (DOCUMENTED, not held here): `AoE2DE_s.exe`, PE32+ x64, MSVC, about 72 MB,
no PDB, intact import table, RTTI and log strings and source paths surviving; Arxan anti-tamper on
every version (PCGamingWiki), with selected functions encrypted on disk and decrypted at run time,
an integrity reaction (clean exit about 5.6 s after a protected function is patched) and a
`WinVerifyTrust` check over the bundled binaries that makes the game refuse to run under Wine
unless Wine is patched. Layouts differ wholesale between builds; no address translates.

## 3. What the Mac binary shows without a disassembler (DEMONSTRATED, static)

Method: `strings -n 6` (98,944 strings), `nm` (9,198 symbols, 3,519 exported functions, 0 local
function symbols), `otool -L`, pattern searches. Confidence is stated per finding.

| Finding                                                                                                                                          | Evidence                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        | Confidence                                                                                                                                        |
| ------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| The game's own functions are stripped; the exported functions are third-party (Abseil, protobuf in a `feral_google` namespace, Steam networking) | `nm` output, symbol prefixes                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    | high                                                                                                                                              |
| 6,419 C++ RTTI type names survive, including the whole command hierarchy and the object model                                                    | `GameCommand<RGE_Command_*>` and `GameCommand<TRIBE_Command_*>` for Move, Stop, Work, Guard, Pause, Scout, Create, Follow, Patrol, Resign, Game, Gate, Make, Chapter, Retreat, Trigger, Build, Queue, AI_Order, Interact, Stop_All, Repair, Unload, XsData, Explore, Special, Auto_Scout, Research, Attack_Move, Diplomacy, Town_Bell, Add_Waypoint, Seek_Shelter, GoBackToWork, SendAISignal, Build_Wall, Drop_Relic, Multi_Gate, PseudoTech, Unit_Order, Add_Attribute, Unit_AI_State, Multi_Queue, Form_Formation, Give_Attribute, Group_AI_Order, Group_Waypoint, Lock_Formation, **Cancel_Build**, Auto_Formations, Break_Formation, Give_Attributes, Wheel_Formation, Attack_Ground, Multiplayer_Save; objects `RGE_Action_Object`, `RGE_Animated_Object`, `RGE_Combat_Object`, `RGE_Doppleganger_Object`, `RGE_Master_*` (action, animated, combat, doppleganger, missile, moving), `RGE_Map`, `RGE_Map_Analysis`; 269 distinct `RGE_`/`TRIBE_` names outside commands; `TRIBE_Action_Capture`; `Age2TabLoadGameReplays` | high that the names exist; their layouts are not readable this way                                                                                |
| Source paths of the port survive (361 strings)                                                                                                   | `/Users/bob/BobBuild/ageofempires2_1_3/Companies/Feral/Development/Products/AgeOfEmpires2/Source/Aoc/Source/Game/FileTypes/SaveGame/RecordedGameFileExtensions.cpp` and siblings for save games; Feral libraries Iceworks, Macdoze, ZGameLib                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    | high                                                                                                                                              |
| File types the client knows                                                                                                                      | `.aoe2record`, `.aoe2spgame`, `.aoe2mpgame`, `.xsdat`, `SaveGame` paths with Windows separators, `saveGameChecksum`, `oldSaveGameVersion` / `newSaveGameVersion`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                | high                                                                                                                                              |
| Recording controls exist in the UI                                                                                                               | `RecordGame`, `mRecordGameEnabled`, launch options `RECORDGAME`, `NORECORDING`, `ALLOW_SOFTWARE_RENDERER`; URL scheme `aoe2de://0/`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             | high                                                                                                                                              |
| **No gRPC server**                                                                                                                               | zero matches for `grpc`, `CadeRemote`, `cade_api`, `ca-game-api`, `cade-client`, `4341` in the executable and in all six frameworks; the only `CaptureAge` strings are six video subtitle style names; three UI widget paths `ButtonSpectateCA` and a `screenloadgame.json` reference belong to UI definitions shared with the Windows build                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    | high for the absence of the strings; the inference that the server is absent is strong but static (a dynamic check is in the companion report §2) |
| Protobuf present for Steam networking only                                                                                                       | `steamnetworkingsockets_messages_udp.proto`, `google/protobuf/descriptor.proto`, `FileDescriptorProto` in `feral_google::protobuf`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              | high                                                                                                                                              |
| No other IPC surface named                                                                                                                       | no named pipe, shared memory, Mach port or XPC strings beyond Direct3D constant names; one Unix socket path message and `/var/run/minissdpd.sock` from a UPnP library                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           | medium (strings can be built at run time)                                                                                                         |
| Listening sockets belong to Steam networking                                                                                                     | `Cannot create listen socket`, `listen v6 only`, `TakeOwnershipOfSocketAndSelfDestruct` are `SteamNetworkingSockets` messages                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   | medium                                                                                                                                            |

What this yields for FR-001a's ten objectives, honestly: the **names** of the command classes
(replay playback decodes exactly these), of the object model and of the save-game file types; the
**absence** of the gRPC server in this build; and nothing about internal layouts, update routines,
resource accounting or research handling, which need a disassembler and, to be more than
identification, a running game.

## 4. What a REA session could add, and what it could not

**Could add, statically, on the Windows executable held lawfully** (INFERRED from the published
runs): string- and RTTI-led, never whole-binary. Three questions are worth a bounded session:

1. Is the `cade_api.rpc.CadeRemote` descriptor embedded, and what does it declare for the current
   build? Serialized `FileDescriptorProto` strings would confirm the twelve RPCs and the event
   types the 2021 proto lacks (`Damage`, `MonkConversion`, `NotificationResearchDone`,
   `NotificationTrainDone`) without CaptureAge's bundle.
2. Under which condition does the server start (replay playback, spectating, cheats enabled), and
   does the game pin CaptureAge BV's root or accept other roots? A refinement of approach A's legal
   question, not a new route.
3. Which RTTI classes hold player attributes and research states, to cross-check genie's build
   layer for a current build.

Limits: Arxan-encrypted bodies read as garbage on disk (gszep's run saw "contains only a halt
instruction" on a resource routine), so an unknown share of the simulation is not decompilable
from the file; whole-binary analysis does not finish; every address is per build. On the Mac
binary the same three questions have already been answered negatively by `strings`: there is no
descriptor to find.

**Could not add**: a route to actual simulated state. Identifying `WorldPlayerBase::create_checksum`
or `TRIBE_Action_Make_Tech` (genie names both, with addresses, for build 158041) does not make them
observable from outside the process; observing needs hooks, a debugger or a memory read inside the
anti-tamper's integrity domain, all excluded by FR-001a and all Windows-only. Save games are full
state at one instant and genie parses them for build 158041, but producing one at a chosen moment of
a replay needs the running game too, so they do not improve on A.

**Could REA help genie?** Only as the same manual labour genie's author already performs with a
private pipeline (`aoe2de-exe-re` layouts, load and tick oracles, a build-layer generator, none
published): porting is routine by routine from decompiled code, and the output is AGPL code this
project would not link (companion §4, §9).

## 5. Relationship with CaptureAge and the gRPC interface

- The Windows client embeds gRPC 1.51.1 and OpenSSL 1.1.1g (DOCUMENTED, bijoymuzid), resolves
  `localhost svc=4341` at start-up (DOCUMENTED, run-time log on a cracked copy) and serves
  `CadeRemote` to CaptureAge behind mutual TLS with CaptureAge BV's certificates (companion §3).
- The Mac client has none of it (§3 above). Feral's port predates no CaptureAge release for macOS
  and ships without the partner server; this is consistent with CaptureAge's own platform list.
- Therefore approach A exists on Windows (and Linux under Proton, where the Windows binary runs)
  and not on the machine this project develops on. REA changes nothing about that.

## 6. Technical and legal constraints

Technical: hardened runtime without `get-task-allow` on the Mac (no attach, no launch under LLDB);
Arxan on Windows (encrypted functions, integrity exit, `WinVerifyTrust`); no PDB on Windows, no
dSYM on the Mac; 72 to 89 MB images that defeat whole-binary analysis; per-build layouts; a game
patched several times a year.

Legal, what the texts say (not advice; the companion §9 holds the full table):

- Directive 2009/24/EC Art. 5(3) lets a person entitled to use a copy observe, study and test it;
  Art. 6 permits decompilation without authorisation when indispensable for interoperability of an
  independently created program, by a licensee, where the information "has not previously been
  readily available", confined to the necessary parts; Art. 8 voids contrary contract terms. CJEU
  C-13/20 Top System (2021) adds decompilation for error correction by a lawful purchaser, within
  necessity and the contract.
- Steam Subscriber Agreement §2.G forbids reverse engineering "except ... under applicable law
  notwithstanding these restrictions" (2026-09-10 version). Microsoft's Game Content Usage Rules
  forbid reverse engineering "to access the assets" for fan creations. The Steam EULA slot for the
  game holds World's Edge's Code of Conduct. CaptureAge's terms forbid reverse engineering its
  application and working around its technical limitations.
- Spec FR-001a encodes the conservative reading. The one point for the owner: Art. 6(1)(b). The
  interoperability information for the gRPC interface is already readily available through
  LibreMatch's publications, which narrows what decompiling the executable could lawfully add
  under that article. Reading strings from a file one owns does not run the game and triggers
  none of its protections (INFERRED).

## 7. Practical recommendations

1. **Do not adopt REA, or any disassembler, as a dependency of this project.** Nothing it can
   produce is consumed at run time; the product reads recordings.
2. **Do not pursue approach D further for state access.** The decision criterion is answered: no
   route beyond the five known surfaces, and nothing demonstrable from this host.
3. **If the owner wants the three bounded questions of §4 answered**, the setup is: a lawfully held
   Windows executable (DepotDownloader with the owner's own Steam account, or a copy from a Windows
   install), Ghidra 12.1 with an arm64 JDK 21, `npx rea-agents setup`, then string-led
   `rea search` and targeted `rea decompile` by address; budget hours, not minutes, and expect
   encrypted bodies. Record the owner's Art. 6 reasoning first.
4. **What the Mac install is good for now**: the dynamic confirmation in the companion report
   (record a short game, replay it, check that nothing listens on 4341), and later, if a Mac
   recording is needed, producing recordings on build 188329. It cannot serve approach A.
5. **Feed to feature 008**: the command vocabulary above includes `TRIBE_Command_Cancel_Build`,
   `TRIBE_Command_Multi_Queue` and `RGE_Command_Chapter`; the canonical adapter's unseen
   `unit-unqueued` and the first-building collapse of `unit-queued` (008 R1, R7) have names in the
   client worth checking against the parser's layouts when a recording with a cancellation exists.

## Sources

- REA: https://github.com/morluto/rea (README, AGENTS.md, DISCLAIMER.md, CHANGELOG.md,
  docs/getting-started/installation.md, docs/providers/ghidra-provider.md,
  docs/providers/ida-provider.md, docs/guides/native/native-investigation.md,
  docs/guides/runtime/process-capture.md); https://rea.tools/
- Published REA and Ghidra runs on the Windows executable: https://github.com/gszep/age-of-empires
  (docs/rea-resume-plan.md, docs/aoe2de-native-machinery-notes.md);
  https://github.com/bijoymuzid/AoE2DE-LAN (PLAN.md, notes/m1-session14.md; cracked copy)
- Anti-tamper: https://www.pcgamingwiki.com/wiki/Age_of_Empires_II:_Definitive_Edition ; Wine bug
  55165, https://list.winehq.org/hyperkitty/list/wine-bugs@list.winehq.org/message/NZPAMF6YB2ROVVOMCVOAG37BNNFB5R4W/
- Prior art: https://github.com/librematch/genie ; https://github.com/librematch/delta-play-replay ;
  https://librematch.github.io/wiki/grpc ; https://aoe2control.github.io/ ;
  https://github.com/01010100b/AoE2Lib
- Obtaining the executable: https://github.com/SteamRE/DepotDownloader ;
  https://store.steampowered.com/subscriber_agreement/
- Legal texts: https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:32009L0024 ;
  https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:62020CJ0013 ;
  https://www.xbox.com/en-US/developers/rules ; https://captureage.com/terms
- The installed Mac build: inspected locally on 2026-11-08 with `strings`, `nm`, `otool -L`,
  `codesign -dv --entitlements -`, `plutil -p`; Steam manifest `appmanifest_813780.acf`
