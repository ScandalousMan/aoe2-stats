# Data Model: Shrink what each production deployment stores

This feature stores no data and adds no table. Its "entities" are the declarations a deployment is
built from and the one decision the build-skip rule makes. Each is defined once, in the file named,
and read by the test that guards it.

## 1. Function bundle

One entry per production function in `vercel.json`'s `functions` map.

| Field            | Meaning                                              | Rule                                                                                                                          |
| ---------------- | ---------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------- |
| entrypoint       | The file under `api/` the host turns into a function | Exactly three, unchanged (FR-012): `api/index.py`, `api/analyze.py` and `api/cron/ingest.py`                         |
| time limit       | `maxDuration`                                        | `api/index.py` keeps its short limit; the two long-running entrypoints keep theirs |
| excluded content | `excludeFiles`, one glob                             | Names repository content to drop (FR-002); never names `api/`, never names installed dependencies (research R1)               |

**Invariant**: every file under `api/` is one of the three entrypoints, and
`scripts/checks/api_entrypoint_deps.py` scans every file under `api/`.

## 2. Never-shipped path list

The declared repository paths whose changes cannot affect the static build's output or any function.
Defined once, in the skip rule's module (research R3); read by the rule and by its test.

| Field   | Meaning                                                                                                                                 |
| ------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| pattern | A repository-rooted glob                                                                                                                |
| reason  | One line: why no build output and no function reads it — kept next to the pattern, so a reviewer weighs each entry rather than the list |

**Validation** (asserted by the test, not by prose):

- A change to any always-deploy path (§3) builds, alone or beside any never-shipped path. Overlap
  between the two lists is allowed and expected (`scripts/**` covers `scripts/deploy/**`): the
  always-deploy list is checked first, so the verdict, not the absence of overlap, is the
  invariant (FR-008, amended).
- No pattern matches an application source path or a web-app path that is neither a test nor a
  story. Those deploy through the rule below, not through §3 (FR-008, amended).
- A path matched by no pattern is shipped. There is no "unknown" class (FR-007).

## 3. Always-deploy list

The concrete paths FR-008 names. Checked before the never-shipped list, so a change to one of them
deploys whatever else the push contains. Includes the skip rule's own module and its never-shipped
list (Edge Cases: the skip rule changes itself). FR-008's "application source" and "the web app"
are deliberately not entries here: they hold their own tests and stories, and checking their
directories first would deploy every test-only and story-only change. They deploy because no
never-shipped pattern matches them (§2).

## 4. Skip decision

The rule's only output. A pure function of its inputs, so the test can drive it without the host.

| Input              | Source at build time (research R3)                                               | When absent or unreadable                                                             |
| ------------------ | -------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------- |
| target environment | The host's system environment variable for it                                    | Build (FR-011, FR-007)                                                                |
| comparison base    | The host's variable for the last successfully deployed commit                    | Build (FR-007)                                                                        |
| pushed commit      | The host's variable for the commit being built                                   | Build                                                                                 |
| changed paths      | A diff between the comparison base and the pushed commit, both sides of a rename | Build, when the diff cannot be computed (base absent from the clone, shallow history) |

| Output | Exit code the host reads (research R3) | Logged reason                                                  |
| ------ | -------------------------------------- | -------------------------------------------------------------- |
| skip   | the host's "cancel" code               | `non-production` or `nothing shipped between <base> and <head>` |
| build  | the host's "proceed" code              | the first shipped path, or the reason the input was unreadable |

**Order of evaluation** (FR-011 before FR-006):

1. Target environment is readable and not production → skip.
2. Any input unreadable, or the diff fails → build.
3. No changed path at all (the base is the pushed commit, which only a redeploy produces) → build
   (FR-010).
4. Any changed path is in the always-deploy list → build.
5. Any changed path is matched by no never-shipped pattern → build.
6. Otherwise → skip.

An exception anywhere in the rule exits with the "proceed" code: the host treats a non-zero,
non-cancel exit as proceed (research R3), and the module also catches everything at its top level so
the outcome does not depend on that reading alone.

## 5. History fixture

One recorded case for the offline test (FR-009).

| Field         | Meaning                                                                                       |
| ------------- | --------------------------------------------------------------------------------------------- |
| range         | Base and head commit ids from `main`'s first-parent history                                   |
| changed paths | The paths `git diff --name-only --no-renames base head` printed when the fixture was recorded |
| environment   | `production` unless the case is the non-production one                                        |
| expected      | `skip` or `build`                                                                             |
| why           | One line                                                                                      |

Recording the paths, rather than re-running `git diff` in the test, keeps the test independent of
the CI checkout depth. A separate test over a throwaway git repository covers what recorded paths
cannot: an absent base, a shallow clone, and a rename (research R4).
