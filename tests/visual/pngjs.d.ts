// The part of `pngjs` that `state-signal-sweep.spec.ts` uses (`PNG.sync.read`, `PNG.sync.write`,
// `PNG.bitblt`, `new PNG({ width, height })`, `.data`). The package ships no types and `@types/pngjs`
// is not a dependency of the workspace root, so the typecheck of `tests/visual` (`tsconfig.check.json`,
// T712) declares what is read, and a use of anything else is a type error to be declared here.
declare module 'pngjs' {
  export class PNG {
    constructor(options?: { width?: number; height?: number })
    width: number
    height: number
    data: Buffer
    static sync: {
      read(buffer: Buffer): PNG
      write(png: PNG): Buffer
    }
    static bitblt(
      source: PNG,
      destination: PNG,
      sourceX: number,
      sourceY: number,
      width: number,
      height: number,
      destinationX: number,
      destinationY: number,
    ): void
  }
}
