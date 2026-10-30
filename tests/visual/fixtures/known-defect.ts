// T744: a scenario whose page is known to fail one suite's assertion is not skipped and not run as
// "expected to fail" (`test.fail` accepts any failure, a timeout and a typo included). The suite runs
// its assertion through `expectKnownDefect`, which holds the failure to the one message the defect
// is filed with: a walk that throws something else fails, naming what it threw, and a walk that does
// not throw fails, telling the reader to remove the marker. That second half is what keeps the
// marker from outliving the fix. Everything the suite asserts after the walk still runs.

/** A defect a scenario is known to show to one suite. */
export interface KnownDefect {
  /** What is wrong and where it lives, in a sentence. */
  reason: string
  /** The failure the suite's assertion throws for this defect, and only this one. */
  message: RegExp
}

export async function expectKnownDefect(
  run: () => void | Promise<void>,
  defect: KnownDefect,
  context: string,
): Promise<void> {
  let thrown: unknown
  try {
    await run()
  } catch (error) {
    thrown = error
  }
  if (thrown === undefined) {
    throw new Error(
      `${context}: the assertion passed, but this scenario is marked with a known defect ` +
        `(${defect.reason}). The defect looks fixed: remove its \`knownDefects\` marker.`,
    )
  }
  const message = thrown instanceof Error ? thrown.message : String(thrown)
  if (!defect.message.test(message)) {
    throw new Error(
      `${context}: the assertion failed, but not with the known defect's message ` +
        `${String(defect.message)} (${defect.reason}). It threw: ${message}`,
      { cause: thrown },
    )
  }
}
