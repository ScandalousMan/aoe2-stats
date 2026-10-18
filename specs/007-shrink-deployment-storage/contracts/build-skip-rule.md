# Contract: build-skip rule

The interface between the host and `scripts/deploy/ignore-build.mjs`. The host runs it as
`vercel.json`'s `ignoreCommand` when a deployment starts building, from the repository root, in a
clone of depth 10 (research R3).

## Inputs

Three host system variables, named in research R3: the **target environment**, the **pushed
commit**, and the **comparison base** (the last successful deployment's commit on this branch). It
reads no other variable and no file outside the repository, and makes no network call.

## Exit codes

| Exit | Host reading           | When                                                                                          |
| ---- | ---------------------- | --------------------------------------------------------------------------------------------- |
| 0    | ignore: build canceled | target environment is readable and not production; **or** at least one path changed and every changed path is never-shipped |
| 1    | proceed: full build    | anything else, including every error                                                          |

Any other non-zero exit (a crash, `git` failing) also builds, by the host's reading. The rule never
relies on that: its body is wrapped so that every failure exits 1.

## Decision order

Exactly `data-model.md` §4:

1. Non-production → 0.
2. Comparison base or pushed commit empty, unreadable, or absent from the clone; `git diff` fails → 1.
3. No changed path at all (the base is the pushed commit: a redeploy) → 1.
4. A changed path on the always-deploy list → 1.
5. A changed path matched by no never-shipped pattern → 1.
6. Otherwise → 0.

"Changed paths" are every path between the comparison base and the pushed commit, both sides of a
rename, every commit in the range, not only the last.

## Output

One line on standard output, which the host shows in the build log:

- `skip: non-production (<environment>)`
- `skip: nothing shipped between <base> and <head> (<n> paths)`
- `build: <first shipped path> (<base>..<head>)`
- `build: <reason the input could not be read>`

Commit ids and repository paths only, never an environment dump. The log line is how the maintainer
confirms the host's side of the contract in production (quickstart §4).

## Lists

Both lists are constants in the module, each pattern with its one-line reason (research R4).

- **Always-deploy**: FR-008's paths plus `scripts/deploy/**`.
- **Never-shipped**: research R4's table.

The test asserts that no never-shipped pattern matches an always-deploy path.

## Not this rule's job

- Branch filtering: `git.deploymentEnabled` already limits deployments to `main`. The rule only
  carries the dashboard preset's non-production check (FR-011).
- Deployment quota: a canceled build still counts against it (research R3).
- Forcing a deploy: the rule has no override flag, because a flag would be one more input that can
  go wrong. A dashboard redeploy, if the host re-runs the rule for it, builds the commit the last
  successful deployment already built, so the diff is empty, and step 3 makes that build (FR-010).
  Whether the host re-runs the rule for a redeploy at all is not documented; quickstart §4 records
  what it does.
