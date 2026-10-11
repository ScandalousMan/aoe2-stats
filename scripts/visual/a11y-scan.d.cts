// Declaration for `./a11y-scan.cjs`, which `tests/visual/stories.spec.ts` imports. TypeScript pairs a
// `.d.cts` with the `.cjs` module of the same name; it exists so the typecheck of `tests/visual`
// (`tests/visual/tsconfig.check.json`, T712) reads a real type instead of an implicit `any` (TS7016).
// `a11y-scan.cjs` is the source of truth for what each function does.
export declare const allowlistPath: string
export declare function componentFromTitle(title: string): string
export declare function resetResultsDir(): void
export declare function recordScanned(component: string, theme: string): void
export declare function recordViolation(component: string, theme: string, rule: string): void
export declare function readAllowlist(): { component: string; rule: string }[]
export declare function isAllowed(component: string, rule: string): boolean
export declare function checkStaleness(): { component: string; rule: string }[]
