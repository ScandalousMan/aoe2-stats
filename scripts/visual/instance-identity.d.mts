// Declaration for `./instance-identity.mjs`, which `tests/visual/state-coverage-runtime.ts` imports.
// TypeScript pairs a `.d.mts` with the `.mjs` module of the same name.
export declare function instanceKey(instance: {
  component: string
  variant?: string | null
  size?: string | null
  disabledAt?: readonly string[]
}): string
